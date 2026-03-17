from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, JSON, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from agent_publisher.models.base import Base


class MediaAsset(Base):
    __tablename__ = "media_assets"

    id: Mapped[int] = mapped_column(primary_key=True)
    filename: Mapped[str] = mapped_column(String(300), comment="Original filename")
    stored_filename: Mapped[str] = mapped_column(String(300), unique=True, comment="UUID-based stored filename")
    content_type: Mapped[str] = mapped_column(String(100), default="image/png")
    file_size: Mapped[int] = mapped_column(Integer, default=0, comment="File size in bytes")
    tags: Mapped[list | None] = mapped_column(JSON, default=list, comment="Tag list for categorization")
    description: Mapped[str] = mapped_column(Text, default="", comment="Description of the asset")
    owner_email: Mapped[str] = mapped_column(String(200), default="", comment="Uploader email")
    source_kind: Mapped[str] = mapped_column(String(50), default="manual", comment="manual / article_body / article_cover")
    source_url: Mapped[str] = mapped_column(String(1000), default="", comment="Original remote URL or inline image fingerprint")
    article_id: Mapped[int | None] = mapped_column(ForeignKey("articles.id"), nullable=True, default=None)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    wechat_mappings: Mapped[list["MediaAssetWechatMapping"]] = relationship(
        back_populates="media_asset",
        cascade="all, delete-orphan",
        order_by="MediaAssetWechatMapping.id.desc()",
    )

    def __repr__(self) -> str:
        return f"<MediaAsset id={self.id} filename={self.filename!r} source_kind={self.source_kind!r}>"


class MediaAssetWechatMapping(Base):
    __tablename__ = "media_asset_wechat_mappings"
    __table_args__ = (
        UniqueConstraint(
            "media_asset_id",
            "account_id",
            name="uq_media_asset_wechat_mapping_asset_account",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    media_asset_id: Mapped[int] = mapped_column(ForeignKey("media_assets.id"), nullable=False)
    account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id"), nullable=False)
    wechat_url: Mapped[str] = mapped_column(String(1000), default="")
    upload_status: Mapped[str] = mapped_column(String(20), default="pending")
    error_message: Mapped[str] = mapped_column(Text, default="")
    uploaded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    media_asset: Mapped["MediaAsset"] = relationship(back_populates="wechat_mappings")

    def __repr__(self) -> str:
        return (
            f"<MediaAssetWechatMapping id={self.id} media_asset_id={self.media_asset_id} "
            f"account_id={self.account_id} status={self.upload_status!r}>"
        )
