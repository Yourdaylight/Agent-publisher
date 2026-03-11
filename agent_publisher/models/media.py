from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Integer, JSON, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

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
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    def __repr__(self) -> str:
        return f"<MediaAsset id={self.id} filename={self.filename!r}>"
