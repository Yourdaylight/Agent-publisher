"""Slideshow generation service — v2 pipeline with draft review step."""
from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from agent_publisher.config import settings
from agent_publisher.extensions.slideshow.prompts import (
    SLIDESHOW_SYSTEM_PROMPT,
    build_user_prompt,
)
from agent_publisher.extensions.slideshow.tts_service import TTSService
from agent_publisher.extensions.slideshow.video_exporter import (
    screenshot_slides,
    compose_video,
    _find_ffmpeg,
)
from agent_publisher.models.article import Article
from agent_publisher.models.task import Task
from agent_publisher.services.llm_service import LLMService

logger = logging.getLogger(__name__)

STORAGE_ROOT = Path("storage/slideshow")


# ---------------------------------------------------------------------------
# Phase 1: Generate slide outline (stops at draft_ready)
# ---------------------------------------------------------------------------

async def run_generate_outline(
    task_id: int,
    article_id: int,
    session: AsyncSession,
) -> None:
    """Step 1 only: generate LLM outline, then wait in draft_ready state.

    Frontend can GET /draft/{task_id} to review & edit slides,
    then POST /draft/{task_id}/confirm or /skip to proceed.
    """
    task = await session.get(Task, task_id)
    if not task:
        return

    task.status = "running"
    task.started_at = datetime.now(timezone.utc)
    task.steps = []
    await session.commit()

    article = await session.get(Article, article_id)
    if not article:
        await _fail(task, session, f"Article {article_id} not found", article_id)
        return

    try:
        await _record_step(task, session, "llm_outline", "running", {})
        slides = await _generate_outline(article)
        await _record_step(task, session, "llm_outline", "success", {"slide_count": len(slides)})

        task.status = "draft_ready"
        task.result = {
            "article_id": article_id,
            "slides_draft": slides,
        }
        await session.commit()
        logger.info("Slideshow outline ready: task=%d slides=%d", task_id, len(slides))

    except Exception as exc:
        logger.exception("Slideshow outline generation failed for task %d", task_id)
        await _fail(task, session, str(exc), article_id)


# ---------------------------------------------------------------------------
# Phase 2: Produce video from slides
# ---------------------------------------------------------------------------

async def run_pipeline_from_slides(
    task_id: int,
    article_id: int,
    slides: list[dict],
    with_tts: bool,
    session: AsyncSession,
) -> None:
    """TTS → screenshots → video composition.

    Called after user confirms (or skips) the draft outline.
    """
    task = await session.get(Task, task_id)
    if not task:
        return

    task.status = "running"
    await session.commit()

    article = await session.get(Article, article_id)
    if not article:
        await _fail(task, session, f"Article {article_id} not found", article_id)
        return

    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    out_dir = STORAGE_ROOT / f"article_{article_id}_{timestamp}"
    out_dir.mkdir(parents=True, exist_ok=True)

    try:
        # ── TTS narration ────────────────────────────────────────────
        tts_result: dict[str, Any] | None = None
        if with_tts:
            await _record_step(task, session, "tts_generate", "running", {})
            tts_svc = TTSService()
            tts_result = await tts_svc.generate(slides, str(out_dir))

            for idx, dur in tts_result.get("slide_durations", {}).items():
                if isinstance(idx, int) and idx < len(slides):
                    slides[idx]["duration"] = max(float(dur), 2.0)

            await _record_step(task, session, "tts_generate", "success", {
                "duration_ms": tts_result["duration_ms"],
            })

        # ── Screenshot each slide ────────────────────────────────────
        await _record_step(task, session, "screenshot_slides", "running", {})
        frame_list = await screenshot_slides(slides, out_dir)
        await _record_step(task, session, "screenshot_slides", "success", {
            "frame_count": len(frame_list),
        })

        # ── Compose video ────────────────────────────────────────────
        await _record_step(task, session, "video_export", "running", {})

        ffmpeg_bin = _find_ffmpeg()
        audio_path = tts_result["audio_path"] if tts_result else None
        srt_path = tts_result["srt_path"] if tts_result else None

        video_path = await compose_video(
            frames=frame_list,
            output_path=str(out_dir / "video.mp4"),
            audio_path=audio_path,
            srt_path=srt_path,
            ffmpeg_bin=ffmpeg_bin,
        )

        await _record_step(task, session, "video_export", "success", {})

        # ── Preview HTML (reveal.js) ─────────────────────────────────
        from agent_publisher.extensions.slideshow.reveal_builder import build_reveal_html
        preview_html = build_reveal_html(slides, preview_mode=True)
        preview_path = out_dir / "preview.html"
        preview_path.write_text(preview_html, encoding="utf-8")

        # ── Done ─────────────────────────────────────────────────────
        result: dict[str, Any] = {
            "article_id": article_id,
            "preview_html_path": str(preview_path),
            "video_path": video_path,
            "slide_count": len(slides),
        }
        if tts_result:
            result["narration_path"] = tts_result["audio_path"]
            result["srt_path"] = tts_result["srt_path"]

        task.status = "success"
        task.result = result
        task.finished_at = datetime.now(timezone.utc)
        await session.commit()
        logger.info("Slideshow video ready: task=%d path=%s", task_id, video_path)

    except Exception as exc:
        logger.exception("Slideshow video generation failed for task %d", task_id)
        await _fail(task, session, str(exc), article_id)


