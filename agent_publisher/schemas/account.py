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
    owner_email: str
    ip_whitelist: str
    auth_mode: str = "manual"
    nick_name: str = ""
    head_img: str = ""
    service_type: int = 0
    verify_type: int = 0
    created_at: datetime

    model_config = {"from_attributes": True}
