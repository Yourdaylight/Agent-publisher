from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from agent_publisher.database import async_session_factory
from agent_publisher.models.agent import Agent
from agent_publisher.models.task import Task
from agent_publisher.services.article_service import ArticleService

logger = logging.getLogger(__name__)


class TaskService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_task(
        self, agent_id: int | None, task_type: str
    ) -> Task:
        task = Task(
            agent_id=agent_id,
            task_type=task_type,
            status="pending",
        )
        self.session.add(task)
        await self.session.commit()
        await self.session.refresh(task)
        return task

    async def run_generate(self, agent_id: int) -> Task:
        """Create a generate task and execute it asynchronously in the background."""
        task = await self.create_task(agent_id, "generate")
        # Fire and forget – execute in background with its own session
        asyncio.create_task(_execute_generate(task.id, agent_id))
        return task

    async def run_publish(self, article_id: int) -> Task:
        """Publish an article to WeChat draft box."""
        task = await self.create_task(None, "publish")
        task.status = "running"
        task.started_at = datetime.now(timezone.utc)
        await self.session.commit()

        try:
            article_svc = ArticleService(self.session)
            media_id = await article_svc.publish_article(article_id)

            task.status = "success"
            task.result = {"article_id": article_id, "media_id": media_id}
        except Exception as e:
            logger.error("Publish task %d failed: %s", task.id, e)
            task.status = "failed"
            task.result = {"error": str(e)}

        task.finished_at = datetime.now(timezone.utc)
        await self.session.commit()
        return task

    async def run_batch_all(self) -> list[Task]:
        """Create generate tasks for all active agents and execute them asynchronously."""
        stmt = select(Agent).where(Agent.is_active.is_(True))
        result = await self.session.execute(stmt)
        agents = result.scalars().all()

        tasks = []
        for agent in agents:
            task = await self.create_task(agent.id, "generate")
            asyncio.create_task(_execute_generate(task.id, agent.id))
            tasks.append(task)
        return tasks


async def _execute_generate(task_id: int, agent_id: int) -> None:
    """Background coroutine that performs the actual article generation.

    Uses its own database session so the original request can return immediately.
    """
    async with async_session_factory() as session:
        task = await session.get(Task, task_id)
        if not task:
            logger.error("Task %d not found, cannot execute", task_id)
            return

        task.status = "running"
        task.started_at = datetime.now(timezone.utc)
        task.steps = []
        await session.commit()

        # Helper to record step progress into task.steps
        step_start_times: dict[str, str] = {}

        async def _step_callback(step_name: str, status: str, output: dict) -> None:
            finished_at = datetime.now(timezone.utc).isoformat()
            started_at = step_start_times.pop(step_name, finished_at)
            step_entry = {
                "name": step_name,
                "status": status,
                "started_at": started_at,
                "finished_at": finished_at,
                "output": output,
            }
            # SQLAlchemy won't detect in-place list mutation, so reassign
            task.steps = [*(task.steps or []), step_entry]
            await session.commit()

        try:
            agent = await session.get(Agent, agent_id)
            if not agent:
                raise ValueError(f"Agent {agent_id} not found")

            # Record the start time of the first step
            step_start_times["rss_fetch"] = datetime.now(timezone.utc).isoformat()

            article_svc = ArticleService(session)

            # Wrap step_callback to also track start times for upcoming steps
            async def _tracked_callback(step_name: str, status: str, output: dict) -> None:
                await _step_callback(step_name, status, output)
                # Pre-record start time for the next step
                next_steps = {
                    "rss_fetch": "llm_generate",
                    "llm_generate": "image_generate",
                    "image_generate": "save_article",
                }
                next_step = next_steps.get(step_name)
                if next_step:
                    step_start_times[next_step] = datetime.now(timezone.utc).isoformat()

            # Chunk callback to store streaming LLM output for SSE consumers
            async def _chunk_callback(chunk: str) -> None:
                current_result = task.result or {}
                llm_text = current_result.get("llm_partial", "") + chunk
                task.result = {**current_result, "llm_partial": llm_text}
                await session.commit()

            article = await article_svc.generate_article(
                agent,
                step_callback=_tracked_callback,
                chunk_callback=_chunk_callback,
            )

            task.status = "success"
            task.result = {"article_id": article.id, "title": article.title}
        except Exception as e:
            logger.error("Task %d failed: %s", task_id, e)
            task.status = "failed"
            task.result = {"error": str(e)}

        task.finished_at = datetime.now(timezone.utc)
        await session.commit()


async def run_scheduled_agent(agent_id: int) -> None:
    """Entry point for APScheduler to trigger agent generation."""
    async with async_session_factory() as session:
        task_svc = TaskService(session)
        await task_svc.run_generate(agent_id)
