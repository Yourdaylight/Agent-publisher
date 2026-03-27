"""Build a self-contained reveal.js HTML file from slide JSON data."""
from __future__ import annotations

import json
import uuid
import logging
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


def _extract_charts(slides: list[dict]) -> list[dict[str, Any]]:
    """Walk slides and convert chart semantic data to ECharts options."""
    charts: list[dict[str, Any]] = []
    for slide in slides:
        content = slide.get("content", {})
        chart_data = content.get("chart")
        if chart_data:
            chart_id = f"chart_{slide.get('slide_id', uuid.uuid4().hex[:8])}"
            slide["chart_id"] = chart_id
            option = build_echarts_option(chart_data)
            charts.append({"id": chart_id, "option": option})
    return charts


def build_reveal_html(
    slides: list[dict],
    *,
    preview_mode: bool = True,
    theme: str = "corporate",
) -> str:
    """Return a complete, self-contained reveal.js HTML string.

    Parameters
    ----------
    slides:
        List of slide dicts (LLM output).
    preview_mode:
        ``True`` → show controls, no autoSlide.
        ``False`` → autoSlide based on per-page ``duration``, for video recording.
    theme:
        CSS theme file name under ``templates/themes/``.
    """
    env = _make_env()

    charts = _extract_charts(slides)
    has_charts = len(charts) > 0

    # In video mode, auto_slide_ms is set per-slide via data-timing.
    # The global autoSlide is a fallback for slides without data-timing.
    auto_slide_ms = 0 if preview_mode else 5000

    # Load optional theme CSS
    theme_css = ""
    theme_file = TEMPLATES_DIR / "themes" / f"{theme}.css"
    if theme_file.exists():
        theme_css = theme_file.read_text(encoding="utf-8")

    template = env.get_template("reveal.html.j2")
    html = template.render(
        slides=slides,
        charts=charts,
        has_charts=has_charts,
        auto_slide_ms=auto_slide_ms,
        preview_mode=preview_mode,
        theme_css=theme_css,
        json=json,
    )
    return html
