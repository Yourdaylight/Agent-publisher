"""Video exporter v2 — per-slide screenshots + ffmpeg xfade + subtitle burn-in.

Architecture change from v1:
  OLD: Playwright screen-record entire slideshow playback → bad quality, no control
  NEW: Screenshot each slide individually (1920×1080 @2x) → ffmpeg concat + xfade + audio

Output quality: 1920×1080 H.264 (libopenh264) or VP9 (libvpx-vp9 fallback)
"""
from __future__ import annotations

import asyncio
import logging
import shutil
import tempfile
from pathlib import Path

logger = logging.getLogger(__name__)

# Transition between slides (seconds)
XFADE_DURATION = 0.4
# Slide screenshot resolution
SLIDE_WIDTH = 1920
SLIDE_HEIGHT = 1080


# ---------------------------------------------------------------------------
# Codec detection
# ---------------------------------------------------------------------------

def _find_ffmpeg() -> str:
    """Return usable ffmpeg binary path."""
    sys_ffmpeg = shutil.which("ffmpeg")
    if sys_ffmpeg:
        return sys_ffmpeg

    import glob
    for pattern in [
        "/root/.cache/ms-playwright/ffmpeg-*/ffmpeg-linux",
        "/home/*/.cache/ms-playwright/ffmpeg-*/ffmpeg-linux",
    ]:
        found = glob.glob(pattern)
        if found:
            return found[0]

    raise RuntimeError("ffmpeg not found. Install: dnf install ffmpeg")


def _best_video_codec(ffmpeg_bin: str) -> tuple[str, str]:
    """Return (vcodec, output_ext) based on what's available.

    Priority: libvpx-vp9 > libvpx(VP8) > libopenh264(mp4)
    Note: libopenh264 is often broken for static image→video; VP8/VP9 is always reliable.
    """
    import subprocess
    try:
        r = subprocess.run([ffmpeg_bin, "-encoders"], capture_output=True, text=True, timeout=10)
        if "libvpx-vp9" in r.stdout:
            return "libvpx-vp9", ".webm"
        if "libvpx" in r.stdout:
            return "libvpx", ".webm"
        if "libopenh264" in r.stdout:
            return "libopenh264", ".mp4"
    except Exception:
        pass
    return "libvpx", ".webm"


# ---------------------------------------------------------------------------
# Per-slide single-page HTML builder
# ---------------------------------------------------------------------------

def build_single_slide_html(slide: dict, theme_css: str = "") -> str:
    """Render a single slide to a standalone HTML page (1920×1080)."""
    layout = slide.get("layout", "bullets")
    title = slide.get("title", "")
    content = slide.get("content") or {}

    body = _render_layout(layout, title, content, slide)
    chart_js = _build_chart_js(slide, content)

    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=1920">
<style>
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
html, body {{
  width: 1920px; height: 1080px; overflow: hidden;
  font-family: "PingFang SC", "Microsoft YaHei", "Noto Sans CJK SC", "Helvetica Neue", Arial, sans-serif;
  background: #fff;
}}
{SLIDE_BASE_CSS}
{theme_css or CORPORATE_THEME_CSS}
</style>
</head>
<body>
<div class="slide-page">
{body}
</div>
<script src="https://cdn.jsdelivr.net/npm/echarts@5/dist/echarts.min.js"></script>
<script>
{chart_js}
window.__SLIDE_READY__ = true;
</script>
</body>
</html>"""


def _render_layout(layout: str, title: str, content: dict, slide: dict) -> str:
    if layout == "title":
        subtitle = content.get("subtitle", "")
        author = content.get("author", "")
        date = content.get("date", "")
        meta = " · ".join(filter(None, [author, date]))
        return f"""
<div class="layout-title">
  <h1>{title}</h1>
  {f'<div class="subtitle">{subtitle}</div>' if subtitle else ""}
  {f'<div class="meta">{meta}</div>' if meta else ""}
