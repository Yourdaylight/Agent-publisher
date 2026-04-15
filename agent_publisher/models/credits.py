"""Credits balance and transaction models for the Credits billing system."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from agent_publisher.models.base import Base


class CreditsBalance(Base):
    """Per-user credits balance."""

    __tablename__ = "credits_balance"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_email: Mapped[str] = mapped_column(String(200), unique=True, index=True)
    total_credits: Mapped[int] = mapped_column(Integer, default=0)
    used_credits: Mapped[int] = mapped_column(Integer, default=0)
    free_credits: Mapped[int] = mapped_column(Integer, default=50)  # Monthly free quota
    paid_credits: Mapped[int] = mapped_column(Integer, default=0)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    @property
    def available(self) -> int:
        return self.free_credits + self.paid_credits - self.used_credits


class CreditsTransaction(Base):
    """Individual credits consumption / recharge record."""

    __tablename__ = "credits_transaction"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_email: Mapped[str] = mapped_column(String(200), index=True)
    operation_type: Mapped[str] = mapped_column(
        String(50)
    )  # generate_article, generate_image, rewrite, recharge, etc.
    credits_amount: Mapped[int] = mapped_column(Integer)  # negative=consume, positive=recharge
    balance_after: Mapped[int] = mapped_column(Integer)
    reference_id: Mapped[int | None] = mapped_column(
        Integer, nullable=True, default=None
    )  # article_id / image_id etc.
    description: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
