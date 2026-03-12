from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, JSON, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from agent_publisher.models.base import Base


class Agent(Base):
    __tablename__ = "agents"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    topic: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text, default="")
    account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id"))
    rss_sources: Mapped[list | None] = mapped_column(JSON, default=list)
    # Deprecated: LLM config now comes from platform settings (DEFAULT_LLM_*)
    llm_provider: Mapped[str] = mapped_column(String(50), default="", nullable=True)
    llm_model: Mapped[str] = mapped_column(String(100), default="", nullable=True)
    llm_api_key: Mapped[str] = mapped_column(String(300), default="", nullable=True)
    llm_base_url: Mapped[str] = mapped_column(String(500), default="", nullable=True)
    prompt_template: Mapped[str] = mapped_column(Text, default="")
    image_style: Mapped[str] = mapped_column(String(500), default="现代简约风格，色彩鲜明")
    default_style_id: Mapped[str | None] = mapped_column(String(50), default=None, nullable=True)
    schedule_cron: Mapped[str] = mapped_column(String(50), default="0 8 * * *")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    account: Mapped["Account"] = relationship(back_populates="agents")  # noqa: F821
    articles: Mapped[list["Article"]] = relationship(back_populates="agent")  # noqa: F821
    tasks: Mapped[list["Task"]] = relationship(back_populates="agent")  # noqa: F821

    def __repr__(self) -> str:
        return f"<Agent id={self.id} name={self.name!r} topic={self.topic!r}>"
