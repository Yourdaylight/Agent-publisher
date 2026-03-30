"""Slideshow generation service — v3 chapter-parallel pipeline.

Architecture:
  Phase 0: Orchestrator — single LLM call to split article into chapters
  Phase 1: Parallel chapter writers — N concurrent LLM calls (Semaphore=3)
  Phase 2: Assembly — build HTML files + timeline.json + concat.html player

No Playwright, no ffmpeg, no TTS dependencies.
"""
from __future__ import annotations

import asyncio
import json
import logging
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from agent_publisher.config import settings
from agent_publisher.extensions.slideshow.chapter_builder import (
    build_chapter_html,
    build_concat_html,
    build_timeline_json,
)
from agent_publisher.extensions.slideshow.prompts import (
    ORCHESTRATOR_SYSTEM_PROMPT,
    CHAPTER_WRITER_SYSTEM_PROMPT,
    build_orchestrator_prompt,
    build_chapter_prompt,
)
from agent_publisher.models.article import Article
from agent_publisher.models.task import Task
from agent_publisher.services.llm_service import LLMService

logger = logging.getLogger(__name__)

STORAGE_ROOT = Path("storage/slideshow")


# ---------------------------------------------------------------------------
# Main entry: full chapter pipeline
# ---------------------------------------------------------------------------

async def run_chapter_pipeline(
    task_id: int,
    article_id: int,
    session: AsyncSession,
) -> None:
    """Full pipeline: orchestrator → parallel chapters → assembly."""
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
        # Phase 0: Orchestrator
        orchestrator_output = await _run_orchestrator(article, task, session)

        # Phase 1: Parallel chapters
        chapter_results = await _run_chapters_parallel(
            orchestrator_output, article, task, session
        )

        # Phase 2: Assembly
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        out_dir = STORAGE_ROOT / f"article_{article_id}_{timestamp}"
        result = await _assemble(
            orchestrator_output, chapter_results, out_dir, task, session
        )

        # Done
        task.status = "success"
        task.result = {
            "article_id": article_id,
            **result,
        }
        task.finished_at = datetime.now(timezone.utc)
        await session.commit()
        logger.info(
            "Slideshow chapter pipeline complete: task=%d chapters=%d",
            task_id, result["chapter_count"],
        )

    except Exception as exc:
        logger.exception("Slideshow chapter pipeline failed for task %d", task_id)
        await _fail(task, session, str(exc), article_id)


# ---------------------------------------------------------------------------
# Draft review flow (Phase 0 only → pause → Phase 1+2)
# ---------------------------------------------------------------------------

async def run_generate_outline(
    task_id: int,
    article_id: int,
    session: AsyncSession,
) -> None:
    """Phase 0 only: generate orchestrator output, then pause at draft_ready."""
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
        orchestrator_output = await _run_orchestrator(article, task, session)

        # Store as draft for review
        task.status = "draft_ready"
        task.result = {
            "article_id": article_id,
            "orchestrator_output": orchestrator_output,
            # Legacy compat: also produce a flat slides_draft for old consumers
            "slides_draft": _flatten_orchestrator_to_draft(orchestrator_output),
        }
        await session.commit()
        logger.info(
            "Slideshow orchestrator ready: task=%d chapters=%d",
            task_id, len(orchestrator_output.get("chapters", [])),
        )

    except Exception as exc:
        logger.exception("Slideshow orchestrator failed for task %d", task_id)
        await _fail(task, session, str(exc), article_id)


async def run_pipeline_from_draft(
    task_id: int,
    article_id: int,
    orchestrator_output: dict,
    session: AsyncSession,
) -> None:
    """Phase 1+2: from a confirmed orchestrator output, run parallel chapters + assembly."""
    task = await session.get(Task, task_id)
    if not task:
        return

    task.status = "running"
    await session.commit()

    article = await session.get(Article, article_id)
    if not article:
        await _fail(task, session, f"Article {article_id} not found", article_id)
        return

    try:
        # Phase 1: Parallel chapters
        chapter_results = await _run_chapters_parallel(
            orchestrator_output, article, task, session
        )

        # Phase 2: Assembly
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        out_dir = STORAGE_ROOT / f"article_{article_id}_{timestamp}"
        result = await _assemble(
            orchestrator_output, chapter_results, out_dir, task, session
        )

        # Done
        task.status = "success"
        task.result = {
            "article_id": article_id,
            **result,
        }
        task.finished_at = datetime.now(timezone.utc)
        await session.commit()
        logger.info(
            "Slideshow pipeline from draft complete: task=%d chapters=%d",
            task_id, result["chapter_count"],
        )

    except Exception as exc:
        logger.exception("Slideshow pipeline from draft failed for task %d", task_id)
        await _fail(task, session, str(exc), article_id)


# Legacy compatibility
async def run_pipeline(
    task_id: int,
    article_id: int,
    with_tts: bool,  # ignored, kept for signature compat
    session: AsyncSession,
) -> None:
    """Legacy entry point — delegates to run_chapter_pipeline."""
    await run_chapter_pipeline(task_id, article_id, session)


