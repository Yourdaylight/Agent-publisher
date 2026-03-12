import asyncio
import json

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from agent_publisher.api.deps import get_db, get_current_user, UserContext
from agent_publisher.database import async_session_factory
from agent_publisher.models.account import Account
from agent_publisher.models.agent import Agent
from agent_publisher.models.task import Task
from agent_publisher.schemas.task import BatchRequest, TaskOut
from agent_publisher.services.task_service import TaskService

router = APIRouter(prefix="/api/tasks", tags=["tasks"])


async def _get_task_with_ownership(
    task_id: int, user: UserContext, db: AsyncSession
) -> Task:
    """Fetch a task and verify ownership through Agent -> Account chain."""
    task = await db.get(Task, task_id)
    if not task:
        raise HTTPException(404, "Task not found")
    if not user.is_admin and task.agent_id:
        agent = await db.get(Agent, task.agent_id)
        if agent:
            account = await db.get(Account, agent.account_id)
            if not account or account.owner_email != user.email:
                raise HTTPException(403, "Access denied")
    return task


@router.get("", response_model=list[TaskOut])
async def list_tasks(
    status: str | None = None,
    db: AsyncSession = Depends(get_db),
    user: UserContext = Depends(get_current_user),
):
    stmt = select(Task).order_by(Task.id.desc())
    if not user.is_admin:
        stmt = stmt.join(Agent).join(Account).where(Account.owner_email == user.email)
    if status:
        stmt = stmt.where(Task.status == status)
    result = await db.execute(stmt)
    return result.scalars().all()


@router.get("/{task_id}", response_model=TaskOut)
async def get_task(
    task_id: int,
    db: AsyncSession = Depends(get_db),
    user: UserContext = Depends(get_current_user),
):
    return await _get_task_with_ownership(task_id, user, db)


@router.get("/{task_id}/stream")
async def stream_task(task_id: int):
    """SSE endpoint that pushes task progress in real-time."""

    async def _event_generator():
        last_steps_len = 0
        last_llm_len = 0
        while True:
            async with async_session_factory() as session:
                task = await session.get(Task, task_id)
                if not task:
                    yield f"event: error\ndata: {json.dumps({'error': 'Task not found'})}\n\n"
                    return

                current_steps = task.steps or []
                current_result = task.result or {}
                llm_partial = current_result.get("llm_partial", "")

                # Push LLM streaming chunks as they arrive
                if len(llm_partial) > last_llm_len:
                    new_text = llm_partial[last_llm_len:]
                    last_llm_len = len(llm_partial)
                    yield f"event: llm_chunk\ndata: {json.dumps({'chunk': new_text}, ensure_ascii=False)}\n\n"

                # Build progress payload (exclude llm_partial to keep payload small)
                result_clean = {k: v for k, v in current_result.items() if k != "llm_partial"}
                payload = {
                    "task_id": task.id,
                    "status": task.status,
                    "steps": current_steps,
                    "result": result_clean,
                    "started_at": task.started_at.isoformat() if task.started_at else None,
                    "finished_at": task.finished_at.isoformat() if task.finished_at else None,
                }

                # Push progress when there are new steps or status changed
                if len(current_steps) != last_steps_len or task.status in ("success", "failed"):
                    last_steps_len = len(current_steps)
                    yield f"event: progress\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"

                if task.status in ("success", "failed"):
                    yield f"event: done\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"
                    return

            await asyncio.sleep(1)

    return StreamingResponse(
        _event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/batch")
async def batch_run(
    req: BatchRequest,
    db: AsyncSession = Depends(get_db),
    user: UserContext = Depends(get_current_user),
):
    task_svc = TaskService(db)

    if req.agent_ids:
        results = []
        for agent_id in req.agent_ids:
            agent = await db.get(Agent, agent_id)
            if not agent:
                results.append({"agent_id": agent_id, "error": "not found"})
                continue
            # Verify ownership
            if not user.is_admin:
                account = await db.get(Account, agent.account_id)
                if not account or account.owner_email != user.email:
                    results.append({"agent_id": agent_id, "error": "access denied"})
                    continue
            task = await task_svc.run_generate(agent_id)
            results.append({"agent_id": agent_id, "task_id": task.id, "status": task.status})
        return {"results": results}
    else:
        if not user.is_admin:
            # Normal users can only batch-run their own agents
            stmt = select(Agent.id).join(Account).where(Account.owner_email == user.email)
            result = await db.execute(stmt)
            user_agent_ids = [row[0] for row in result.all()]
            results = []
            for agent_id in user_agent_ids:
                task = await task_svc.run_generate(agent_id)
                results.append({"agent_id": agent_id, "task_id": task.id, "status": task.status})
            return {"results": results}
        tasks = await task_svc.run_batch_all()
        return {
            "results": [
                {"agent_id": t.agent_id, "task_id": t.id, "status": t.status}
                for t in tasks
            ]
        }
