from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel


class AgentCreate(BaseModel):
    name: str
    topic: str
    description: str = ""
    account_id: int
    rss_sources: list[dict] = []
    role: Literal["collector", "processor", "publisher", "full_pipeline"] = "full_pipeline"
    source_mode: Literal["independent_search", "rss", "skills_feed"] = "rss"
    search_config: dict | None = None
    allowed_skill_sources: list[str] | None = None
    llm_provider: str = "openai"
    llm_model: str = "gpt-4o"
    llm_api_key: str = ""
    llm_base_url: str = ""
    prompt_template: str = ""
    image_style: str = "现代简约风格，色彩鲜明"
    default_style_id: str | None = None
    schedule_cron: str = "0 8 * * *"
    is_active: bool = True


class AgentUpdate(BaseModel):
    name: str | None = None
    topic: str | None = None
    description: str | None = None
    rss_sources: list[dict] | None = None
    role: Literal["collector", "processor", "publisher", "full_pipeline"] | None = None
    source_mode: Literal["independent_search", "rss", "skills_feed"] | None = None
    search_config: dict | None = None
    allowed_skill_sources: list[str] | None = None
    llm_provider: str | None = None
    llm_model: str | None = None
    llm_api_key: str | None = None
    llm_base_url: str | None = None
    prompt_template: str | None = None
    image_style: str | None = None
    default_style_id: str | None = None
    schedule_cron: str | None = None
    is_active: bool | None = None


class AgentOut(BaseModel):
    id: int
    name: str
    topic: str
    description: str
    account_id: int
    rss_sources: list[dict] | None
    role: str
    source_mode: str
    search_config: dict | None = None
    allowed_skill_sources: list[str] | None = None
    llm_provider: str
    llm_model: str
    llm_base_url: str
    image_style: str
    default_style_id: str | None = None
    schedule_cron: str
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}
