from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, JSON, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from agent_publisher.models.base import Base

# Valid values for the 'source_type' field
MATERIAL_SOURCE_TYPES = ("rss", "search", "skills_feed", "manual")

# Valid values for the 'status' field
MATERIAL_STATUSES = ("pending", "accepted", "rejected")


class CandidateMaterial(Base):
    __tablename__ = "candidate_materials"

    id: Mapped[int] = mapped_column(primary_key=True)
    # Source type: rss / search / skills_feed / manual
    source_type: Mapped[str] = mapped_column(String(50))
    # Source identity (e.g. agent name, skill identity, manual uploader)
    source_identity: Mapped[str] = mapped_column(String(200), default="")
    original_url: Mapped[str] = mapped_column(String(1000), default="")
    title: Mapped[str] = mapped_column(String(500))
    summary: Mapped[str] = mapped_column(Text, default="")
    raw_content: Mapped[str] = mapped_column(Text, default="")
    # JSON metadata: credibility, collection time, RSS feed name, etc.
    extra_metadata: Mapped[dict | None] = mapped_column(JSON, default=None, nullable=True)
    # Tags: unified JSON array for auto tags + custom tags
    tags: Mapped[list | None] = mapped_column(JSON, default=list)
    agent_id: Mapped[int | None] = mapped_column(ForeignKey("agents.id"), nullable=True)
    is_duplicate: Mapped[bool] = mapped_column(Boolean, default=False)
    quality_score: Mapped[float | None] = mapped_column(Float, default=None, nullable=True)
    # Status: pending / accepted / rejected
    status: Mapped[str] = mapped_column(String(20), default="pending")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    agent: Mapped["Agent"] = relationship(backref="candidate_materials")  # noqa: F821

    def __repr__(self) -> str:
        return f"<CandidateMaterial id={self.id} title={self.title!r} source_type={self.source_type!r}>"
