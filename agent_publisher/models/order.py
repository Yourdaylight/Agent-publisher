from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Float, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from agent_publisher.models.base import Base


class Order(Base):
    __tablename__ = "orders"

    id: Mapped[int] = mapped_column(primary_key=True)
    order_no: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    user_email: Mapped[str] = mapped_column(String(200), index=True)
    plan_id: Mapped[int] = mapped_column(ForeignKey("membership_plans.id"))
    amount: Mapped[float] = mapped_column(Float, default=0)
    status: Mapped[str] = mapped_column(String(20), default="pending")
    payment_method: Mapped[str | None] = mapped_column(String(50), nullable=True, default="manual")
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    plan: Mapped["MembershipPlan"] = relationship()  # noqa: F821

    def __repr__(self) -> str:
        return f"<Order order_no={self.order_no!r} status={self.status!r}>"