async def run_pipeline_from_slides(
    task_id: int,
    article_id: int,
    slides: list[dict],
    with_tts: bool,  # ignored
    session: AsyncSession,
) -> None:
    """Legacy entry point for draft confirm — wraps slides into orchestrator format."""
    # Convert flat slides list back to a simple orchestrator output
    orchestrator_output = _slides_to_orchestrator(slides)
    await run_pipeline_from_draft(task_id, article_id, orchestrator_output, session)


# ---------------------------------------------------------------------------
# Phase 0: Orchestrator
# ---------------------------------------------------------------------------

async def _run_orchestrator(
    article: Article,
    task: Task,
    session: AsyncSession,
) -> dict:
    """Single LLM call to split article into chapters."""
    await _record_step(task, session, "orchestrator", "running", {})

    user_prompt = build_orchestrator_prompt(
        title=article.title or "无标题",
        content=article.content or article.html_content or "",
    )
    messages = [
        {"role": "system", "content": ORCHESTRATOR_SYSTEM_PROMPT},
        {"role": "user", "content": user_prompt},
    ]

    raw = await _call_llm(messages)
    result = _parse_json(raw)

    if not isinstance(result, dict) or "chapters" not in result:
        raise ValueError("Orchestrator LLM 返回格式不正确，缺少 chapters 字段")

    chapters = result["chapters"]
    if not isinstance(chapters, list) or len(chapters) == 0:
        raise ValueError("Orchestrator 返回了空的章节列表")

    # Ensure chapter_ids
    for i, ch in enumerate(chapters):
        if "chapter_id" not in ch:
            ch["chapter_id"] = f"ch_{i + 1:02d}"

    await _record_step(task, session, "orchestrator", "success", {
        "chapter_count": len(chapters),
        "total_slides": sum(ch.get("slide_count", 2) for ch in chapters),
    })

    return result


# ---------------------------------------------------------------------------
# Phase 1: Parallel chapter generation
# ---------------------------------------------------------------------------

