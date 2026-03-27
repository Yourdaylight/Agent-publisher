"""Slideshow generation service — the 5-step pipeline."""
from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from agent_publisher.config import settings
from agent_publisher.extensions.slideshow.chart_builder import build_echarts_option  # noqa: F401
from agent_publisher.extensions.slideshow.prompts import (
    SLIDESHOW_SYSTEM_PROMPT,
    SLIDESHOW_USER_PROMPT,
)
from agent_publisher.extensions.slideshow.reveal_builder import build_reveal_html
from agent_publisher.extensions.slideshow.tts_service import TTSService
from agent_publisher.extensions.slideshow.video_exporter import VideoExporter
from agent_publisher.models.article import Article
from agent_publisher.models.task import Task
from agent_publisher.services.llm_service import LLMService

logger = logging.getLogger(__name__)

STORAGE_ROOT = Path("storage/slideshow")


async def run_pipeline(
    task_id: int,
    article_id: int,
    with_tts: bool,
    session: AsyncSession,
) -> None:
    """Execute the full slideshow generation pipeline.

    Steps:
        1. LLM → slide outline JSON
        2. (optional) TTS → narration audio + subtitles
        3. Build reveal.js HTML (preview + video variants)
        4. Playwright → record video
        5. ffmpeg → merge audio + video
    """
    task = await session.get(Task, task_id)
    if not task:
        logger.error("Slideshow task %d not found", task_id)
        return

    task.status = "running"
    task.started_at = datetime.now(timezone.utc)
    task.steps = []
    await session.commit()

    article = await session.get(Article, article_id)
    if not article:
        task.status = "failed"
        task.result = {"error": f"Article {article_id} not found"}
        task.finished_at = datetime.now(timezone.utc)
        await session.commit()
        return

    # Prepare output directory
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    out_dir = STORAGE_ROOT / f"article_{article_id}_{timestamp}"
    out_dir.mkdir(parents=True, exist_ok=True)

    try:
        # ── Step 1: LLM generate slide outline ──────────────────────
        await _record_step(task, session, "llm_outline", "running", {})

        slides = await _generate_outline(article)

        await _record_step(task, session, "llm_outline", "success", {"slide_count": len(slides)})

        # ── Step 2: TTS narration (optional) ────────────────────────
        tts_result: dict[str, Any] | None = None
        if with_tts:
            await _record_step(task, session, "tts_generate", "running", {})
            tts_svc = TTSService()
            tts_result = await tts_svc.generate(slides, str(out_dir))

            # Update slide durations based on actual TTS audio lengths
            for idx, dur in tts_result.get("slide_durations", {}).items():
                if isinstance(idx, int) and idx < len(slides):
                    slides[idx]["duration"] = max(dur, 2)  # minimum 2 seconds

            await _record_step(task, session, "tts_generate", "success", {
                "duration_ms": tts_result["duration_ms"],
            })

        # ── Step 3: Build reveal.js HTML ────────────────────────────
        await _record_step(task, session, "build_html", "running", {})

        preview_html = build_reveal_html(slides, preview_mode=True)
        preview_path = out_dir / "preview.html"
        preview_path.write_text(preview_html, encoding="utf-8")

        video_html = build_reveal_html(slides, preview_mode=False)
        video_html_path = out_dir / "video_source.html"
        video_html_path.write_text(video_html, encoding="utf-8")

        await _record_step(task, session, "build_html", "success", {})

        # ── Step 4 & 5: Video recording + merge ────────────────────
        await _record_step(task, session, "video_export", "running", {})

        exporter = VideoExporter()
        # Prefer mp4 (requires system ffmpeg with libx264); exporter auto-falls back to webm
        video_path_requested = str(out_dir / "video.mp4")
        tts_audio = tts_result["audio_path"] if tts_result else None
        actual_video_path = await exporter.export(str(video_html_path), video_path_requested, tts_audio)

        await _record_step(task, session, "video_export", "success", {})

        # ── Done ────────────────────────────────────────────────────
        result: dict[str, Any] = {
            "article_id": article_id,
            "preview_html_path": str(preview_path),
            "video_path": actual_video_path,
        }
        if tts_result:
            result["narration_path"] = tts_result["audio_path"]
            result["srt_path"] = tts_result["srt_path"]

        task.status = "success"
        task.result = result
        task.finished_at = datetime.now(timezone.utc)
        await session.commit()

    except Exception as exc:
        logger.exception("Slideshow pipeline failed for task %d", task_id)
        task.status = "failed"
        task.result = {"error": str(exc), "article_id": article_id}
        task.finished_at = datetime.now(timezone.utc)
        await session.commit()


# ------------------------------------------------------------------
# Internal helpers
# ------------------------------------------------------------------


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


async def _generate_outline(article: Article) -> list[dict]:
    """Ask the LLM to produce slide JSON from the article content."""
    messages = [
        {"role": "system", "content": SLIDESHOW_SYSTEM_PROMPT},
        {
            "role": "user",
            "content": SLIDESHOW_USER_PROMPT.format(
                title=article.title or "无标题",
                content=article.content or article.html_content or "",
            ),
        },
    ]

    # Resolve LLM profile
    provider = settings.default_llm_provider
    model = settings.default_llm_model
    api_key = settings.default_llm_api_key
    base_url = settings.default_llm_base_url

    raw = await LLMService.generate(provider, model, api_key, messages, base_url=base_url)

    # Parse JSON from the response (handle markdown code blocks)
    json_match = re.search(r"```(?:json)?\s*\n?(.*?)```", raw, re.DOTALL)
    json_str = json_match.group(1).strip() if json_match else raw.strip()

    try:
        slides = json.loads(json_str)
    except json.JSONDecodeError as exc:
        logger.error("Failed to parse LLM slide JSON: %s\n%s", exc, json_str[:500])
        raise ValueError("LLM 返回的幻灯片数据格式不正确") from exc

    if not isinstance(slides, list) or len(slides) == 0:
        raise ValueError("LLM 返回了空的幻灯片数据")

    return slides
