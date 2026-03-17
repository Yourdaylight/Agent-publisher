from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class ArticlePublishRelationOut(BaseModel):
    id: int
    article_id: int
    account_id: int
    account_name: str = ""
    wechat_media_id: str
    publish_status: str
    sync_status: str
    last_error: str
    last_published_at: datetime | None
    last_synced_at: datetime | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ArticlePublishRequest(BaseModel):
    target_account_ids: list[int] | None = None


class ArticleSyncRequest(BaseModel):
    target_account_ids: list[int] | None = None


class AccountScopedPublishResult(BaseModel):
    account_id: int
    account_name: str
    status: str
    wechat_media_id: str = ""
    stage: str = ""
    error: str = ""


class ArticlePublishResponse(BaseModel):
    ok: bool
    article_id: int
    overall_status: str
    media_id: str = ""
    target_account_ids: list[int]
    results: list[AccountScopedPublishResult]


class ArticleSyncResponse(BaseModel):
    ok: bool
    article_id: int
    overall_status: str
    sync_status: str
    target_account_ids: list[int]
    results: list[AccountScopedPublishResult]


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
    publish_relations: list[ArticlePublishRelationOut] = []

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
