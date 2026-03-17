from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, JSON, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from agent_publisher.models.base import Base


class Article(Base):
    __tablename__ = "articles"

    id: Mapped[int] = mapped_column(primary_key=True)
    agent_id: Mapped[int] = mapped_column(ForeignKey("agents.id"))
    title: Mapped[str] = mapped_column(String(200))
    digest: Mapped[str] = mapped_column(String(500), default="")
    content: Mapped[str] = mapped_column(Text, default="")
    html_content: Mapped[str] = mapped_column(Text, default="")
    cover_image_url: Mapped[str] = mapped_column(String(500), default="")
    images: Mapped[list | None] = mapped_column(JSON, default=list)
    source_news: Mapped[list | None] = mapped_column(JSON, default=list)
    status: Mapped[str] = mapped_column(String(20), default="draft")
    wechat_media_id: Mapped[str] = mapped_column(String(200), default="")
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # Variant relationship fields
    source_article_id: Mapped[int | None] = mapped_column(
        ForeignKey("articles.id"), nullable=True, default=None
    )
    variant_style: Mapped[str | None] = mapped_column(String(50), nullable=True, default=None)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    agent: Mapped["Agent"] = relationship(back_populates="articles")  # noqa: F821
    publish_records: Mapped[list["PublishRecord"]] = relationship(  # noqa: F821
        back_populates="article", order_by="PublishRecord.id.desc()"
    )
    publish_relations: Mapped[list["ArticlePublishRelation"]] = relationship(  # noqa: F821
        back_populates="article",
        order_by="ArticlePublishRelation.id.desc()",
    )
    # Self-referencing relationships for variant tracking
    source_article: Mapped["Article | None"] = relationship(
        back_populates="variants",
        remote_side="Article.id",
    )
    variants: Mapped[list["Article"]] = relationship(
        back_populates="source_article",
    )

    def __repr__(self) -> str:
        return f"<Article id={self.id} title={self.title!r} status={self.status}>"
