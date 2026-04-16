from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import JSON, DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from agent_publisher.models.base import Base


class UserPreference(Base):
    """Lightweight user preference storage for personalized hotspot discovery."""

    __tablename__ = "user_preferences"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_email: Mapped[str] = mapped_column(String(255), unique=True, index=True)

    # Topics the user is interested in (e.g. ["AI", "金融", "新能源"])
    interest_keywords: Mapped[list] = mapped_column(JSON, default=list)

    # Platforms the user prefers (e.g. ["weibo", "douyin", "zhihu"])
    preferred_platforms: Mapped[list] = mapped_column(JSON, default=list)

    # Keywords to suppress from results (e.g. ["广告", "推广"])
    blocked_keywords: Mapped[list] = mapped_column(JSON, default=list)

    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