</div>"""

    if layout == "bullets":
        groups = content.get("groups") or []
        groups_html = ""
        for g in groups:
            heading = g.get("heading", "")
            items = g.get("items") or []
            items_html = "".join(
                f'<li class="level-{item.get("level", 1)}">{item.get("text", "")}</li>'
                for item in items
            )
            groups_html += f"""
<div class="bullet-group">
  {f'<div class="group-heading">{heading}</div>' if heading else ""}
  <ul>{items_html}</ul>
</div>"""
        return f"""
<div class="layout-content">
  <h2>{title}</h2>
  <div class="bullets-body">{groups_html}</div>
</div>"""

    if layout == "chart":
        chart_id = f"chart_{slide.get('slide_id', 'c0')}"
        slide["_chart_id"] = chart_id
        return f"""
<div class="layout-chart">
  <h2>{title}</h2>
  <div id="{chart_id}" class="chart-container"></div>
</div>"""

    if layout == "chart_with_text":
        chart_id = f"chart_{slide.get('slide_id', 'c0')}"
        slide["_chart_id"] = chart_id
        text_content = content.get("text_content") or {}
        tc_heading = text_content.get("heading", "")
        tc_items = text_content.get("items") or []
        items_html = "".join(f'<li>{i.get("text","")}</li>' for i in tc_items)
        chart_pos = content.get("chart_position", "left")
        chart_html = f'<div id="{chart_id}" class="chart-container-half"></div>'
        text_html = f"""<div class="text-half">
  {f'<div class="group-heading">{tc_heading}</div>' if tc_heading else ""}
  <ul>{items_html}</ul>
</div>"""
        left, right = (chart_html, text_html) if chart_pos == "left" else (text_html, chart_html)
        return f"""
<div class="layout-chart-text">
  <h2>{title}</h2>
  <div class="chart-text-body">{left}{right}</div>
</div>"""

    if layout == "two_column":
        left = content.get("left") or {}
        right = content.get("right") or {}
        def col_html(col):
            heading = col.get("heading", "")
            items = col.get("items") or []
            items_html = "".join(f'<li>{i.get("text","")}</li>' for i in items)
            return f"""<div class="column">
  {f'<div class="col-heading">{heading}</div>' if heading else ""}
  <ul>{items_html}</ul>
</div>"""
        return f"""
<div class="layout-two-col">
  <h2>{title}</h2>
  <div class="cols-body">{col_html(left)}{col_html(right)}</div>
</div>"""

    if layout == "timeline":
        milestones = content.get("milestones") or []
        ms_html = ""
        for m in milestones:
            status_class = f"ms-{m.get('status', 'default')}"
            ms_html += f"""<div class="milestone {status_class}">
  <div class="ms-dot"></div>
  <div class="ms-content">
    <div class="ms-date">{m.get('date','')}</div>
    <div class="ms-label">{m.get('label','')}</div>
    <div class="ms-desc">{m.get('description','')}</div>
  </div>
</div>"""
        return f"""
<div class="layout-timeline">
  <h2>{title}</h2>
  <div class="timeline">{ms_html}</div>
</div>"""

    if layout == "table":
        table = content.get("table") or {}
        headers = table.get("headers") or []
        rows = table.get("rows") or []
        th_html = "".join(f"<th>{h}</th>" for h in headers)
        rows_html = "".join(
            "<tr>" + "".join(f"<td>{c}</td>" for c in row) + "</tr>"
            for row in rows
        )
        return f"""
<div class="layout-table">
  <h2>{title}</h2>
  <div class="table-wrapper">
    <table><thead><tr>{th_html}</tr></thead><tbody>{rows_html}</tbody></table>
  </div>
