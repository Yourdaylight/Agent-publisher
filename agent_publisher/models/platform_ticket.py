"""PlatformTicket model — stores the component_verify_ticket pushed by WeChat."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column

from agent_publisher.models.base import Base


class PlatformTicket(Base):
    __tablename__ = "platform_tickets"

    id: Mapped[int] = mapped_column(primary_key=True)
    ticket: Mapped[str] = mapped_column(String(200))
    received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    def __repr__(self) -> str:
        return f"<PlatformTicket id={self.id} received_at={self.received_at!r}>"
