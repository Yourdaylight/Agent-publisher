from __future__ import annotations

import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from sqlalchemy import select

from agent_publisher.database import async_session_factory
from agent_publisher.models.agent import Agent
from agent_publisher.services.task_service import run_scheduled_agent

logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler()


async def sync_agent_schedules() -> None:
    """Load all active agents and register their cron jobs."""
    scheduler.remove_all_jobs()
    async with async_session_factory() as session:
        result = await session.execute(select(Agent).where(Agent.is_active.is_(True)))
        agents = result.scalars().all()

    for agent in agents:
        if not agent.schedule_cron:
            continue
        try:
            parts = agent.schedule_cron.split()
            if len(parts) == 5:
                trigger = CronTrigger(
                    minute=parts[0], hour=parts[1], day=parts[2],
                    month=parts[3], day_of_week=parts[4],
                )
            else:
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
            logger.info("Scheduled agent %d (%s) with cron: %s", agent.id, agent.name, agent.schedule_cron)
        except Exception as e:
            logger.error("Failed to schedule agent %d: %s", agent.id, e)

    logger.info("Scheduled %d agent jobs", len(scheduler.get_jobs()))
