from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, JSON, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from agent_publisher.models.base import Base


class SourceConfig(Base):
    """数据源配置 — RSS订阅 / 热榜平台 / 搜索引擎"""

    __tablename__ = "source_configs"

    id: Mapped[int] = mapped_column(primary_key=True)
    # "rss" | "trending" | "search"
    source_type: Mapped[str] = mapped_column(String(50))
    # 唯一标识: "toutiao" / "feed:hacker-news" / "search:google"
    source_key: Mapped[str] = mapped_column(String(200), unique=True)
    # 显示名称: "今日头条" / "Hacker News"
    display_name: Mapped[str] = mapped_column(String(200))
    # JSON — 类型特定配置
    #   RSS:      {"url": "https://...", "max_age_days": 3}
    #   Trending: {"platform_id": "toutiao"}
    #   Search:   {"engine": "google", "keywords": [...]}
    config: Mapped[dict | None] = mapped_column(JSON, default=dict, nullable=True)
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    # 可选覆盖采集频率 (cron 表达式)
    collect_cron: Mapped[str | None] = mapped_column(String(100), default=None, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    bindings: Mapped[list["AgentSourceBinding"]] = relationship(
        back_populates="source_config", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<SourceConfig id={self.id} key={self.source_key!r} type={self.source_type!r}>"


class AgentSourceBinding(Base):
    """Agent <-> SourceConfig 多对多绑定"""

    __tablename__ = "agent_source_bindings"
    __table_args__ = (UniqueConstraint("agent_id", "source_config_id", name="uq_agent_source"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    agent_id: Mapped[int] = mapped_column(ForeignKey("agents.id"))
    source_config_id: Mapped[int] = mapped_column(ForeignKey("source_configs.id"))
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    # Per-agent 关键词过滤 (JSON array)
    filter_keywords: Mapped[list | None] = mapped_column(JSON, default=None, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    source_config: Mapped["SourceConfig"] = relationship(back_populates="bindings")