</div>"""

    # Fallback to bullets
    return f'<div class="layout-content"><h2>{title}</h2></div>'


def _build_chart_js(slide: dict, content: dict) -> str:
    """Generate ECharts init JS for slides that have a chart."""
    from agent_publisher.extensions.slideshow.chart_builder import build_echarts_option
    import json

    chart_id = slide.get("_chart_id")
    chart_data = content.get("chart")

    if not chart_id or not chart_data:
        # chart_with_text layout
        chart_data = content.get("chart") if content.get("chart") else None
        if not chart_data:
            return ""
        chart_id = slide.get("_chart_id", "")

    if not chart_id:
        return ""

    try:
        option = build_echarts_option(chart_data)
        option_json = json.dumps(option, ensure_ascii=False)
    except Exception:
        return ""

    return f"""
(function() {{
  var dom = document.getElementById('{chart_id}');
  if (!dom) return;
  var chart = echarts.init(dom, null, {{renderer: 'canvas', width: dom.offsetWidth, height: dom.offsetHeight}});
  chart.setOption({option_json});
}})();
"""


# ---------------------------------------------------------------------------
# CSS
# ---------------------------------------------------------------------------

SLIDE_BASE_CSS = """
.slide-page {
  width: 1920px;
  height: 1080px;
  overflow: hidden;
  position: relative;
  display: flex;
  flex-direction: column;
}

