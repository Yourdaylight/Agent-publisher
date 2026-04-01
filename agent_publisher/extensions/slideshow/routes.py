"""Slideshow API routes — v3 chapter-parallel, no video/TTS dependencies.

Endpoints:
  POST /generate         — Create slideshow task (chapter pipeline)
  GET  /status/{task_id} — Task status with chapter info
  GET  /preview/{task_id} — Serve concat.html player
  GET  /draft/{task_id}  — Get orchestrator output for review
  POST /draft/{task_id}/confirm — Accept edited chapter structure
  POST /draft/{task_id}/skip   — Continue with original structure
  GET  /chapter/{task_id}/{chapter_id} — Serve single chapter HTML
  GET  /timeline/{task_id} — Serve timeline.json
"""
from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from agent_publisher.api.deps import get_db, get_current_user, UserContext
from agent_publisher.api.skills import verify_skill_token
from agent_publisher.api.auth import verify_token
from agent_publisher.config import settings
from agent_publisher.database import async_session_factory
from agent_publisher.models.account import Account
from agent_publisher.models.agent import Agent
from agent_publisher.models.article import Article
from agent_publisher.models.task import Task
from agent_publisher.services.task_service import TaskService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/extensions/slideshow", tags=["slideshow"])

# Allowed base directory for slideshow output files (defense-in-depth)
_SLIDESHOW_STORAGE_ROOT = Path("storage/slideshow").resolve()


def _validate_file_path(file_path: str | None, must_exist: bool = True) -> Path | None:
    """Validate that a file path stays within the slideshow storage root."""
    if not file_path:
        return None
    resolved = Path(file_path).resolve()
    if not resolved.is_relative_to(_SLIDESHOW_STORAGE_ROOT):
        logger.warning("Path traversal blocked: %s is outside %s", file_path, _SLIDESHOW_STORAGE_ROOT)
        return None
    if must_exist and not resolved.exists():
        return None
    return resolved


# ---------------------------------------------------------------------------
# Auth helpers (unchanged from v2)
# ---------------------------------------------------------------------------

async def _resolve_user(
    request: Request,
    token: str | None,
    db: AsyncSession,
) -> tuple[str, bool]:
    """Return (email, is_admin) from either Authorization header or ?token= querystring."""
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


async def _verify_task_ownership(
    task: Task,
    email: str,
    is_admin: bool,
    db: AsyncSession,
) -> None:
    """Verify the given user owns the task's article chain."""
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

class SlideshowRequest(BaseModel):
    article_id: int
    skip_review: bool = False
    mode: str = "slideshow"  # "slideshow" | "video"


class DraftConfirmRequest(BaseModel):
    orchestrator_output: dict | None = None  # New: chapter structure
    slides: list[dict] | None = None  # Legacy: flat slides array


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("/generate")
async def generate_slideshow(
    req: SlideshowRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: UserContext = Depends(get_current_user),
):
    """Create a slideshow task using the chapter-parallel pipeline.

    If skip_review=False (default): generates orchestrator outline and pauses at draft_ready.
    If skip_review=True: runs full pipeline (orchestrator + chapters + assembly).
    """
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
    task = await task_svc.create_task(None, "slideshow_generate")

    if req.skip_review:
        asyncio.create_task(_execute_full_pipeline(task.id, req.article_id, mode=req.mode))
    else:
        asyncio.create_task(_execute_outline_only(task.id, req.article_id))

    return {"task_id": task.id, "mode": req.mode, "review": "skip_review" if req.skip_review else "draft_review"}


