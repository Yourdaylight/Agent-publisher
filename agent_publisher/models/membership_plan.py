from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, JSON, String, func
from sqlalchemy.orm import Mapped, mapped_column

from agent_publisher.models.base import Base


class MembershipPlan(Base):
    __tablename__ = "membership_plans"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    display_name: Mapped[str] = mapped_column(String(100))
    price_monthly: Mapped[float] = mapped_column(Float, default=0)
    price_yearly: Mapped[float] = mapped_column(Float, default=0)
    features: Mapped[dict | None] = mapped_column(JSON, default=dict)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    sort_order: Mapped[int] = mapped_column(default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    def __repr__(self) -> str:
        return f"<MembershipPlan name={self.name!r} display_name={self.display_name!r}>"
