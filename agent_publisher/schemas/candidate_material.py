from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class CandidateMaterialCreate(BaseModel):
    source_type: Literal["rss", "search", "skills_feed", "manual", "trending"]
    source_identity: str = ""
    original_url: str = ""
    title: str
    summary: str = ""
    raw_content: str = ""
    metadata: dict | None = None
    tags: list[str] = []
    agent_id: int | None = None
    quality_score: float | None = None


class CandidateMaterialUpdate(BaseModel):
    title: str | None = None
    summary: str | None = None
    raw_content: str | None = None
    metadata: dict | None = None
    status: Literal["pending", "accepted", "rejected"] | None = None
    quality_score: float | None = None


class CandidateMaterialTagUpdate(BaseModel):
    """Schema for adding/removing tags on a material."""

    add_tags: list[str] = []
    remove_tags: list[str] = []


class CandidateMaterialOut(BaseModel):
    id: int
    source_type: str
    source_identity: str
    original_url: str
    title: str
    summary: str
    raw_content: str
    metadata: dict | None = Field(
        None, validation_alias="extra_metadata", serialization_alias="metadata"
    )
    tags: list[str] = []
    agent_id: int | None = None
    is_duplicate: bool
    quality_score: float | None = None
    status: str
    created_at: datetime

    model_config = {"from_attributes": True, "populate_by_name": True, "by_alias": True}


class CandidateMaterialListParams(BaseModel):
    """Query parameters for listing candidate materials."""

    agent_id: int | None = None
    source_type: str | None = None
    status: str | None = None
    tags: list[str] | None = None
    start_date: datetime | None = None
    end_date: datetime | None = None
    page: int = 1
    page_size: int = 20
