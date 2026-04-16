"""Invite code models for the invite-based user onboarding system."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from agent_publisher.models.base import Base


class InviteCode(Base):
    """Invite code for user registration via self-media promotion."""

    __tablename__ = "invite_codes"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    channel: Mapped[str] = mapped_column(
        String(50), default="open"
    )  # douyin/xiaohongshu/wechat/open
    max_uses: Mapped[int] = mapped_column(Integer, default=0)  # 0 = unlimited
    used_count: Mapped[int] = mapped_column(Integer, default=0)
    bonus_credits: Mapped[int] = mapped_column(Integer, default=100)
    expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, default=None
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_by: Mapped[str] = mapped_column(String(200), default="")
    note: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class InviteRedemption(Base):
    """Record of an invite code being redeemed by a user."""

    __tablename__ = "invite_redemptions"

    id: Mapped[int] = mapped_column(primary_key=True)
    invite_code_id: Mapped[int] = mapped_column(Integer, ForeignKey("invite_codes.id"), index=True)
    user_email: Mapped[str] = mapped_column(String(200), index=True)
    ip_address: Mapped[str] = mapped_column(String(50), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
