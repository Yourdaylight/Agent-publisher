from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


# ── 11 个支持的热榜平台 ──────────────────────────────────────────────

TRENDING_PLATFORMS = [
    {"id": "toutiao", "name": "今日头条"},
    {"id": "weibo", "name": "微博热搜"},
    {"id": "zhihu", "name": "知乎热榜"},
    {"id": "baidu", "name": "百度热搜"},
    {"id": "douyin", "name": "抖音热点"},
    {"id": "bilibili", "name": "B站热门"},
    {"id": "36kr", "name": "36氪"},
    {"id": "sspai", "name": "少数派"},
    {"id": "ithome", "name": "IT之家"},
    {"id": "hackernews", "name": "Hacker News"},
    {"id": "producthunt", "name": "Product Hunt"},
]

TRENDING_PLATFORM_IDS = {p["id"] for p in TRENDING_PLATFORMS}


# ── SourceConfig schemas ──────────────────────────────────────────────

class SourceConfigCreate(BaseModel):
    source_type: Literal["rss", "trending", "search"]
    source_key: str
    display_name: str
    config: dict = {}
    is_enabled: bool = True
    collect_cron: str | None = None


class SourceConfigUpdate(BaseModel):
    display_name: str | None = None
    config: dict | None = None
    is_enabled: bool | None = None
    collect_cron: str | None = None


class SourceConfigOut(BaseModel):
    id: int
    source_type: str
    source_key: str
    display_name: str
    config: dict | None
    is_enabled: bool
    collect_cron: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ── AgentSourceBinding schemas ────────────────────────────────────────

class AgentSourceBindingCreate(BaseModel):
    source_config_id: int
    is_enabled: bool = True
    filter_keywords: list[str] | None = None


class AgentSourceBindingOut(BaseModel):
    id: int
    agent_id: int
    source_config_id: int
    is_enabled: bool
    filter_keywords: list[str] | None
    created_at: datetime
    # Nested source info
    source_config: SourceConfigOut | None = None

    model_config = {"from_attributes": True}


# ── Toggle schema ─────────────────────────────────────────────────────

class ToggleRequest(BaseModel):
    is_enabled: bool


# ── Collect result ────────────────────────────────────────────────────

class CollectResult(BaseModel):
    """采集结果"""
    source_type: str
    material_ids: list[int]
    count: int
