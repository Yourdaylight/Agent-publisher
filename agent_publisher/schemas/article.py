from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class ArticleOut(BaseModel):
    id: int
    agent_id: int
    title: str
    digest: str
    content: str
    html_content: str
    cover_image_url: str
    images: list | None
    source_news: list | None
    status: str
    wechat_media_id: str
    published_at: datetime | None
    created_at: datetime
    source_article_id: int | None = None
    variant_style: str | None = None
    variant_count: int = 0

    model_config = {"from_attributes": True}


class ArticleBrief(BaseModel):
    id: int
    agent_id: int
    title: str
    digest: str
    status: str
    created_at: datetime
    source_article_id: int | None = None
    variant_style: str | None = None
    variant_count: int = 0

    model_config = {"from_attributes": True}
