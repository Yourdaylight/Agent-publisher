from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class AccountCreate(BaseModel):
    name: str
    appid: str
    appsecret: str
    ip_whitelist: str = ""


class AccountUpdate(BaseModel):
    name: str | None = None
    appid: str | None = None
    appsecret: str | None = None
    ip_whitelist: str | None = None


class AccountOut(BaseModel):
    id: int
    name: str
    appid: str
    ip_whitelist: str
    created_at: datetime

    model_config = {"from_attributes": True}
