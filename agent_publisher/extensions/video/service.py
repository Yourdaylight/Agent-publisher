"""Video generation service — LLM script → edge-tts → Remotion render → MP4.

Pipeline:
  Phase 0: LLM generates video script (scenes JSON)
  Phase 1: Write props JSON + preview HTML
  Phase 1.5: edge-tts TTS for each scene narration → mp3 + subtitle word timestamps
  Phase 2: Run `npx remotion render` to produce MP4
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
from agent_publisher.extensions.video.prompts import SCRIPT_SYSTEM_PROMPT, build_script_prompt
from agent_publisher.models.article import Article
from agent_publisher.models.task import Task
from agent_publisher.services.llm_service import LLMService

logger = logging.getLogger(__name__)

STORAGE_ROOT = Path(__file__).parent.parent.parent.parent / "storage" / "video"
REMOTION_DIR = Path(__file__).parent / "remotion"

# edge-tts voice to use for Chinese narration
TTS_VOICE = "zh-CN-XiaoxiaoNeural"


# ---------------------------------------------------------------------------
# Main entry
# ---------------------------------------------------------------------------


async def run_video_pipeline(
    task_id: int,
    article_id: int,
    session: AsyncSession,
) -> None:
    """Full pipeline: LLM script → Remotion render → MP4."""
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
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        out_dir = STORAGE_ROOT / f"article_{article_id}_{timestamp}"
        out_dir.mkdir(parents=True, exist_ok=True)

        # Phase 0: Generate script
        script = await _generate_script(article, task, session)

        # Phase 1: Write props + preview HTML
        props_path = out_dir / "props.json"
        props_path.write_text(json.dumps(script, ensure_ascii=False, indent=2), encoding="utf-8")

        preview_html = _build_preview_html(script, task_id=task_id)
        preview_path = out_dir / "preview.html"
        preview_path.write_text(preview_html, encoding="utf-8")

        await _record_step(
            task,
            session,
            "props_ready",
            "success",
            {
                "scene_count": len(script.get("scenes", [])),
                "total_duration_s": script.get("total_duration_s", 0),
            },
        )

        # Phase 1.5: edge-tts — generate audio + subtitle timestamps for each scene
        await _generate_tts(script, out_dir, task, session)

        # Phase 2: Render with Remotion
        mp4_path = await _render_remotion(script, out_dir, task, session)

        task.status = "success"
        task.result = {
            "article_id": article_id,
            "output_dir": str(out_dir),
            "props_path": str(props_path),
            "preview_path": str(preview_path),
            "mp4_path": str(mp4_path) if mp4_path else None,
            "scene_count": len(script.get("scenes", [])),
            "total_duration_s": script.get("total_duration_s", 0),
            "title": script.get("title", ""),
        }
        task.finished_at = datetime.now(timezone.utc)
        await session.commit()
        logger.info("Video pipeline complete: task=%d", task_id)

    except Exception as exc:
        logger.exception("Video pipeline failed for task %d", task_id)
        await _fail(task, session, str(exc), article_id)


# ---------------------------------------------------------------------------
# Phase 0: Script generation
# ---------------------------------------------------------------------------


async def _generate_script(article: Article, task: Task, session: AsyncSession) -> dict:
    """Call LLM to generate video script."""
    await _record_step(task, session, "script_generation", "running", {})

    messages = [
        {"role": "system", "content": SCRIPT_SYSTEM_PROMPT},
        {
            "role": "user",
            "content": build_script_prompt(
                title=article.title or "无标题",
                content=article.content or article.html_content or "",
            ),
        },
    ]

    raw = await _call_llm(messages)
    script = _parse_json(raw)

    if not isinstance(script, dict) or "scenes" not in script:
        raise ValueError("LLM 返回的脚本格式不正确")

    scenes = script["scenes"]
    if not isinstance(scenes, list) or len(scenes) == 0:
        raise ValueError("脚本场景列表为空")

    # Normalize scene IDs
    for i, sc in enumerate(scenes):
        if "scene_id" not in sc:
            sc["scene_id"] = f"scene_{i + 1:02d}"

    await _record_step(
        task,
        session,
        "script_generation",
        "success",
        {
            "scene_count": len(scenes),
            "total_duration_s": script.get("total_duration_s", 0),
        },
    )

    return script


# ---------------------------------------------------------------------------
# Phase 1: Build preview HTML (instant preview before MP4 render)
# ---------------------------------------------------------------------------


def _build_preview_html(script: dict, *, task_id: int = 0) -> str:
    """Build a static HTML preview of the video script (no Remotion required)."""
    scenes = script.get("scenes", [])
    title = script.get("title", "Video")
    total_duration = script.get("total_duration_s", 0)

    scenes_html = ""
    for i, sc in enumerate(scenes):
        bg = sc.get("bg_gradient", "linear-gradient(160deg, #0f0c29, #302b63)")
        accent = sc.get("accent_color", "#818cf8")
        headline = sc.get("headline", "")
        subline = sc.get("subline", "")
        icon = sc.get("icon", "🎬")
        visual_desc = sc.get("visual_desc", "")
        body_lines = sc.get("body_lines", [])
        duration = sc.get("duration_s", 6)
        purpose = sc.get("purpose", "core")

        body_html = "".join(
            f'<div style="margin:4px 0;color:#e2e8f0;font-size:15px">{line}</div>'
            for line in body_lines
        )

        scenes_html += f"""
        <div class="scene" style="background:{bg}">
          <div class="scene-num">{i + 1}/{len(scenes)} · {purpose} · {duration}s</div>
          <div class="top-zone">
            <div class="headline" style="color:{accent}">{headline}</div>
            <div class="subline">{subline}</div>
          </div>
          <div class="visual-zone">
            <div class="icon">{icon}</div>
            <div style="color:#94a3b8;font-size:14px;margin-top:8px">{visual_desc}</div>
          </div>
          <div class="bottom-zone">{body_html}</div>
        </div>
        """

    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <title>{title} — 视频预览</title>
  <style>
    * {{ margin:0; padding:0; box-sizing:border-box; }}
    body {{ background:#0a0a0f; font-family:'PingFang SC',system-ui,sans-serif; color:#fff; }}
    .header {{ padding:24px; border-bottom:1px solid #1e293b; display:flex; justify-content:space-between; align-items:center; }}
    .header h1 {{ font-size:20px; font-weight:700; }}
    .meta {{ color:#64748b; font-size:13px; }}
    .scenes {{ display:flex; flex-wrap:wrap; gap:16px; padding:24px; }}
    .scene {{
      width:192px; height:341px; border-radius:16px; overflow:hidden;
      display:flex; flex-direction:column; padding:16px; position:relative;
      box-shadow:0 8px 32px rgba(0,0,0,.5); flex-shrink:0;
    }}
    .scene-num {{ font-size:11px; color:rgba(255,255,255,.5); margin-bottom:8px; }}
    .top-zone {{ flex:0 0 30%; display:flex; flex-direction:column; justify-content:center; }}
    .headline {{ font-size:17px; font-weight:800; line-height:1.3; margin-bottom:6px; }}
    .subline {{ font-size:12px; color:rgba(255,255,255,.7); line-height:1.4; }}
    .visual-zone {{ flex:0 0 35%; display:flex; flex-direction:column; align-items:center; justify-content:center; }}
    .icon {{ font-size:48px; }}
    .bottom-zone {{ flex:0 0 30%; display:flex; flex-direction:column; justify-content:flex-end; }}
    .download {{ padding:16px 24px; border-top:1px solid #1e293b; display:flex; gap:12px; align-items:center; }}
    .btn {{ padding:8px 16px; border-radius:8px; border:none; cursor:pointer; font-size:14px; font-weight:600; }}
    .btn-primary {{ background:#6366f1; color:#fff; }}
    .btn-outline {{ background:transparent; color:#94a3b8; border:1px solid #334155; }}
  </style>
</head>
<body>
  <div class="header">
    <div>
      <h1>🎬 {title}</h1>
      <div class="meta">{len(scenes)} 个场景 · 约 {total_duration} 秒</div>
    </div>
    <div class="meta">Task #{task_id} · 脚本预览</div>
  </div>
  <div class="scenes">{scenes_html}</div>
  <div class="download">
    <span style="color:#64748b;font-size:13px">MP4 渲染需要 Node.js + Remotion 环境</span>
  </div>
</body>
</html>"""