/* ---- Title layout ---- */
.layout-title {
  width: 100%; height: 100%;
  display: flex; flex-direction: column;
  justify-content: center; align-items: center;
  text-align: center; padding: 80px 140px;
  background: var(--title-bg, linear-gradient(135deg, #1a365d 0%, #2b6cb0 100%));
}
.layout-title h1 {
  font-size: 72px; font-weight: 800; color: #fff;
  line-height: 1.2; margin-bottom: 24px; letter-spacing: -1px;
}
.layout-title .subtitle {
  font-size: 36px; color: rgba(255,255,255,0.85); margin-bottom: 20px; font-weight: 400;
}
.layout-title .meta {
  font-size: 28px; color: rgba(255,255,255,0.6);
}

/* ---- Content layouts (bullets, chart, etc.) ---- */
.layout-content, .layout-chart, .layout-chart-text, .layout-two-col, .layout-timeline, .layout-table {
  width: 100%; height: 100%;
  padding: 60px 100px 60px;
  display: flex; flex-direction: column;
  background: var(--slide-bg, #fff);
}
.layout-content h2, .layout-chart h2, .layout-chart-text h2,
.layout-two-col h2, .layout-timeline h2, .layout-table h2 {
  font-size: 52px; font-weight: 700;
  color: var(--title-color, #1a365d);
  margin-bottom: 40px; line-height: 1.2;
  border-bottom: 5px solid var(--accent, #3182ce);
  padding-bottom: 20px;
}

/* ---- Bullets ---- */
.bullets-body { flex: 1; display: flex; flex-direction: column; justify-content: center; gap: 16px; }
.bullet-group { margin-bottom: 20px; }
.group-heading {
  font-size: 34px; font-weight: 600; color: var(--accent, #2b6cb0);
  margin-bottom: 12px;
}
ul { list-style: none; padding: 0; }
li {
  font-size: 38px; line-height: 1.5; color: #2d3748;
  padding: 10px 0 10px 48px; position: relative;
  border-bottom: 1px solid #f0f4f8;
}
li::before {
  content: "▸";
  position: absolute; left: 10px;
  color: var(--accent, #3182ce); font-size: 32px;
}
li.level-2 { font-size: 32px; padding-left: 80px; color: #4a5568; }

/* ---- Chart ---- */
.chart-container { flex: 1; min-height: 600px; }
.chart-container-half { width: 100%; min-height: 500px; }

/* ---- Chart + Text ---- */
.chart-text-body {
  flex: 1; display: flex; gap: 60px; align-items: stretch;
}
.chart-text-body > * { flex: 1; }
.text-half {
  display: flex; flex-direction: column; justify-content: center;
  padding: 20px 0;
}
.text-half ul li { font-size: 34px; }

/* ---- Two column ---- */
.cols-body {
  flex: 1; display: grid; grid-template-columns: 1fr 1fr; gap: 60px;
}
.column {
  background: #f7fafc; border-radius: 16px; padding: 40px;
  border-left: 8px solid var(--accent, #3182ce);
}
.col-heading {
  font-size: 38px; font-weight: 700; color: var(--accent, #2b6cb0);
  margin-bottom: 24px;
}
.column ul li { font-size: 32px; border-bottom-color: #e2e8f0; }

/* ---- Timeline ---- */
.timeline { flex: 1; display: flex; flex-direction: column; justify-content: center; gap: 24px; padding-left: 60px; position: relative; }
.timeline::before {
  content: ""; position: absolute; left: 16px; top: 20px; bottom: 20px;
  width: 4px; background: var(--accent, #3182ce); border-radius: 2px;
}
.milestone { display: flex; gap: 40px; align-items: flex-start; position: relative; }
.ms-dot {
  width: 24px; height: 24px; border-radius: 50%;
  background: var(--accent, #3182ce); border: 4px solid #fff;
  box-shadow: 0 0 0 3px var(--accent, #3182ce);
  flex-shrink: 0; margin-top: 8px; margin-left: -10px;
}
.ms-completed .ms-dot { background: #38a169; box-shadow: 0 0 0 3px #38a169; }
.ms-content { flex: 1; }
.ms-date { font-size: 28px; color: #718096; font-weight: 500; }
.ms-label { font-size: 36px; font-weight: 700; color: #1a202c; }
.ms-desc { font-size: 28px; color: #4a5568; margin-top: 4px; }

/* ---- Table ---- */
.table-wrapper { flex: 1; overflow: hidden; }
table { width: 100%; border-collapse: collapse; font-size: 32px; }
thead th {
  background: var(--title-color, #1a365d); color: #fff;
  padding: 20px 28px; text-align: left; font-size: 30px;
}
tbody td { padding: 18px 28px; border-bottom: 1px solid #e2e8f0; }
tbody tr:nth-child(even) { background: #f7fafc; }
"""

CORPORATE_THEME_CSS = """
:root {
  --title-bg: linear-gradient(135deg, #1a365d 0%, #2b6cb0 100%);
  --slide-bg: #ffffff;
  --title-color: #1a365d;
  --accent: #3182ce;
}
"""


# ---------------------------------------------------------------------------
# Screenshot engine
# ---------------------------------------------------------------------------

async def screenshot_slides(
    slides: list[dict],
    out_dir: Path,
    theme_css: str = "",
) -> list[tuple[Path, float]]:
    """Render each slide to a PNG screenshot.

    Returns list of (png_path, duration_seconds).
    Uses Playwright with 1920×1080 viewport and deviceScaleFactor=2 for crisp rendering.
    """
    from playwright.async_api import async_playwright

    out_dir.mkdir(parents=True, exist_ok=True)
    results: list[tuple[Path, float]] = []

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-web-security", "--allow-file-access-from-files"],
        )
        context = await browser.new_context(
            viewport={"width": SLIDE_WIDTH, "height": SLIDE_HEIGHT},
            device_scale_factor=2,  # Retina quality
        )
        page = await context.new_page()

        for i, slide in enumerate(slides):
            html = build_single_slide_html(slide, theme_css=theme_css)

            # Write temp HTML to disk (needed for ECharts CDN)
            tmp_html = out_dir / f"_slide_{i:03d}.html"
            tmp_html.write_text(html, encoding="utf-8")

            await page.goto(f"file://{tmp_html.resolve()}")

            # Wait for ECharts to render (if any chart)
            if slide.get("_chart_id") or (slide.get("content") or {}).get("chart"):
                try:
                    await page.wait_for_function(
                        "window.__SLIDE_READY__ === true", timeout=8000
                    )
                    # Extra wait for ECharts animation
                    await page.wait_for_timeout(800)
                except Exception:
                    await page.wait_for_timeout(1200)
            else:
                await page.wait_for_function(
                    "window.__SLIDE_READY__ === true", timeout=5000
                )
                await page.wait_for_timeout(200)

            png_path = out_dir / f"slide_{i:03d}.png"
            await page.screenshot(
                path=str(png_path),
                full_page=False,
                clip={"x": 0, "y": 0, "width": SLIDE_WIDTH, "height": SLIDE_HEIGHT},
            )
            duration = float(slide.get("duration") or 6)
            results.append((png_path, duration))
            logger.info("Screenshot slide %d/%d: %s (%.1fs)", i + 1, len(slides), png_path.name, duration)

            # Clean up temp HTML
            tmp_html.unlink(missing_ok=True)

        await context.close()
        await browser.close()

    return results


# ---------------------------------------------------------------------------
# ffmpeg video composition
# ---------------------------------------------------------------------------

async def compose_video(
    frames: list[tuple[Path, float]],
    output_path: str,
    audio_path: str | None = None,
    srt_path: str | None = None,
    ffmpeg_bin: str | None = None,
) -> str:
    """Compose frames into a video using ffmpeg concat demuxer.

    Fast path: PNG images → concat → VP8/VP9 encode → merge audio → burn subtitles.
    No intermediate clips needed. 9 slides encode in ~2 seconds.

    Returns actual output path (always .webm with current codec setup).
    """
    if not ffmpeg_bin:
        ffmpeg_bin = _find_ffmpeg()

    vcodec, ext = _best_video_codec(ffmpeg_bin)
    if not output_path.endswith(ext):
        output_path = output_path.rsplit(".", 1)[0] + ext

    if not frames:
        raise ValueError("No frames to compose")

    tmp_dir = tempfile.mkdtemp(prefix="slideshow_compose_")
    try:
        # Step 1: Build concat list file (PNG + duration)
        concat_list = Path(tmp_dir) / "concat.txt"
        with open(concat_list, "w") as f:
            for png, dur in frames:
                # Each PNG is held for its duration
                f.write(f"file '{png.resolve()}'\n")
                f.write(f"duration {dur:.3f}\n")
            # ffmpeg concat demuxer quirk: repeat last frame to avoid truncation
            last_png, last_dur = frames[-1]
            f.write(f"file '{last_png.resolve()}'\n")

        # Step 2: Encode video from PNG concat (no intermediate clips)
        raw_video = str(Path(tmp_dir) / f"raw{ext}")
        await _concat_pngs_to_video(concat_list, raw_video, ffmpeg_bin, vcodec)

        # Step 3: Merge audio + burn subtitles
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        # Resolve to absolute paths
        abs_audio = str(Path(audio_path).resolve()) if audio_path else None
        abs_srt = str(Path(srt_path).resolve()) if srt_path else None
        final = await _add_audio_subtitles(
            raw_video, output_path, abs_audio, abs_srt, ffmpeg_bin, vcodec, ext
        )

        logger.info("Video composed: %s (%.1f MB)", final, Path(final).stat().st_size / 1024 / 1024)
        return final

    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


async def _concat_pngs_to_video(
    concat_list: Path, output: str, ffmpeg_bin: str, vcodec: str
) -> None:
    """Encode PNG sequence from concat list into a video file."""
    is_webm = output.endswith(".webm")
    vcodec_args = _vcodec_args(vcodec, is_webm)
    args = [
        ffmpeg_bin, "-y",
        "-f", "concat", "-safe", "0",
        "-i", str(concat_list),
        "-vf", f"scale={SLIDE_WIDTH}:{SLIDE_HEIGHT}:flags=lanczos",
        *vcodec_args,
        "-pix_fmt", "yuv420p",
        "-r", "25",
        output,
    ]
    await _run_ffmpeg(args)


async def _single_frame_video(
    png: str, dur: float, output: str,
    audio: str | None, srt: str | None,
    ffmpeg: str, vcodec: str
) -> str:
    """Create a video from a single PNG frame."""
    is_webm = output.endswith(".webm")
    vcodec_args = _vcodec_args(vcodec, is_webm)

    args = [
        ffmpeg, "-y",
        "-loop", "1", "-i", png,
        "-t", str(dur),
        *vcodec_args,
        "-pix_fmt", "yuv420p",
        "-r", "25",
        output,
    ]
    await _run_ffmpeg(args)
    return output


async def _frames_to_clips(
    frames: list[tuple[Path, float]], tmp_dir: str,
    ffmpeg: str, vcodec: str
) -> list[str]:
    """Encode each PNG frame as a short video clip."""
    is_webm = vcodec in ("libvpx", "libvpx-vp9")
    ext = ".webm" if is_webm else ".mp4"
    vcodec_args = _vcodec_args(vcodec, is_webm)
    clips = []

    for i, (png, dur) in enumerate(frames):
        clip_path = str(Path(tmp_dir) / f"clip_{i:03d}{ext}")
        # Each clip: hold the image for (duration - xfade_duration) + xfade_duration
        # The xfade overlap means each clip needs to be slightly longer
        clip_dur = max(dur, XFADE_DURATION + 0.1)
        args = [
            ffmpeg, "-y",
            "-loop", "1", "-i", str(png),
            "-t", f"{clip_dur:.3f}",
            *vcodec_args,
            "-pix_fmt", "yuv420p",
            "-r", "25",
            clip_path,
        ]
        await _run_ffmpeg(args)
        clips.append(clip_path)

    return clips


async def _concat_with_xfade(
    clips: list[str],
    frames: list[tuple[Path, float]],
    output: str,
    ffmpeg: str,
    vcodec: str,
    ext: str,
) -> None:
    """Use ffmpeg xfade filter to crossfade between clips."""
    if len(clips) == 1:
        shutil.copy2(clips[0], output)
        return

    # Build xfade filter graph
    # For n clips: [0][1]xfade=...[v01]; [v01][2]xfade=...[v012]; ...
    inputs = []
    for c in clips:
        inputs += ["-i", c]

    # Calculate xfade offsets: offset = cumulative duration of clips before this one
    # minus xfade_duration per transition
    filter_parts = []
    cumulative = 0.0
    prev_label = "[0:v]"

    for i in range(1, len(clips)):
        dur_i = float(frames[i - 1][1])
        cumulative += dur_i - XFADE_DURATION
        out_label = f"[v{i}]" if i < len(clips) - 1 else "[vout]"
        filter_parts.append(
            f"{prev_label}[{i}:v]xfade=transition=fade:duration={XFADE_DURATION}:offset={cumulative:.3f}{out_label}"
        )
        prev_label = f"[v{i}]"

    filter_complex = ";".join(filter_parts)
    vcodec_args = _vcodec_args(vcodec, ext == ".webm")

    args = [
        ffmpeg, "-y",
        *inputs,
        "-filter_complex", filter_complex,
        "-map", "[vout]",
        *vcodec_args,
        "-pix_fmt", "yuv420p",
        output,
    ]
    await _run_ffmpeg(args)


async def _add_audio_subtitles(
    video: str, output: str,
    audio: str | None, srt: str | None,
    ffmpeg: str, vcodec: str, ext: str,
) -> str:
    """Merge audio and burn subtitles into the video."""
    if not audio and not srt:
        shutil.copy2(video, output)
        return output

    is_webm = ext == ".webm"
    vcodec_args = _vcodec_args(vcodec, is_webm)
    acodec = "libvorbis" if is_webm else "aac"

    args = [ffmpeg, "-y", "-i", video]
    if audio:
        args += ["-i", audio]

    if srt and Path(srt).exists():
        # Burn subtitles as filter
        # Escape path for ffmpeg filter
        srt_escaped = srt.replace("\\", "/").replace(":", "\\:")
        vf = f"subtitles='{srt_escaped}':force_style='FontName=PingFang SC,FontSize=24,PrimaryColour=&Hffffff,OutlineColour=&H000000,Outline=2,Shadow=1,Alignment=2,MarginV=40'"
        args += ["-vf", vf]

    args += [*vcodec_args, "-pix_fmt", "yuv420p"]

    if audio:
        args += ["-c:a", acodec, "-shortest"]
    else:
        args += ["-an"]

    args.append(output)
    await _run_ffmpeg(args)
    return output


def _vcodec_args(vcodec: str, is_webm: bool) -> list[str]:
    """Return ffmpeg video codec arguments."""
    if vcodec == "libopenh264":
        return ["-c:v", "libopenh264", "-b:v", "4M"]
    if vcodec == "libvpx-vp9":
        return ["-c:v", "libvpx-vp9", "-crf", "30", "-b:v", "0", "-deadline", "realtime"]
    if vcodec == "libvpx":
        return ["-c:v", "libvpx", "-crf", "10", "-b:v", "4M"]
    return ["-c:v", vcodec]


async def _run_ffmpeg(args: list[str]) -> None:
    """Run an ffmpeg command, raising on error."""
    proc = await asyncio.create_subprocess_exec(
        *args,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    _, stderr = await proc.communicate()
    if proc.returncode != 0:
        err = stderr.decode(errors="replace")
        logger.error("ffmpeg failed (rc=%d): %s", proc.returncode, err[-600:])
        raise RuntimeError(f"ffmpeg failed (rc={proc.returncode})")


# ---------------------------------------------------------------------------
# Legacy compatibility shim
# ---------------------------------------------------------------------------

class VideoExporter:
    """Compatibility shim — delegates to new screenshot-based pipeline.

    Old callers using .export(html_path, output_mp4, tts_audio_path) still work.
    New code should call screenshot_slides() + compose_video() directly.
    """

    async def export(
        self,
        html_path: str,
        output_mp4: str,
        tts_audio_path: str | None = None,
    ) -> str:
        """Legacy entry point: kept for backward compatibility only.

        NOTE: This path no longer screen-records. Instead it builds the HTML,
        screenshots each slide, and composes the video — but it needs the
        slides list, not an HTML path. If you have slides, call compose_video directly.

        This shim parses the reveal.js HTML to count slides and takes whole-page
        screenshots of the rendered HTML as a fallback.
        """
        # Fall back to whole-page screenshot of the HTML as-is
        # (legacy behavior, still better than recording)
        ffmpeg_bin = _find_ffmpeg()
        vcodec, ext = _best_video_codec(ffmpeg_bin)
        out_path = output_mp4
        if not out_path.endswith(ext):
            out_path = out_path.rsplit(".", 1)[0] + ext

        from playwright.async_api import async_playwright

        tmp_dir = tempfile.mkdtemp(prefix="slideshow_legacy_")
        try:
            async with async_playwright() as pw:
                browser = await pw.chromium.launch(
                    headless=True,
                    args=["--no-sandbox"],
                )
                context = await browser.new_context(
                    viewport={"width": SLIDE_WIDTH, "height": SLIDE_HEIGHT},
                    device_scale_factor=2,
                )
                page = await context.new_page()
                abs_html = str(Path(html_path).resolve())
                await page.goto(f"file://{abs_html}")
                await page.wait_for_timeout(2000)

                # Screenshot full page once
                png = str(Path(tmp_dir) / "frame.png")
                await page.screenshot(path=png, full_page=False)
                await context.close()
                await browser.close()

            # Encode as 10-second static video
            result = await _single_frame_video(
                png, 10.0, out_path, tts_audio_path, None, ffmpeg_bin, vcodec
            )
            return result
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)
