from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from agent_publisher.models.base import Base


class Account(Base):
    __tablename__ = "accounts"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    appid: Mapped[str] = mapped_column(String(100), unique=True)
    appsecret: Mapped[str] = mapped_column(String(200))
    owner_email: Mapped[str] = mapped_column(String(200), default="")
    ip_whitelist: Mapped[str] = mapped_column(String(500), default="")
    access_token: Mapped[str] = mapped_column(String(600), default="")
    token_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # 第三方平台扫码授权模式
    auth_mode: Mapped[str] = mapped_column(
        String(20), default="manual"
    )  # "manual" | "platform"
    authorizer_appid: Mapped[str] = mapped_column(String(100), default="")
    authorizer_refresh_token: Mapped[str] = mapped_column(String(200), default="")
    authorizer_access_token: Mapped[str] = mapped_column(String(600), default="")
    authorizer_token_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    nick_name: Mapped[str] = mapped_column(String(200), default="")
    head_img: Mapped[str] = mapped_column(String(500), default="")
    service_type: Mapped[int] = mapped_column(Integer, default=0)
    verify_type: Mapped[int] = mapped_column(Integer, default=0)

    agents: Mapped[list["Agent"]] = relationship(back_populates="account")  # noqa: F821
    publish_records: Mapped[list["PublishRecord"]] = relationship(back_populates="account")  # noqa: F821
    article_publish_relations: Mapped[list["ArticlePublishRelation"]] = relationship(  # noqa: F821
        back_populates="account"
    )

    def __repr__(self) -> str:
        return f"<Account id={self.id} name={self.name!r} auth_mode={self.auth_mode!r}>"
