from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class TaskOut(BaseModel):
    id: int
    agent_id: int | None
    task_type: str
    status: str
    result: dict | None
    steps: list | None = None
    started_at: datetime | None
    finished_at: datetime | None
    created_at: datetime

    model_config = {"from_attributes": True}


class BatchRequest(BaseModel):
    agent_ids: list[int] | None = None  # None = all active agents
