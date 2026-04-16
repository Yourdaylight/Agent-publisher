from __future__ import annotations

import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from sqlalchemy import select

from agent_publisher.database import async_session_factory
from agent_publisher.models.agent import Agent
from agent_publisher.models.account import Account
from agent_publisher.services.task_service import run_scheduled_agent

logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler()

TRENDING_JOB_ID = "global_trending_refresh"
PLATFORM_TOKEN_JOB_ID = "platform_token_refresh"


async def run_trending_refresh() -> None:
    """全局热榜定时刷新任务 — 由调度器自动触发，禁止普通用户手动调用。"""
    logger.info("Scheduler: running global trending refresh")
    try:
        async with async_session_factory() as session:
            from agent_publisher.services.source_registry_service import SourceRegistryService

            registry = SourceRegistryService(session)
            result = await registry.collect_all_trending()
            logger.info(
                "Scheduler: trending refresh done — sources=%s new_items=%d",
                result.get("platforms_collected", []),
                result.get("new_items", 0),
            )
    except Exception as e:
        logger.error("Scheduler: trending refresh failed: %s", e, exc_info=True)


def sync_trending_schedule(interval_minutes: int | None = None) -> None:
    """Register (or update) the global trending refresh job.

    Args:
        interval_minutes: refresh interval in minutes; 0 or None disables the job.
                          Defaults to settings.trending_refresh_interval.
    """
    from agent_publisher.config import settings

    minutes = (
        interval_minutes if interval_minutes is not None else settings.trending_refresh_interval
    )

    # Remove existing job first
    if scheduler.get_job(TRENDING_JOB_ID):
        scheduler.remove_job(TRENDING_JOB_ID)

    if minutes <= 0:
        logger.info("Trending auto-refresh disabled (interval=0)")
        return

    scheduler.add_job(
        run_trending_refresh,
        trigger=IntervalTrigger(minutes=minutes),
        id=TRENDING_JOB_ID,
        replace_existing=True,
        name=f"Global trending refresh (every {minutes}min)",
    )
    logger.info("Scheduled global trending refresh every %d minutes", minutes)


def _parse_cron_trigger(cron_str: str) -> CronTrigger | None:
    """Parse a 5-field cron string into a CronTrigger, or return None."""
    parts = cron_str.split()
    if len(parts) != 5:
        return None
    return CronTrigger(
        minute=parts[0],
        hour=parts[1],
        day=parts[2],
        month=parts[3],
        day_of_week=parts[4],
    )


def _offset_cron_minutes(cron_str: str, offset_minutes: int = -30) -> str | None:
    """Shift the minute/hour of a cron expression by offset_minutes.

    Only works for simple numeric minute+hour crons (e.g. '0 8 * * *').
    Returns None if the cron is too complex (wildcards, ranges, etc.).
    """
    parts = cron_str.split()
    if len(parts) != 5:
        return None
    minute_str, hour_str = parts[0], parts[1]

    # Only handle simple numeric values
    if not minute_str.isdigit() or not hour_str.isdigit():
        return None

    minute = int(minute_str)
    hour = int(hour_str)

    total_minutes = hour * 60 + minute + offset_minutes
    if total_minutes < 0:
        total_minutes += 24 * 60
    total_minutes %= 24 * 60

    new_hour = total_minutes // 60
    new_minute = total_minutes % 60

    return f"{new_minute} {new_hour} {parts[2]} {parts[3]} {parts[4]}"


async def run_scheduled_collection(agent_id: int) -> None:
    """定时采集任务 — 在文章生成前运行"""
    from agent_publisher.services.source_registry_service import SourceRegistryService

    logger.info("Running scheduled collection for agent %d", agent_id)
    try:
        async with async_session_factory() as session:
            agent = await session.get(Agent, agent_id)
            if not agent or not agent.is_active:
                logger.info("Agent %d is not active, skipping collection", agent_id)
                return

            registry = SourceRegistryService(session)
            result = await registry.collect_for_agent(agent)
            total = sum(len(ids) for ids in result.values())
            logger.info(
                "Scheduled collection for agent %d (%s): %d materials",
                agent_id,
                agent.name,
                total,
            )
    except Exception as e:
        logger.error("Scheduled collection failed for agent %d: %s", agent_id, e, exc_info=True)