# ---------------------------------------------------------------------------
# Phase 1.5: edge-tts TTS + subtitle generation
# ---------------------------------------------------------------------------


async def _generate_tts(
    script: dict,
    out_dir: Path,
    task: Task,
    session: AsyncSession,
) -> None:
    """Generate TTS audio (MP3) and word-level subtitle timestamps for each scene.

    Mutates script['scenes'] in-place, adding:
      - audio_url: staticFile path relative to remotion project public/ dir
      - subtitles: list of {text, start_ms, end_ms}

    Audio files are written to out_dir and symlinked into the Remotion public/ dir.
    """
    try:
        import edge_tts  # noqa: F401 — confirm available
    except ImportError:
        logger.warning("edge-tts not installed — skipping TTS (pip install edge-tts)")
        await _record_step(
            task, session, "tts_generate", "skipped", {"reason": "edge-tts not installed"}
        )
        return

    import edge_tts as _edge_tts

    await _record_step(task, session, "tts_generate", "running", {})

    # Remotion staticFile() resolves from the remotion/public/ directory
    public_dir = REMOTION_DIR / "public"
    public_dir.mkdir(exist_ok=True)

    # Create a per-task subdirectory inside public/ using symlink to out_dir
    # Remotion needs files relative to its own project root.
    task_id_str = out_dir.name  # e.g. article_13_20260406214957
    public_task_dir = public_dir / task_id_str
    if not public_task_dir.exists():
        # Symlink public/<task_dir> → actual out_dir so staticFile works
        public_task_dir.symlink_to(out_dir)

    scenes = script.get("scenes", [])
    total_audio_ms = 0
    success_count = 0

    for scene in scenes:
        scene_id = scene.get("scene_id", "unknown")
        narration = scene.get("narration", "").strip()
        if not narration:
            continue

        audio_filename = f"{scene_id}.mp3"
        audio_path = out_dir / audio_filename

        # Collect word boundaries
        words: list[dict] = []

        try:
            communicate = _edge_tts.Communicate(narration, TTS_VOICE)
            audio_chunks: list[bytes] = []

            async for event in communicate.stream():
                if event["type"] == "audio":
                    audio_chunks.append(event["data"])
                elif event["type"] in ("WordBoundary", "SentenceBoundary"):
                    words.append(
                        {
                            "text": event["text"],
                            "start_ms": event["offset"] // 10000,
                            "end_ms": (event["offset"] + event["duration"]) // 10000,
                        }
                    )

            audio_path.write_bytes(b"".join(audio_chunks))

            # Duration = last word end_ms (fallback: scene duration_s)
            duration_ms = words[-1]["end_ms"] if words else int(scene.get("duration_s", 5) * 1000)
            total_audio_ms += duration_ms

            # Inject into scene dict
            # Remotion staticFile('article_13_xxx/scene_01.mp3') resolves to
            # <remotion_dir>/public/article_13_xxx/scene_01.mp3
            scene["audio_url"] = f"{task_id_str}/{audio_filename}"
            scene["subtitles"] = words
            success_count += 1

            logger.info(
                "TTS OK: scene=%s words=%d duration=%.1fs", scene_id, len(words), duration_ms / 1000
            )

        except Exception as e:
            logger.warning("TTS failed for scene %s: %s", scene_id, e)
            # Non-fatal: continue without audio for this scene

    # Re-write props.json with updated audio_url / subtitles
    props_path = out_dir / "props.json"
    props_path.write_text(json.dumps(script, ensure_ascii=False, indent=2), encoding="utf-8")

    await _record_step(
        task,
        session,
        "tts_generate",
        "success",
        {
            "scenes_with_audio": success_count,
            "total_scenes": len(scenes),
            "total_audio_s": round(total_audio_ms / 1000, 1),
        },
    )
    logger.info(
        "TTS complete: %d/%d scenes, total %.1fs", success_count, len(scenes), total_audio_ms / 1000
    )


