"""Semantic chart data → ECharts option builder.

Converts LLM-produced chart descriptions into ECharts ``option`` dicts that
can be embedded in the reveal.js HTML via JSON serialisation.
"""
from __future__ import annotations

from typing import Any


# ---------------------------------------------------------------------------
# Per-type builders
# ---------------------------------------------------------------------------


def _bar_option(chart: dict) -> dict[str, Any]:
    return {
        "tooltip": {"trigger": "axis"},
        "legend": {"data": [s["name"] for s in chart.get("series", [])]},
        "xAxis": {"type": "category", "data": chart.get("categories", [])},
        "yAxis": {"type": "value"},
        "series": [
            {"name": s["name"], "type": "bar", "data": s["data"]}
            for s in chart.get("series", [])
        ],
    }


def _line_option(chart: dict) -> dict[str, Any]:
    return {
        "tooltip": {"trigger": "axis"},
        "legend": {"data": [s["name"] for s in chart.get("series", [])]},
        "xAxis": {"type": "category", "data": chart.get("categories", [])},
        "yAxis": {"type": "value"},
        "series": [
            {"name": s["name"], "type": "line", "data": s["data"], "smooth": True}
            for s in chart.get("series", [])
        ],
    }


def _pie_option(chart: dict) -> dict[str, Any]:
    series_list = chart.get("series", [{}])
    first = series_list[0] if series_list else {}
    return {
        "tooltip": {"trigger": "item"},
        "legend": {"orient": "vertical", "left": "left"},
        "series": [
            {
                "name": first.get("name", ""),
                "type": "pie",
                "radius": "55%",
                "data": first.get("data", []),
                "emphasis": {"itemStyle": {"shadowBlur": 10, "shadowOffsetX": 0, "shadowColor": "rgba(0, 0, 0, 0.5)"}},
            }
        ],
    }


def _radar_option(chart: dict) -> dict[str, Any]:
    return {
        "tooltip": {},
        "radar": {"indicator": chart.get("indicators", [])},
        "series": [
            {
                "type": "radar",
                "data": [
                    {"value": s["data"], "name": s.get("name", "")}
                    for s in chart.get("series", [])
                ],
            }
        ],
    }


def _scatter_option(chart: dict) -> dict[str, Any]:
    return {
        "tooltip": {"trigger": "item"},
        "xAxis": {"type": "value"},
        "yAxis": {"type": "value"},
        "series": [
            {"name": s.get("name", ""), "type": "scatter", "data": s["data"]}
            for s in chart.get("series", [])
        ],
    }


def _funnel_option(chart: dict) -> dict[str, Any]:
    series_list = chart.get("series", [{}])
    first = series_list[0] if series_list else {}
    return {
        "tooltip": {"trigger": "item", "formatter": "{a} <br/>{b} : {c}%"},
        "series": [
            {
                "name": chart.get("title", ""),
                "type": "funnel",
                "left": "10%",
                "width": "80%",
                "data": first.get("data", []),
            }
        ],
    }


def _gauge_option(chart: dict) -> dict[str, Any]:
    series_list = chart.get("series", [{}])
    first = series_list[0] if series_list else {}
    return {
        "tooltip": {"formatter": "{a} <br/>{b} : {c}%"},
        "series": [
            {
                "name": chart.get("title", ""),
                "type": "gauge",
                "data": first.get("data", []),
            }
        ],
    }


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

BUILDERS: dict[str, Any] = {
    "bar": _bar_option,
    "line": _line_option,
    "pie": _pie_option,
    "radar": _radar_option,
    "scatter": _scatter_option,
    "funnel": _funnel_option,
    "gauge": _gauge_option,
}


def build_echarts_option(chart_data: dict) -> dict[str, Any]:
    """Convert a semantic chart dict from the LLM into a complete ECharts option."""
    chart_type = chart_data.get("chart_type", "bar")
    builder = BUILDERS.get(chart_type)
    if builder is None:
        builder = _bar_option  # fallback

    option = builder(chart_data)

    # Add title
    if chart_data.get("title"):
        option["title"] = {"text": chart_data["title"], "left": "center"}

    # Keep animation (great for preview and video recording)
    option["animation"] = True
    option["animationDuration"] = 1000

    return option
