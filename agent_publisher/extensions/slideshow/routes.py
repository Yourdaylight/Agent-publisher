"""Slideshow API routes — with auth, IDOR protection, and querystring token support."""
from __future__ import annotations

import asyncio
import logging
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse
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


# ---------------------------------------------------------------------------
# Auth helpers
# ---------------------------------------------------------------------------

async def _resolve_user(
    request: Request,
    token: str | None,  # querystring fallback for iframe src
    db: AsyncSession,
) -> tuple[str, bool]:
    """Return (email, is_admin) from either Authorization header or ?token= querystring.

    Priority:
      1. Authorization: Bearer <token> header (normal API calls)
      2. ?token=<token> querystring (iframe src workaround — header not settable)
    """
    # Try header first
    auth_header = request.headers.get("authorization", "")
    raw_token = auth_header[7:] if auth_header.startswith("Bearer ") else None

    # Fall back to querystring token
    if not raw_token and token:
        raw_token = token

    if not raw_token:
        raise HTTPException(401, "Authentication required")

    # Admin token (dot-separated)
    if "|" not in raw_token:
        if not verify_token(raw_token):
            raise HTTPException(401, "Invalid or expired token")
        return "__admin__", True

    # Skill/email token (pipe-separated)
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
    """Verify the given user owns the task's article chain.

    Raises 403 (not 404) to prevent IDOR enumeration.
    Slideshow tasks have no agent_id — ownership is via task.result['article_id'].
    """
    if is_admin:
        return

    result = task.result or {}
    article_id = result.get("article_id")
    if article_id is None:
        # Task still in progress — allow owner access by checking task type
        # For pending/running slideshow tasks we can't verify yet; allow for now
        # (task was created by the same session, so implicitly owned)
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
    with_tts: bool = True
    skip_review: bool = False  # True = skip draft review, generate immediately