@router.get("/status/{task_id}")
async def slideshow_status(
    task_id: int,
    request: Request,
    token: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    """Get slideshow task status with chapter details."""
    email, is_admin = await _resolve_user(request, token, db)

    task = await db.get(Task, task_id)
    if not task:
        raise HTTPException(403, "Access denied")

    await _verify_task_ownership(task, email, is_admin, db)

    result = task.result or {}
    has_player = _validate_file_path(result.get("concat_path")) is not None
    has_timeline = _validate_file_path(result.get("timeline_path")) is not None

    return {
        "task_id": task.id,
        "status": task.status,
        "mode": result.get("mode", "slideshow"),
        "steps": task.steps or [],
        "error": result.get("error"),
        "article_id": result.get("article_id"),
        "chapter_count": result.get("chapter_count", 0),
        "scene_count": result.get("scene_count", 0),
        "has_player": has_player,
        "has_timeline": has_timeline,
        "chapters": result.get("chapters", []),
        "scenes": result.get("scenes", []),
        "started_at": task.started_at.isoformat() if task.started_at else None,
        "finished_at": task.finished_at.isoformat() if task.finished_at else None,
    }


@router.get("/preview/{task_id}")
async def preview_slideshow(
    task_id: int,
    request: Request,
    token: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    """Serve the concat.html player for in-browser preview."""
    email, is_admin = await _resolve_user(request, token, db)

    task = await db.get(Task, task_id)
    if not task:
        raise HTTPException(403, "Access denied")

    await _verify_task_ownership(task, email, is_admin, db)

    if task.status != "success":
        raise HTTPException(400, f"Task not ready (status={task.status})")

    result = task.result or {}
    concat_path = _validate_file_path(result.get("concat_path"))
    if not concat_path:
        raise HTTPException(404, "Player HTML not found")

    return FileResponse(concat_path, media_type="text/html")


@router.get("/chapter/{task_id}/{chapter_id}")
async def get_chapter_html(
    task_id: int,
    chapter_id: str,
    request: Request,
    token: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    """Serve a single chapter's HTML file."""
    email, is_admin = await _resolve_user(request, token, db)

    task = await db.get(Task, task_id)
    if not task:
        raise HTTPException(403, "Access denied")

    await _verify_task_ownership(task, email, is_admin, db)

    if task.status != "success":
        raise HTTPException(400, f"Task not ready (status={task.status})")

    result = task.result or {}
    output_dir = result.get("output_dir")
    if not output_dir:
        raise HTTPException(404, "Output directory not found")

    # Validate chapter_id to prevent path traversal
    if not chapter_id.replace("_", "").replace("-", "").isalnum():
        raise HTTPException(400, "Invalid chapter_id")

    chapter_path = _validate_file_path(f"{output_dir}/chapters/{chapter_id}.html")
    if not chapter_path:
        raise HTTPException(404, f"Chapter {chapter_id} not found")

    return FileResponse(chapter_path, media_type="text/html")


@router.get("/scene/{task_id}/{scene_id}")
async def get_scene_html(
    task_id: int,
    scene_id: str,
    request: Request,
    token: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    """Serve a single scene's HTML file (vertical video mode)."""
    email, is_admin = await _resolve_user(request, token, db)

    task = await db.get(Task, task_id)
    if not task:
        raise HTTPException(403, "Access denied")

    await _verify_task_ownership(task, email, is_admin, db)

    if task.status != "success":
        raise HTTPException(400, f"Task not ready (status={task.status})")

    result = task.result or {}
    output_dir = result.get("output_dir")
    if not output_dir:
        raise HTTPException(404, "Output directory not found")

    # Validate scene_id to prevent path traversal
    if not scene_id.replace("_", "").replace("-", "").isalnum():
        raise HTTPException(400, "Invalid scene_id")

    scene_path = _validate_file_path(f"{output_dir}/scenes/{scene_id}.html")
    if not scene_path:
        raise HTTPException(404, f"Scene {scene_id} not found")

    return FileResponse(scene_path, media_type="text/html")


@router.get("/timeline/{task_id}")
async def get_timeline(
    task_id: int,
    request: Request,
    token: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    """Serve the timeline.json metadata file."""
    email, is_admin = await _resolve_user(request, token, db)

    task = await db.get(Task, task_id)
    if not task:
        raise HTTPException(403, "Access denied")

    await _verify_task_ownership(task, email, is_admin, db)

    if task.status != "success":
        raise HTTPException(400, f"Task not ready (status={task.status})")

    result = task.result or {}
    timeline_path = _validate_file_path(result.get("timeline_path"))
    if not timeline_path:
        raise HTTPException(404, "Timeline not found")

    timeline_data = json.loads(timeline_path.read_text(encoding="utf-8"))
    return JSONResponse(content=timeline_data)


# ---------------------------------------------------------------------------
# Draft review endpoints
# ---------------------------------------------------------------------------

@router.get("/draft/{task_id}")
async def get_draft(
    task_id: int,
    request: Request,
    token: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    """Return the orchestrator output (chapter structure) for user review."""
    email, is_admin = await _resolve_user(request, token, db)
    task = await db.get(Task, task_id)
    if not task:
        raise HTTPException(403, "Access denied")
    await _verify_task_ownership(task, email, is_admin, db)

    if task.status not in ("draft_ready", "running", "success"):
        raise HTTPException(400, f"No draft available (status={task.status})")

    result = task.result or {}
    orchestrator_output = result.get("orchestrator_output")
    slides_draft = result.get("slides_draft")

    if not orchestrator_output and not slides_draft:
        raise HTTPException(404, "Draft not found — outline may still be generating")

    return {
        "task_id": task_id,
        "status": task.status,
        "orchestrator_output": orchestrator_output,
        # Legacy compat
        "slides": slides_draft,
        "slide_count": len(slides_draft) if slides_draft else 0,
        "chapter_count": len(orchestrator_output.get("chapters", [])) if orchestrator_output else 0,
    }


@router.post("/draft/{task_id}/confirm")
async def confirm_draft(
    task_id: int,
    body: DraftConfirmRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: UserContext = Depends(get_current_user),
):
    """Accept (optionally edited) chapter structure and start generation."""
    task = await db.get(Task, task_id)
    if not task:
        raise HTTPException(403, "Access denied")
    await _verify_task_ownership(task, user.email, user.is_admin, db)

    if task.status != "draft_ready":
        raise HTTPException(400, f"Task is not in draft_ready state (status={task.status})")

    result = task.result or {}
    article_id = result.get("article_id")
    if not article_id:
        raise HTTPException(400, "Missing article_id in task result")

    # Use new orchestrator_output if provided, else fall back to legacy slides
    if body.orchestrator_output:
        orchestrator_output = body.orchestrator_output
    elif body.slides:
        # Legacy: convert slides to orchestrator format
        from agent_publisher.extensions.slideshow.service import _slides_to_orchestrator
        orchestrator_output = _slides_to_orchestrator(body.slides)
    else:
        # Use the original orchestrator output
        orchestrator_output = result.get("orchestrator_output")
        if not orchestrator_output:
            raise HTTPException(400, "No orchestrator_output or slides provided")

    asyncio.create_task(
        _execute_from_draft(task_id, article_id, orchestrator_output)
    )

    chapter_count = len(orchestrator_output.get("chapters", []))
    return {"task_id": task_id, "status": "running", "chapter_count": chapter_count}


@router.post("/draft/{task_id}/skip")
async def skip_draft(
    task_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: UserContext = Depends(get_current_user),
):
    """Skip review and generate using the original orchestrator output."""
    task = await db.get(Task, task_id)
    if not task:
        raise HTTPException(403, "Access denied")
    await _verify_task_ownership(task, user.email, user.is_admin, db)

    if task.status != "draft_ready":
        raise HTTPException(400, f"Task is not in draft_ready state (status={task.status})")

    result = task.result or {}
    article_id = result.get("article_id")
    orchestrator_output = result.get("orchestrator_output")

    if not article_id or not orchestrator_output:
        raise HTTPException(400, "Missing article_id or orchestrator_output in task")

    asyncio.create_task(
        _execute_from_draft(task_id, article_id, orchestrator_output)
    )

    chapter_count = len(orchestrator_output.get("chapters", []))
    return {"task_id": task_id, "status": "running", "chapter_count": chapter_count}


# ---------------------------------------------------------------------------
# Background task executors
# ---------------------------------------------------------------------------

async def _execute_full_pipeline(task_id: int, article_id: int, *, mode: str = "slideshow") -> None:
    """Full pipeline: orchestrator + parallel chapters/scenes + assembly."""
    async with async_session_factory() as session:
        from agent_publisher.extensions.slideshow.service import run_chapter_pipeline
        await run_chapter_pipeline(task_id, article_id, session, mode=mode)


async def _execute_outline_only(task_id: int, article_id: int) -> None:
    """Phase 0 only: generate orchestrator output, stop at draft_ready."""
    async with async_session_factory() as session:
        from agent_publisher.extensions.slideshow.service import run_generate_outline
        await run_generate_outline(task_id, article_id, session)


async def _execute_from_draft(
    task_id: int, article_id: int, orchestrator_output: dict
) -> None:
    """Phase 1+2: from confirmed orchestrator output."""
    async with async_session_factory() as session:
        from agent_publisher.extensions.slideshow.service import run_pipeline_from_draft
        await run_pipeline_from_draft(task_id, article_id, orchestrator_output, session)
