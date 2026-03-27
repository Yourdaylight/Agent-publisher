from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class LLMProfileCreate(BaseModel):
    name: str
    provider: str = "openai"
    model: str = "gpt-4o"
    api_key: str = ""
    base_url: str = ""
    is_default: bool = False
    description: str = ""


class LLMProfileUpdate(BaseModel):
    name: str | None = None
    provider: str | None = None
    model: str | None = None
    api_key: str | None = None
    base_url: str | None = None
    is_default: bool | None = None
    description: str | None = None


def _mask(value: str) -> str:
    """Mask sensitive values, showing only first 4 and last 4 chars."""
    if not value:
        return ""
    if len(value) <= 8:
        return "*" * len(value)
    return value[:4] + "*" * (len(value) - 8) + value[-4:]


class LLMProfileOut(BaseModel):
    id: int
    name: str
    provider: str
    model: str
    api_key: str
    base_url: str
    is_default: bool
    description: str
    created_at: datetime

    model_config = {"from_attributes": True}

    @classmethod
    def from_orm_masked(cls, obj: object) -> "LLMProfileOut":
        """Create output with masked api_key."""
        data = cls.model_validate(obj)
        data.api_key = _mask(data.api_key)
        return data
