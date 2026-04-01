"""Build independent chapter HTML files and concat player from slide data.

Replaces reveal_builder.py. Produces:
  - chapters/ch_XX.html  (self-contained, 1920x1080)
  - concat.html           (iframe player)
  - timeline.json          (metadata)
"""
from __future__ import annotations

import json
import logging
import uuid
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, select_autoescape

from agent_publisher.extensions.slideshow.chart_builder import build_echarts_option

logger = logging.getLogger(__name__)

TEMPLATES_DIR = Path(__file__).parent / "templates"


def _make_env() -> Environment:
    return Environment(
        loader=FileSystemLoader(str(TEMPLATES_DIR)),
        autoescape=select_autoescape(["html"]),
    )


def _load_theme_css(theme: str = "corporate") -> str:
    """Load and adapt theme CSS for chapter HTML (non-reveal.js selectors)."""
    theme_file = TEMPLATES_DIR / "themes" / f"{theme}.css"
    if not theme_file.exists():
        return ""
    css = theme_file.read_text(encoding="utf-8")
    # Adapt reveal.js selectors to standalone selectors
    css = _adapt_theme_css(css)
    return css


def _adapt_theme_css(css: str) -> str:
    """Replace reveal.js selectors with standalone chapter selectors.

    .reveal .slides section → .slide
    .reveal .slides section hN → .slide hN
    """
    import re
    # Replace .reveal .slides section with .slide
    css = re.sub(r"\.reveal\s+\.slides\s+section", ".slide", css)
    # Also handle .slide-layout-- selectors (already correct, no change needed)
    return css


def _extract_charts(slides: list[dict]) -> list[dict[str, Any]]:
    """Walk slides and convert chart semantic data to ECharts options.

    Returns list of {id, option_json} for template rendering.
    """
    charts: list[dict[str, Any]] = []
    for slide in slides:
        content = slide.get("content", {})
        chart_data = content.get("chart")
        if chart_data:
            chart_id = f"chart_{slide.get('slide_id', uuid.uuid4().hex[:8])}"
            slide["chart_id"] = chart_id
            option = build_echarts_option(chart_data)
            option_json = json.dumps(option, ensure_ascii=False)
            charts.append({"id": chart_id, "option_json": option_json})
    return charts


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def build_chapter_html(
    chapter_id: str,
    slides: list[dict],
    *,
    theme: str = "corporate",
    presentation_title: str = "",
    chapter_title: str = "",
) -> str:
    """Render a self-contained chapter HTML file.

    The HTML contains:
    - Inline CSS (base + theme)
    - All slide layouts via Jinja2 partials
    - ECharts init scripts (inline)
    - Auto-slide switching based on duration
    - postMessage('chapter-complete') when done
    """
    env = _make_env()

    charts = _extract_charts(slides)
    has_charts = len(charts) > 0
    theme_css = _load_theme_css(theme)

    template = env.get_template("chapter.html.j2")
    html = template.render(
        slides=slides,
        charts=charts,
        has_charts=has_charts,
        theme_css=theme_css,
        presentation_title=presentation_title,
        chapter_title=chapter_title,
        chapter_id=chapter_id,
    )
    return html


def build_concat_html(timeline: dict) -> str:
    """Render the concat.html browser player.

    The player loads chapter HTML files via iframes and provides
    playback controls (play/pause, prev/next, progress bar, fullscreen).
    """
    env = _make_env()

    chapters_for_js = []
    for ch in timeline.get("chapters", []):
        chapters_for_js.append({
            "chapter_id": ch["chapter_id"],
            "title": ch["title"],
            "slide_count": ch["slide_count"],
            "html_file": ch["html_file"],
            "notes": ch.get("notes_combined", ""),
        })

    template = env.get_template("concat.html.j2")
    html = template.render(
        title=timeline.get("title", "Slideshow"),
        chapters=timeline.get("chapters", []),
        chapters_json=json.dumps(chapters_for_js, ensure_ascii=False),
    )
    return html