def staticFile(relative_path: str) -> str:
    """Unused — kept for reference. Remotion resolves staticFile() paths
    relative to <remotion_dir>/public/ at render time."""
    return relative_path


# ---------------------------------------------------------------------------
# Phase 2: Remotion render
# ---------------------------------------------------------------------------


async def _render_remotion(
    script: dict,
    out_dir: Path,
    task: Task,
    session: AsyncSession,
) -> Path | None:
    """Run Remotion to render the MP4. Returns mp4 path or None if unavailable."""
    await _record_step(task, session, "remotion_render", "running", {})

    # Check that Remotion project exists
    if not (REMOTION_DIR / "package.json").exists():
        logger.warning("Remotion project not found at %s — skipping MP4 render", REMOTION_DIR)
        await _record_step(
            task,
            session,
            "remotion_render",
            "skipped",
            {
                "reason": "Remotion project not installed. Run: cd agent_publisher/extensions/video/remotion && npm install"
            },
        )
        return None

    mp4_path = out_dir / "output.mp4"
    props_path = out_dir / "props.json"

    cmd = [
        "npx",
        "remotion",
        "render",
        "VideoComposition",
        str(mp4_path),
        "--props",
        str(props_path),
        "--log",
        "error",
    ]

    logger.info("Running Remotion render: %s", " ".join(cmd))

    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            cwd=str(REMOTION_DIR),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=300)

        if proc.returncode != 0:
            err_msg = stderr.decode("utf-8", errors="replace")[-1000:]
            logger.error("Remotion render failed: %s", err_msg)
            await _record_step(task, session, "remotion_render", "failed", {"error": err_msg})
            raise RuntimeError(f"Remotion render failed: {err_msg}")

        await _record_step(
            task,
            session,
            "remotion_render",
            "success",
            {
                "mp4_path": str(mp4_path),
                "file_size_mb": round(mp4_path.stat().st_size / 1024 / 1024, 2)
                if mp4_path.exists()
                else 0,
            },
        )
        return mp4_path

    except asyncio.TimeoutError:
        await _record_step(
            task, session, "remotion_render", "failed", {"error": "Render timeout (300s)"}
        )
        raise RuntimeError("Remotion render timed out after 300 seconds")


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


async def _call_llm(messages: list[dict]) -> str:
    provider = settings.default_llm_provider
    model = settings.default_llm_model
    api_key = settings.default_llm_api_key
    base_url = settings.default_llm_base_url
    return await LLMService.generate(provider, model, api_key, messages, base_url=base_url)


def _parse_json(raw: str) -> Any:
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
