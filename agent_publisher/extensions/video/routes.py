"""Video extension API routes — Remotion-based video generation.

Endpoints:
  POST /generate         — Create video task
  GET  /status/{task_id} — Task status
  GET  /preview/{task_id} — Serve static HTML preview
  GET  /download/{task_id} — Download rendered MP4
"""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from agent_publisher.api.deps import get_db, get_current_user, UserContext
from agent_publisher.api.auth import verify_token
from agent_publisher.api.skills import verify_skill_token
from agent_publisher.config import settings
from agent_publisher.database import async_session_factory
from agent_publisher.models.account import Account
from agent_publisher.models.agent import Agent
from agent_publisher.models.article import Article
from agent_publisher.models.task import Task
from agent_publisher.services.task_service import TaskService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/extensions/video", tags=["video"])

_VIDEO_STORAGE_ROOT = Path("storage/video").resolve()


def _validate_file_path(file_path: str | None) -> Path | None:
    if not file_path:
        return None
    resolved = Path(file_path).resolve()
    if not resolved.is_relative_to(_VIDEO_STORAGE_ROOT):
        logger.warning("Path traversal blocked: %s", file_path)
        return None
    if not resolved.exists():
        return None
    return resolved


async def _resolve_user(request: Request, token: str | None, db: AsyncSession) -> tuple[str, bool]:
    auth_header = request.headers.get("authorization", "")
    raw_token = auth_header[7:] if auth_header.startswith("Bearer ") else None
    if not raw_token and token:
        raw_token = token
    if not raw_token:
        raise HTTPException(401, "Authentication required")
    if "|" not in raw_token:
        if not verify_token(raw_token):
            raise HTTPException(401, "Invalid or expired token")
        return "__admin__", True
    email = verify_skill_token(raw_token)
    if not email:
        raise HTTPException(401, "Invalid or expired token")
    return email, settings.is_admin(email)


async def _verify_task_ownership(task: Task, email: str, is_admin: bool, db: AsyncSession) -> None:
    if is_admin:
        return
    result = task.result or {}
    article_id = result.get("article_id")
    if article_id is None:
        return
    article = await db.get(Article, int(article_id))
    if not article:
        raise HTTPException(403, "Access denied")
    agent = await db.get(Agent, article.agent_id)
    if not agent:
        raise HTTPException(403, "Access denied")
    account = await db.get(Account, agent.account_id)
    if not account or account.owner_email != email:
        raise HTTPException(403, "Access denied")


# ---------------------------------------------------------------------------
# Request schemas
# ---------------------------------------------------------------------------


class VideoRequest(BaseModel):
    article_id: int


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post("/generate")
async def generate_video(
    req: VideoRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: UserContext = Depends(get_current_user),
):
    """Create a video generation task using Remotion pipeline."""
    article = await db.get(Article, req.article_id)
    if not article:
        raise HTTPException(404, "Article not found")
    if not user.is_admin:
        agent = await db.get(Agent, article.agent_id)
        if agent:
            account = await db.get(Account, agent.account_id)
            if not account or account.owner_email != user.email:
                raise HTTPException(403, "Access denied")

    task_svc = TaskService(db)
    task = await task_svc.create_task(None, "video_generate")

    asyncio.create_task(_execute_pipeline(task.id, req.article_id))

    return {"task_id": task.id}


@router.get("/status/{task_id}")
async def video_status(
    task_id: int,
    request: Request,
    token: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    """Get video task status and result info."""
    email, is_admin = await _resolve_user(request, token, db)
    task = await db.get(Task, task_id)
    if not task:
        raise HTTPException(403, "Access denied")
    await _verify_task_ownership(task, email, is_admin, db)

    result = task.result or {}
    has_preview = _validate_file_path(result.get("preview_path")) is not None
    has_mp4 = _validate_file_path(result.get("mp4_path")) is not None

    return {
        "task_id": task.id,
        "status": task.status,
        "steps": task.steps or [],
        "error": result.get("error"),
        "article_id": result.get("article_id"),
        "scene_count": result.get("scene_count", 0),
        "total_duration_s": result.get("total_duration_s", 0),
        "title": result.get("title", ""),
        "has_preview": has_preview,
        "has_mp4": has_mp4,
        "started_at": task.started_at.isoformat() if task.started_at else None,
        "finished_at": task.finished_at.isoformat() if task.finished_at else None,
    }


@router.get("/preview/{task_id}")
async def preview_video(
    task_id: int,
    request: Request,
    token: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    """Serve the HTML preview page (available before MP4 render completes)."""
    email, is_admin = await _resolve_user(request, token, db)
    task = await db.get(Task, task_id)
    if not task:
        raise HTTPException(403, "Access denied")
    await _verify_task_ownership(task, email, is_admin, db)

    if task.status not in ("success", "running"):
        raise HTTPException(400, f"Task not ready (status={task.status})")

    result = task.result or {}
    preview_path = _validate_file_path(result.get("preview_path"))
    if not preview_path:
        raise HTTPException(404, "Preview not ready yet")

    return FileResponse(preview_path, media_type="text/html")


@router.get("/download/{task_id}")
async def download_video(
    task_id: int,
    request: Request,
    token: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    """Download the rendered MP4 file."""
    email, is_admin = await _resolve_user(request, token, db)
    task = await db.get(Task, task_id)
    if not task:
        raise HTTPException(403, "Access denied")
    await _verify_task_ownership(task, email, is_admin, db)

    if task.status != "success":
        raise HTTPException(400, f"Task not complete (status={task.status})")

    result = task.result or {}
    mp4_path = _validate_file_path(result.get("mp4_path"))
    if not mp4_path:
        raise HTTPException(404, "MP4 not available (Remotion render may have been skipped)")

    title = result.get("title", "video")
    safe_title = "".join(c for c in title if c.isalnum() or c in "- _")[:30] or "video"

    return FileResponse(
        mp4_path,
        media_type="video/mp4",
        filename=f"{safe_title}.mp4",
    )


@router.get("/props/{task_id}")
async def get_props(
    task_id: int,
    request: Request,
    token: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    """Return the video props JSON (script data for Remotion)."""
    import json as _json

    email, is_admin = await _resolve_user(request, token, db)
    task = await db.get(Task, task_id)
    if not task:
        raise HTTPException(403, "Access denied")
    await _verify_task_ownership(task, email, is_admin, db)

    result = task.result or {}
    props_path = _validate_file_path(result.get("props_path"))
    if not props_path:
        raise HTTPException(404, "Props not found")

    data = _json.loads(props_path.read_text(encoding="utf-8"))
    return JSONResponse(content=data)


# ---------------------------------------------------------------------------
# Background task executor
# ---------------------------------------------------------------------------


async def _execute_pipeline(task_id: int, article_id: int) -> None:
    async with async_session_factory() as session:
        from agent_publisher.extensions.video.service import run_video_pipeline

        await run_video_pipeline(task_id, article_id, session)