# ---------------------------------------------------------------------------
# Full pipeline (skips draft review)
# ---------------------------------------------------------------------------

async def run_pipeline(
    task_id: int,
    article_id: int,
    with_tts: bool,
    session: AsyncSession,
) -> None:
    """Full pipeline: outline → skip review → TTS → screenshots → video."""
    task = await session.get(Task, task_id)
    if not task:
        return

    task.status = "running"
    task.started_at = datetime.now(timezone.utc)
    task.steps = []
    await session.commit()

    article = await session.get(Article, article_id)
    if not article:
        await _fail(task, session, f"Article {article_id} not found", article_id)
        return

    try:
        await _record_step(task, session, "llm_outline", "running", {})
        slides = await _generate_outline(article)
        await _record_step(task, session, "llm_outline", "success", {"slide_count": len(slides)})
    except Exception as exc:
        logger.exception("Slideshow outline failed for task %d", task_id)
        await _fail(task, session, str(exc), article_id)
        return

    await run_pipeline_from_slides(task_id, article_id, slides, with_tts, session)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

async def _record_step(
    task: Task, session: AsyncSession, name: str, status: str, output: dict
) -> None:
    step = {
        "name": name,
        "status": status,
        "finished_at": datetime.now(timezone.utc).isoformat(),
        "output": output,
    }
    task.steps = [*(task.steps or []), step]
    await session.commit()


async def _fail(task: Task, session: AsyncSession, error: str, article_id: int) -> None:
    task.status = "failed"
    task.result = {"error": error, "article_id": article_id}
    task.finished_at = datetime.now(timezone.utc)
    await session.commit()


async def _generate_outline(article: Article) -> list[dict]:
    """Ask the LLM to produce slide JSON from the article content."""
    user_prompt = build_user_prompt(
        title=article.title or "无标题",
        content=article.content or article.html_content or "",
    )
    messages = [
        {"role": "system", "content": SLIDESHOW_SYSTEM_PROMPT},
        {"role": "user", "content": user_prompt},
    ]

    provider = settings.default_llm_provider
    model = settings.default_llm_model
    api_key = settings.default_llm_api_key
    base_url = settings.default_llm_base_url

    raw = await LLMService.generate(provider, model, api_key, messages, base_url=base_url)

    json_match = re.search(r"```(?:json)?\s*\n?(.*?)```", raw, re.DOTALL)
    json_str = json_match.group(1).strip() if json_match else raw.strip()

    try:
        slides = json.loads(json_str)
    except json.JSONDecodeError as exc:
        logger.error("Failed to parse LLM slide JSON: %s\n%s", exc, json_str[:500])
        raise ValueError("LLM 返回的幻灯片数据格式不正确") from exc

    if not isinstance(slides, list) or len(slides) == 0:
        raise ValueError("LLM 返回了空的幻灯片数据")

    for i, slide in enumerate(slides):
        if "slide_id" not in slide:
            slide["slide_id"] = f"slide_{i + 1:02d}"
        if "duration" not in slide:
            notes = slide.get("notes", "")
            slide["duration"] = max(len(notes) // 4, 5)

    return slides
