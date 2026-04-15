from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from agent_publisher.models.base import Base


class PublishRecord(Base):
    __tablename__ = "publish_records"

    id: Mapped[int] = mapped_column(primary_key=True)
    article_id: Mapped[int] = mapped_column(ForeignKey("articles.id"))
    account_id: Mapped[int | None] = mapped_column(ForeignKey("accounts.id"), nullable=True)
    action: Mapped[str] = mapped_column(String(20), default="publish")  # publish / sync
    wechat_media_id: Mapped[str] = mapped_column(String(200), default="")
    status: Mapped[str] = mapped_column(String(20), default="success")  # success / failed
    operator: Mapped[str] = mapped_column(String(200), default="admin")  # email or 'admin'
    error_message: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    article: Mapped["Article"] = relationship(back_populates="publish_records")  # noqa: F821
    account: Mapped["Account | None"] = relationship(back_populates="publish_records")  # noqa: F821

    @property
    def account_name(self) -> str:
        return self.account.name if self.account else ""

    def __repr__(self) -> str:
        return (
            f"<PublishRecord id={self.id} article_id={self.article_id} "
            f"account_id={self.account_id} action={self.action} status={self.status}>"
        )
