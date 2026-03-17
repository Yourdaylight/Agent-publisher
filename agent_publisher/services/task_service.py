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

    async def run_publish(
        self,
        article_id: int,
        target_account_ids: list[int] | None = None,
    ) -> Task:
        """Publish an article to one or more WeChat draft boxes."""
        task = await self.create_task(None, "publish")
        task.status = "running"
        task.started_at = datetime.now(timezone.utc)
        await self.session.commit()

        try:
            article_svc = ArticleService(self.session)
            publish_result = await article_svc.publish_article(
                article_id,
                target_account_ids=target_account_ids,
            )

            task.status = "success" if publish_result.ok else "failed"
            task.result = publish_result.model_dump()
        except Exception as e:
            logger.error("Publish task %d failed: %s", task.id, e)
            task.status = "failed"
            task.result = {"article_id": article_id, "error": str(e)}

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

    async def run_batch_variants(
        self,
        source_article_id: int,
        agent_ids: list[int],
        style_ids: list[str],
    ) -> Task:
        """Create a batch variant generation task.

        Cycles style_ids across agent_ids when len(agent_ids) > len(style_ids).
        Maximum 15 combinations per batch.
        """
        if not style_ids:
            raise ValueError("At least one style_id is required")
        if not agent_ids:
            raise ValueError("At least one agent_id is required")

        # Build (agent_id, style_id) combinations, cycling styles
        combinations: list[tuple[int, str]] = []
        for i, agent_id in enumerate(agent_ids):
            sid = style_ids[i % len(style_ids)]
            combinations.append((agent_id, sid))

        if len(combinations) > 15:
            raise ValueError("Maximum 15 agent×style combinations per batch")

        # Create batch task
        task = await self.create_task(None, "batch_variant")
        task.result = {
            "source_article_id": source_article_id,
            "total": len(combinations),
            "completed": 0,
            "succeeded": 0,
            "failed": 0,
            "subtasks": [
                {
                    "agent_id": aid,
                    "style_id": sid,
                    "status": "pending",
                    "article_id": None,
                    "error": None,
                }
                for aid, sid in combinations
            ],
        }
        await self.session.commit()

        # Fire background execution
        asyncio.create_task(
            _execute_batch_variants(task.id, source_article_id, combinations)
        )
        return task


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


async def _execute_batch_variants(
    task_id: int,
    source_article_id: int,
    combinations: list[tuple[int, str]],
) -> None:
    """Background coroutine that executes batch variant generation.

    Uses asyncio.Semaphore(3) to limit concurrent LLM calls.
    """
    async with async_session_factory() as session:
        task = await session.get(Task, task_id)
        if not task:
            logger.error("Batch variant task %d not found", task_id)
            return

        task.status = "running"
        task.started_at = datetime.now(timezone.utc)
        await session.commit()

        semaphore = asyncio.Semaphore(3)
        result_data = task.result or {}
        subtasks = result_data.get("subtasks", [])
        succeeded = 0
        failed = 0

        async def _process_one(index: int, agent_id: int, style_id: str) -> None:
            nonlocal succeeded, failed
            async with semaphore:
                # Each subtask gets its own session to avoid conflicts
                async with async_session_factory() as sub_session:
                    try:
                        article_svc = ArticleService(sub_session)
                        variant = await article_svc.generate_variant(
                            source_article_id=source_article_id,
                            target_agent_id=agent_id,
                            style_id=style_id,
                        )
                        subtasks[index]["status"] = "success"
                        subtasks[index]["article_id"] = variant.id
                        succeeded += 1
                    except Exception as e:
                        logger.error(
                            "Variant generation failed (agent=%d, style=%s): %s",
                            agent_id, style_id, e,
                        )
                        subtasks[index]["status"] = "failed"
                        subtasks[index]["error"] = str(e)
                        failed += 1

                # Update batch task progress in the main session
                completed = succeeded + failed
                result_data["completed"] = completed
                result_data["succeeded"] = succeeded
                result_data["failed"] = failed
                result_data["subtasks"] = subtasks
                task.result = {**result_data}  # Force SQLAlchemy to detect change
                await session.commit()

        # Run all subtasks concurrently (bounded by semaphore)
        tasks = [
            _process_one(i, agent_id, style_id)
            for i, (agent_id, style_id) in enumerate(combinations)
        ]
        await asyncio.gather(*tasks, return_exceptions=True)

        # Final status
        if failed == 0:
            task.status = "completed"
        elif succeeded == 0:
            task.status = "failed"
        else:
            task.status = "partial_completed"

        task.finished_at = datetime.now(timezone.utc)
        result_data["completed"] = succeeded + failed
        result_data["succeeded"] = succeeded
        result_data["failed"] = failed
        task.result = {**result_data}
        await session.commit()

        logger.info(
            "Batch variant task %d finished: %d succeeded, %d failed",
            task_id, succeeded, failed,
        )
