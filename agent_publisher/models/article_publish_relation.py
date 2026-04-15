from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from agent_publisher.models.base import Base


class ArticlePublishRelation(Base):
    __tablename__ = "article_publish_relations"
    __table_args__ = (
        UniqueConstraint(
            "article_id",
            "account_id",
            name="uq_article_publish_relations_article_account",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    article_id: Mapped[int] = mapped_column(ForeignKey("articles.id"))
    account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id"))
    wechat_media_id: Mapped[str] = mapped_column(String(200), default="")
    publish_status: Mapped[str] = mapped_column(String(20), default="pending")
    sync_status: Mapped[str] = mapped_column(String(20), default="pending")
    last_error: Mapped[str] = mapped_column(Text, default="")
    last_published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    article: Mapped["Article"] = relationship(back_populates="publish_relations")  # noqa: F821
    account: Mapped["Account"] = relationship(back_populates="article_publish_relations")  # noqa: F821

    @property
    def account_name(self) -> str:
        return self.account.name if self.account else ""

    def __repr__(self) -> str:
        return (
            f"<ArticlePublishRelation id={self.id} article_id={self.article_id} "
            f"account_id={self.account_id} publish_status={self.publish_status!r} "
            f"sync_status={self.sync_status!r}>"
        )
