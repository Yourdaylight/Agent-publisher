from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class PublishRecordOut(BaseModel):
    id: int
    article_id: int
    account_id: int | None = None
    account_name: str = ""
    action: str
    wechat_media_id: str
    status: str
    operator: str
    error_message: str
    created_at: datetime

    model_config = {"from_attributes": True}


class PublishRecordBrief(BaseModel):
    id: int
    article_id: int
    account_id: int | None = None
    account_name: str = ""
    action: str
    status: str
    operator: str
    created_at: datetime

    model_config = {"from_attributes": True}