async def refresh_platform_tokens() -> None:
    """Refresh authorizer_access_token for platform-authorized accounts.

    Runs periodically to keep tokens fresh. Only refreshes tokens that
    will expire within the next 30 minutes.
    """
    from agent_publisher.config import settings
    from datetime import datetime, timedelta, timezone

    if not settings.wechat_platform_appid.strip():
        return  # Platform not configured, skip

    logger.info("Scheduler: refreshing platform tokens")
    try:
        async with async_session_factory() as session:
            result = await session.execute(select(Account).where(Account.auth_mode == "platform"))
            accounts = result.scalars().all()

            refreshed = 0
            for account in accounts:
                # Check if token will expire soon
                expires_at = account.authorizer_token_expires_at
                if expires_at:
                    expires_at = (
                        expires_at.replace(tzinfo=timezone.utc)
                        if expires_at.tzinfo is None
                        else expires_at
                    )
                if (
                    not account.authorizer_access_token
                    or not expires_at
                    or expires_at < datetime.now(timezone.utc) + timedelta(minutes=30)
                ):
                    try:
                        from agent_publisher.services.wechat_platform_service import (
                            WeChatPlatformService,
                        )

                        (
                            token,
                            new_expires_at,
                        ) = await WeChatPlatformService.refresh_authorizer_token(
                            account.authorizer_appid, account.authorizer_refresh_token
                        )
                        account.authorizer_access_token = token
                        account.authorizer_token_expires_at = new_expires_at
                        account.access_token = token
                        account.token_expires_at = new_expires_at
                        refreshed += 1
                    except Exception as e:
                        logger.error(
                            "Failed to refresh token for account id=%d appid=%s: %s",
                            account.id,
                            account.authorizer_appid,
                            e,
                        )

            if refreshed > 0:
                await session.commit()
            logger.info(
                "Scheduler: platform token refresh done — refreshed=%d/%d", refreshed, len(accounts)
            )

    except Exception as e:
        logger.error("Scheduler: platform token refresh failed: %s", e, exc_info=True)


def sync_platform_token_schedule() -> None:
    """Register the platform token refresh job (every 90 minutes)."""
    from agent_publisher.config import settings

    if not settings.wechat_platform_appid.strip():
        return  # Platform not configured, skip

    if scheduler.get_job(PLATFORM_TOKEN_JOB_ID):
        scheduler.remove_job(PLATFORM_TOKEN_JOB_ID)

    scheduler.add_job(
        refresh_platform_tokens,
        trigger=IntervalTrigger(minutes=90),
        id=PLATFORM_TOKEN_JOB_ID,
        replace_existing=True,
        name="Platform token refresh (every 90min)",
    )
    logger.info("Scheduled platform token refresh every 90 minutes")


async def sync_agent_schedules() -> None:
    """Load all active agents and register their cron jobs.

    For each agent, registers:
      1. The main article generation job (existing)
      2. A pre-generation collection job (30 min before, if cron is simple)
    """
    scheduler.remove_all_jobs()
    async with async_session_factory() as session:
        result = await session.execute(select(Agent).where(Agent.is_active.is_(True)))
        agents = result.scalars().all()

    for agent in agents:
        if not agent.schedule_cron:
            continue
        try:
            # Main generation job
            trigger = _parse_cron_trigger(agent.schedule_cron)
            if not trigger:
                logger.warning("Invalid cron for agent %d: %s", agent.id, agent.schedule_cron)
                continue

            scheduler.add_job(
                run_scheduled_agent,
                trigger=trigger,
                args=[agent.id],
                id=f"agent_{agent.id}",
                replace_existing=True,
                name=f"Agent {agent.id}: {agent.name}",
            )
            logger.info(
                "Scheduled agent %d (%s) with cron: %s", agent.id, agent.name, agent.schedule_cron
            )

            # Pre-generation collection job (30 min before)
            collect_cron = _offset_cron_minutes(agent.schedule_cron, offset_minutes=-30)
            if collect_cron:
                collect_trigger = _parse_cron_trigger(collect_cron)
                if collect_trigger:
                    scheduler.add_job(
                        run_scheduled_collection,
                        trigger=collect_trigger,
                        args=[agent.id],
                        id=f"collect_{agent.id}",
                        replace_existing=True,
                        name=f"Collect for Agent {agent.id}: {agent.name}",
                    )
                    logger.info(
                        "Scheduled collection for agent %d at cron: %s (30 min before generation)",
                        agent.id,
                        collect_cron,
                    )

        except Exception as e:
            logger.error("Failed to schedule agent %d: %s", agent.id, e)

    logger.info("Scheduled %d agent jobs", len(scheduler.get_jobs()))