async def _run_chapters_parallel(
    orchestrator_output: dict,
    article: Article,
    task: Task,
    session: AsyncSession,
) -> list[dict]:
    """Generate slides for each chapter concurrently (Semaphore=3)."""
    chapters = orchestrator_output["chapters"]
    title = orchestrator_output.get("title", "")
    narrative_arc = orchestrator_output.get("narrative_arc", "")
    total = len(chapters)

    semaphore = asyncio.Semaphore(3)
    step_lock = asyncio.Lock()  # Protect task.steps from concurrent mutation
    results: list[dict | None] = [None] * total
    errors: list[str] = []

    async def _generate_one(index: int, chapter: dict) -> None:
        chapter_id = chapter.get("chapter_id", f"ch_{index + 1:02d}")
        step_name = f"chapter_{chapter_id}"

        async with semaphore:
            async with step_lock:
                await _record_step(task, session, step_name, "running", {})
            try:
                prev_title = chapters[index - 1]["title"] if index > 0 else None
                next_title = chapters[index + 1]["title"] if index < total - 1 else None

                user_prompt = build_chapter_prompt(
                    presentation_title=title,
                    chapter=chapter,
                    chapter_index=index + 1,
                    total_chapters=total,
                    prev_title=prev_title,
                    next_title=next_title,
                    narrative_arc=narrative_arc,
                )
                messages = [
                    {"role": "system", "content": CHAPTER_WRITER_SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ]

                raw = await _call_llm(messages)
                slides = _parse_json(raw)

                if not isinstance(slides, list) or len(slides) == 0:
                    raise ValueError(f"Chapter {chapter_id} 返回了空的 slides")

                # Assign slide_ids
                for j, slide in enumerate(slides):
                    if "slide_id" not in slide:
                        slide["slide_id"] = f"{chapter_id}_slide_{j + 1:02d}"
                    if "duration" not in slide:
                        notes = slide.get("notes", "")
                        slide["duration"] = max(len(notes) // 4, 5)

                results[index] = {
                    "chapter_id": chapter_id,
                    "title": chapter.get("title", ""),
                    "purpose": chapter.get("purpose", ""),
                    "slides": slides,
                }
                async with step_lock:
                    await _record_step(task, session, step_name, "success", {
                        "slide_count": len(slides),
                    })

            except Exception as exc:
                logger.error("Chapter %s generation failed: %s", chapter_id, exc)
                errors.append(f"{chapter_id}: {exc}")
                async with step_lock:
                    await _record_step(task, session, step_name, "failed", {
                        "error": str(exc),
                    })

    # Run all chapters concurrently
    tasks = [
        _generate_one(i, ch)
        for i, ch in enumerate(chapters)
    ]
    await asyncio.gather(*tasks, return_exceptions=True)

    # Filter out failed chapters
    successful = [r for r in results if r is not None]

    if not successful:
        raise ValueError(
            f"所有章节生成均失败: {'; '.join(errors)}"
        )

    if errors:
        logger.warning(
            "Some chapters failed (%d/%d): %s",
            len(errors), total, "; ".join(errors),
        )

    return successful


# ---------------------------------------------------------------------------
# Phase 2: Assembly
# ---------------------------------------------------------------------------

async def _assemble(
    orchestrator_output: dict,
    chapter_results: list[dict],
    out_dir: Path,
    task: Task,
    session: AsyncSession,
) -> dict:
    """Write HTML files + timeline.json + concat.html."""
    await _record_step(task, session, "assembly", "running", {})

    chapters_dir = out_dir / "chapters"
    chapters_dir.mkdir(parents=True, exist_ok=True)

    title = orchestrator_output.get("title", "Slideshow")
    theme = orchestrator_output.get("theme", "corporate")
    narrative_arc = orchestrator_output.get("narrative_arc", "")

    # Build chapter HTML files
    chapter_entries = []
    for ch in chapter_results:
        chapter_id = ch["chapter_id"]
        html_filename = f"{chapter_id}.html"
        html_path = chapters_dir / html_filename

        html = build_chapter_html(
            chapter_id=chapter_id,
            slides=ch["slides"],
            theme=theme,
            presentation_title=title,
            chapter_title=ch["title"],
        )
        html_path.write_text(html, encoding="utf-8")

        chapter_entries.append({
            "chapter_id": chapter_id,
            "title": ch["title"],
            "purpose": ch.get("purpose", ""),
            "slides": ch["slides"],
            "slide_count": len(ch["slides"]),
            "html_file": f"chapters/{html_filename}",
        })

    # Build timeline.json
    timeline = build_timeline_json(
        title=title,
        theme=theme,
        narrative_arc=narrative_arc,
        chapters=chapter_entries,
    )
    timeline_path = out_dir / "timeline.json"
    timeline_path.write_text(
        json.dumps(timeline, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    # Build concat.html player
    concat_html = build_concat_html(timeline)
    concat_path = out_dir / "concat.html"
    concat_path.write_text(concat_html, encoding="utf-8")

    await _record_step(task, session, "assembly", "success", {
        "chapter_count": len(chapter_entries),
        "output_dir": str(out_dir),
    })

    return {
        "output_dir": str(out_dir),
        "chapter_count": len(chapter_entries),
        "timeline_path": str(timeline_path),
        "concat_path": str(concat_path),
        "chapters": [
            {
                "chapter_id": ch["chapter_id"],
                "title": ch["title"],
                "slide_count": ch["slide_count"],
                "html_file": ch["html_file"],
            }
            for ch in chapter_entries
        ],
    }


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

async def _call_llm(messages: list[dict]) -> str:
    """Call the default LLM and return raw text."""
    provider = settings.default_llm_provider
    model = settings.default_llm_model
    api_key = settings.default_llm_api_key
    base_url = settings.default_llm_base_url

    return await LLMService.generate(
        provider, model, api_key, messages, base_url=base_url
    )


def _parse_json(raw: str) -> Any:
    """Extract and parse JSON from LLM output (handles ```json blocks)."""
    json_match = re.search(r"```(?:json)?\s*\n?(.*?)```", raw, re.DOTALL)
    json_str = json_match.group(1).strip() if json_match else raw.strip()

    try:
        return json.loads(json_str)
    except json.JSONDecodeError as exc:
        logger.error("Failed to parse LLM JSON: %s\n%s", exc, json_str[:500])
        raise ValueError("LLM 返回的数据格式不正确") from exc


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


def _flatten_orchestrator_to_draft(orchestrator_output: dict) -> list[dict]:
    """Convert orchestrator output to a flat slides-like draft for backward compat."""
    draft = []
    for ch in orchestrator_output.get("chapters", []):
        draft.append({
            "slide_id": ch.get("chapter_id", ""),
            "layout": "title",
            "title": ch.get("title", ""),
            "content": {
                "subtitle": ch.get("purpose", ""),
            },
            "notes": f"章节要点：{'、'.join(ch.get('key_points', []))}",
            "duration": 5,
            "_chapter_spec": ch,  # Preserve full spec for later use
        })
    return draft


def _slides_to_orchestrator(slides: list[dict]) -> dict:
    """Convert a flat slides list (from legacy confirm flow) to orchestrator format."""
    chapters = []
    for i, slide in enumerate(slides):
        spec = slide.get("_chapter_spec")
        if spec:
            chapters.append(spec)
        else:
            chapters.append({
                "chapter_id": f"ch_{i + 1:02d}",
                "title": slide.get("title", f"Section {i + 1}"),
                "purpose": "core",
                "key_points": [],
                "suggested_layouts": [slide.get("layout", "bullets")],
                "content_excerpt": slide.get("notes", ""),
                "slide_count": 2,
            })

    return {
        "title": slides[0].get("title", "Presentation") if slides else "Presentation",
        "theme": "corporate",
        "narrative_arc": "",
        "chapters": chapters,
    }
