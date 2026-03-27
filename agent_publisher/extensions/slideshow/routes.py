"""Slideshow API routes."""
from __future__ import annotations

import asyncio
import logging
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from agent_publisher.api.deps import get_db
from agent_publisher.database import async_session_factory
from agent_publisher.models.task import Task
from agent_publisher.services.task_service import TaskService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/extensions/slideshow", tags=["slideshow"])


class SlideshowRequest(BaseModel):
    article_id: int
    with_tts: bool = True


@router.post("/generate")
async def generate_slideshow(req: SlideshowRequest, db: AsyncSession = Depends(get_db)):
    """Create a slideshow generation task (runs in background)."""
    task_svc = TaskService(db)
    task = await task_svc.create_task(None, "slideshow_generate")

    # Fire background pipeline
    asyncio.create_task(_execute(task.id, req.article_id, req.with_tts))

    return {"task_id": task.id}


@router.get("/preview/{task_id}")
async def preview_slideshow(task_id: int, db: AsyncSession = Depends(get_db)):
    """Return the reveal.js HTML for in-browser preview."""
    task = await db.get(Task, task_id)
    if not task:
        raise HTTPException(404, "Task not found")
    if task.status != "success":
        raise HTTPException(400, f"Task not ready (status={task.status})")

    result = task.result or {}
    html_path = result.get("preview_html_path")
    if not html_path or not Path(html_path).exists():
        raise HTTPException(404, "Preview HTML not found")

    return FileResponse(html_path, media_type="text/html")


@router.get("/download/{task_id}")
async def download_video(task_id: int, db: AsyncSession = Depends(get_db)):
    """Download the generated mp4 video."""
    task = await db.get(Task, task_id)
    if not task:
        raise HTTPException(404, "Task not found")
    if task.status != "success":
        raise HTTPException(400, f"Task not ready (status={task.status})")

    result = task.result or {}
    video_path = result.get("video_path")
    if not video_path or not Path(video_path).exists():
        raise HTTPException(404, "Video file not found")

    return FileResponse(
        video_path,
        media_type="video/mp4",
        filename=f"slideshow_{task_id}.mp4",
    )


@router.get("/subtitle/{task_id}")
async def download_subtitle(task_id: int, db: AsyncSession = Depends(get_db)):
    """Download the SRT subtitle file."""
    task = await db.get(Task, task_id)
    if not task:
        raise HTTPException(404, "Task not found")
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
    )


async def _execute(task_id: int, article_id: int, with_tts: bool) -> None:
    """Background coroutine that runs the slideshow pipeline."""
    async with async_session_factory() as session:
        from agent_publisher.extensions.slideshow.service import run_pipeline

        await run_pipeline(task_id, article_id, with_tts, session)