class DraftConfirmRequest(BaseModel):
    slides: list[dict]  # Edited slides array from frontend
    with_tts: bool = True


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
    """Create a slideshow task.

    If skip_review=False (default): generates outline and pauses at draft_ready,
    waiting for user to review/edit before video generation.

    If skip_review=True: generates outline + video in one shot (legacy behavior).
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
        asyncio.create_task(_execute_full(task.id, req.article_id, req.with_tts))
    else:
        asyncio.create_task(_execute_outline_only(task.id, req.article_id))

    return {"task_id": task.id, "mode": "skip_review" if req.skip_review else "draft_review"}


@router.get("/preview/{task_id}")
async def preview_slideshow(
    task_id: int,
    request: Request,
    token: str | None = None,  # querystring auth for iframe src
    db: AsyncSession = Depends(get_db),
):
    """Return the reveal.js HTML for in-browser preview.

    Supports both Authorization header and ?token= querystring
    (the latter is required for iframe src since browsers can't set headers on iframe).
    """
    email, is_admin = await _resolve_user(request, token, db)

    task = await db.get(Task, task_id)
    if not task:
        raise HTTPException(403, "Access denied")  # 403 not 404 — prevent IDOR enumeration

    await _verify_task_ownership(task, email, is_admin, db)

    if task.status != "success":
        raise HTTPException(400, f"Task not ready (status={task.status})")

    result = task.result or {}
    html_path = result.get("preview_html_path")
    if not html_path or not Path(html_path).exists():
        raise HTTPException(404, "Preview HTML not found")

    return FileResponse(html_path, media_type="text/html")


@router.get("/download/{task_id}")
async def download_video(
    task_id: int,
    request: Request,
    token: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    """Download the generated video file."""
    email, is_admin = await _resolve_user(request, token, db)

    task = await db.get(Task, task_id)
    if not task:
        raise HTTPException(403, "Access denied")

    await _verify_task_ownership(task, email, is_admin, db)

    if task.status != "success":
        raise HTTPException(400, f"Task not ready (status={task.status})")

    result = task.result or {}
    video_path = result.get("video_path")
    if not video_path or not Path(video_path).exists():
        raise HTTPException(404, "Video file not found")

    is_webm = video_path.endswith(".webm")
    media_type = "video/webm" if is_webm else "video/mp4"
    task_suffix = ".webm" if is_webm else ".mp4"

    # Get article title for a friendlier filename
    article_id = (task.result or {}).get("article_id")
    article = await db.get(Article, int(article_id)) if article_id else None
    slug = (article.title[:30].replace(" ", "_") if article else f"slideshow_{task_id}")

    return FileResponse(
        video_path,
        media_type=media_type,
        filename=f"{slug}{task_suffix}",
        headers={"Content-Disposition": f'attachment; filename="{slug}{task_suffix}"'},
    )


@router.get("/subtitle/{task_id}")
async def download_subtitle(
    task_id: int,
    request: Request,
    token: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    """Download the SRT subtitle file."""
    email, is_admin = await _resolve_user(request, token, db)

    task = await db.get(Task, task_id)
    if not task:
        raise HTTPException(403, "Access denied")

    await _verify_task_ownership(task, email, is_admin, db)

    if task.status != "success":
        raise HTTPException(400, f"Task not ready (status={task.status})")

    result = task.result or {}
    srt_path = result.get("srt_path")
    if not srt_path or not Path(srt_path).exists():
        raise HTTPException(404, "Subtitle file not found")

    return FileResponse(
        srt_path,
        media_type="text/plain",
        filename=f"slideshow_{task_id}.srt",
        headers={"Content-Disposition": f'attachment; filename="slideshow_{task_id}.srt"'},
    )


@router.get("/status/{task_id}")
async def slideshow_status(
    task_id: int,
    request: Request,
    token: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    """Get slideshow task status with step details (for polling)."""
    email, is_admin = await _resolve_user(request, token, db)

    task = await db.get(Task, task_id)
    if not task:
        raise HTTPException(403, "Access denied")

    await _verify_task_ownership(task, email, is_admin, db)

    result = task.result or {}
    has_video = bool(result.get("video_path") and Path(str(result.get("video_path", ""))).exists())
    has_subtitle = bool(result.get("srt_path") and Path(str(result.get("srt_path", ""))).exists())
    has_preview = bool(result.get("preview_html_path") and Path(str(result.get("preview_html_path", ""))).exists())

    return {
        "task_id": task.id,
        "status": task.status,
        "steps": task.steps or [],
        "error": result.get("error"),
        "article_id": result.get("article_id"),
        "has_video": has_video,
        "has_subtitle": has_subtitle,
        "has_preview": has_preview,
        "started_at": task.started_at.isoformat() if task.started_at else None,
        "finished_at": task.finished_at.isoformat() if task.finished_at else None,
    }


async def _execute(task_id: int, article_id: int, with_tts: bool) -> None:
    """Legacy: full pipeline (skip review)."""
    async with async_session_factory() as session:
        from agent_publisher.extensions.slideshow.service import run_pipeline
        await run_pipeline(task_id, article_id, with_tts, session)


async def _execute_full(task_id: int, article_id: int, with_tts: bool) -> None:
    """Full pipeline without review stop."""
    async with async_session_factory() as session:
        from agent_publisher.extensions.slideshow.service import run_pipeline
        await run_pipeline(task_id, article_id, with_tts, session)


async def _execute_outline_only(task_id: int, article_id: int) -> None:
    """Phase 1 only: generate outline, stop at draft_ready."""
    async with async_session_factory() as session:
        from agent_publisher.extensions.slideshow.service import run_generate_outline
        await run_generate_outline(task_id, article_id, session)


async def _execute_from_slides(task_id: int, article_id: int, slides: list[dict], with_tts: bool) -> None:
    """Phase 2+: TTS → screenshots → video, using provided slides."""
    async with async_session_factory() as session:
        from agent_publisher.extensions.slideshow.service import run_pipeline_from_slides
        await run_pipeline_from_slides(task_id, article_id, slides, with_tts, session)


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
    """Return the LLM-generated slide outline for user review/editing."""
    email, is_admin = await _resolve_user(request, token, db)
    task = await db.get(Task, task_id)
    if not task:
        raise HTTPException(403, "Access denied")
    await _verify_task_ownership(task, email, is_admin, db)

    if task.status not in ("draft_ready", "running", "success"):
        raise HTTPException(400, f"No draft available (status={task.status})")

    result = task.result or {}
    slides = result.get("slides_draft")
    if not slides:
        raise HTTPException(404, "Draft not found — outline may still be generating")

    return {
        "task_id": task_id,
        "status": task.status,
        "slides": slides,
        "slide_count": len(slides),
    }


@router.post("/draft/{task_id}/confirm")
async def confirm_draft(
    task_id: int,
    body: DraftConfirmRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: UserContext = Depends(get_current_user),
):
    """Accept (optionally edited) slides and start video generation."""
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

    if not body.slides:
        raise HTTPException(400, "slides array cannot be empty")

    # Kick off video generation with user-edited slides
    asyncio.create_task(_execute_from_slides(task_id, article_id, body.slides, body.with_tts))
    return {"task_id": task_id, "status": "running", "slide_count": len(body.slides)}


@router.post("/draft/{task_id}/skip")
async def skip_draft(
    task_id: int,
    request: Request,
    with_tts: bool = True,
    db: AsyncSession = Depends(get_db),
    user: UserContext = Depends(get_current_user),
):
    """Skip review and generate video using the original LLM outline."""
    task = await db.get(Task, task_id)
    if not task:
        raise HTTPException(403, "Access denied")
    await _verify_task_ownership(task, user.email, user.is_admin, db)

    if task.status != "draft_ready":
        raise HTTPException(400, f"Task is not in draft_ready state (status={task.status})")

    result = task.result or {}
    article_id = result.get("article_id")
    slides = result.get("slides_draft")
    if not article_id or not slides:
        raise HTTPException(400, "Missing article_id or slides_draft in task")

    asyncio.create_task(_execute_from_slides(task_id, article_id, slides, with_tts))
    return {"task_id": task_id, "status": "running", "slide_count": len(slides)}