def build_timeline_json(
    title: str,
    theme: str,
    narrative_arc: str,
    chapters: list[dict],
) -> dict:
    """Build the timeline.json metadata structure.

    Parameters
    ----------
    title: presentation title
    theme: CSS theme name
    narrative_arc: one-line narrative description
    chapters: list of dicts, each with:
        chapter_id, title, purpose, slide_count, slides (list[dict]),
        html_file (relative path like "chapters/ch_01.html")
    """
    chapter_entries = []
    total_duration = 0

    for ch in chapters:
        slides = ch.get("slides", [])
        ch_duration = sum(s.get("duration", 6) for s in slides)
        total_duration += ch_duration

        # Combine all notes for the chapter
        notes_combined = " ".join(
            s.get("notes", "") for s in slides if s.get("notes")
        )

        chapter_entries.append({
            "chapter_id": ch["chapter_id"],
            "title": ch["title"],
            "purpose": ch.get("purpose", ""),
            "slide_count": len(slides),
            "duration": ch_duration,
            "html_file": ch["html_file"],
            "notes_combined": notes_combined,
            "slides": [
                {
                    "slide_id": s.get("slide_id", f"slide_{i}"),
                    "title": s.get("title", ""),
                    "layout": s.get("layout", "bullets"),
                    "duration": s.get("duration", 6),
                    "notes": s.get("notes", ""),
                }
                for i, s in enumerate(slides)
            ],
        })

    return {
        "title": title,
        "theme": theme,
        "narrative_arc": narrative_arc,
        "total_chapters": len(chapter_entries),
        "total_duration": total_duration,
        "chapters": chapter_entries,
    }


# ---------------------------------------------------------------------------
# Video mode (vertical 1080×1920) builders
# ---------------------------------------------------------------------------

def build_vertical_scene_html(
    scenes: list[dict],
    *,
    theme: str = "dark_video",
    video_title: str = "",
    scene_title: str = "",
) -> str:
    """Render a self-contained vertical scene HTML file (1080×1920).

    Each scene contains three zones: top_text, visual, bottom_text
    with CSS entrance animations selected by the LLM.
    """
    env = _make_env()
    theme_css = _load_theme_css(theme)

    template = env.get_template("vertical_scene.html.j2")
    html = template.render(
        scenes=scenes,
        theme_css=theme_css,
        video_title=video_title,
        scene_title=scene_title,
    )
    return html


def build_vertical_concat_html(timeline: dict) -> str:
    """Render the vertical video concat.html player.

    Loads scene HTML files via iframes in 9:16 portrait ratio.
    """
    env = _make_env()

    scenes_for_js = []
    for sc in timeline.get("scenes", []):
        scenes_for_js.append({
            "scene_id": sc["scene_id"],
            "title": sc.get("title", ""),
            "html_file": sc["html_file"],
            "notes": sc.get("notes", ""),
        })

    template = env.get_template("vertical_concat.html.j2")
    html = template.render(
        title=timeline.get("title", "Video"),
        scenes=timeline.get("scenes", []),
        scenes_json=json.dumps(scenes_for_js, ensure_ascii=False),
    )
    return html


def build_video_timeline_json(
    title: str,
    theme: str,
    narrative_arc: str,
    scenes: list[dict],
) -> dict:
    """Build timeline.json for the vertical video mode.

    Parameters
    ----------
    title: video title
    theme: CSS theme name
    narrative_arc: one-line narrative description
    scenes: list of dicts, each with:
        scene_id, title, duration, html_file, notes, etc.
    """
    scene_entries = []
    total_duration = 0

    for sc in scenes:
        dur = sc.get("duration", 8)
        total_duration += dur
        scene_entries.append({
            "scene_id": sc["scene_id"],
            "title": sc.get("title", ""),
            "duration": dur,
            "html_file": sc["html_file"],
            "notes": sc.get("notes", ""),
        })

    return {
        "title": title,
        "theme": theme,
        "mode": "video",
        "narrative_arc": narrative_arc,
        "total_scenes": len(scene_entries),
        "total_duration": total_duration,
        "scenes": scene_entries,
    }
