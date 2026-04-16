from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from agent_publisher.models.base import Base


class LLMProfile(Base):
    __tablename__ = "llm_profiles"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    provider: Mapped[str] = mapped_column(String(50), default="openai")
    model: Mapped[str] = mapped_column(String(100), default="gpt-4o")
    api_key: Mapped[str] = mapped_column(String(300), default="", nullable=True)
    base_url: Mapped[str] = mapped_column(String(500), default="", nullable=True)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)
    description: Mapped[str] = mapped_column(Text, default="", nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    def __repr__(self) -> str:
        return f"<LLMProfile id={self.id} name={self.name!r} provider={self.provider!r} model={self.model!r}>"
