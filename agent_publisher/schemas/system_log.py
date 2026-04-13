from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class SystemLogOut(BaseModel):
    id: int
    timestamp: datetime
    action: str
    target_type: str = ""
    target_id: str = ""
    description: str = ""
    operator: str = ""
    is_admin: bool = False
    status: str = "success"
    error_message: str = ""
    extra: str = ""
    client_ip: str = ""
    request_path: str = ""

    model_config = {"from_attributes": True}


class SystemLogStats(BaseModel):
    total: int = 0
    today: int = 0
    failed: int = 0
    by_action: dict[str, int] = {}
