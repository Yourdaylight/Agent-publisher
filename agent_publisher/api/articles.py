from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from agent_publisher.api.deps import get_db
from agent_publisher.models.article import Article
from agent_publisher.schemas.article import ArticleBrief, ArticleOut
from agent_publisher.services.article_service import ArticleService

router = APIRouter(prefix="/api/articles", tags=["articles"])


class ArticleUpdate(BaseModel):
    """Request body for updating an article."""
    title: str | None = None
    digest: str | None = None
    content: str | None = None
    html_content: str | None = None
    cover_image_url: str | None = None


@router.get("", response_model=list[ArticleBrief])
async def list_articles(
    agent_id: int | None = None,
    status: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    stmt = select(Article).order_by(Article.id.desc())
    if agent_id:
        stmt = stmt.where(Article.agent_id == agent_id)
    if status:
        stmt = stmt.where(Article.status == status)
    result = await db.execute(stmt)
    return result.scalars().all()


@router.get("/{article_id}", response_model=ArticleOut)
async def get_article(article_id: int, db: AsyncSession = Depends(get_db)):
    article = await db.get(Article, article_id)
    if not article:
        raise HTTPException(404, "Article not found")
    return article


@router.post("/{article_id}/publish")
async def publish_article(article_id: int, db: AsyncSession = Depends(get_db)):
    article_svc = ArticleService(db)
    try:
        media_id = await article_svc.publish_article(article_id)
        return {"ok": True, "media_id": media_id}
    except ValueError as e:
        raise HTTPException(404, str(e))


@router.put("/{article_id}", response_model=ArticleOut)
async def update_article(
    article_id: int,
    data: ArticleUpdate,
    db: AsyncSession = Depends(get_db),
):
    """Update article fields (title, digest, content, html_content, cover_image_url).

    When Markdown content is modified, html_content is automatically re-rendered
    via wenyan.
    """
    updates = data.model_dump(exclude_none=True)
    if not updates:
        raise HTTPException(400, "No fields to update")

    article_svc = ArticleService(db)
    try:
        updated = await article_svc.update_article(article_id, updates)
        return updated
    except ValueError as e:
        raise HTTPException(404, str(e))


@router.post("/{article_id}/sync")
async def sync_article(article_id: int, db: AsyncSession = Depends(get_db)):
    """Sync local article edits to WeChat draft box."""
    article_svc = ArticleService(db)
    try:
        status = await article_svc.sync_article_to_draft(article_id)
        return {"ok": True, "sync_status": status}
    except ValueError as e:
        raise HTTPException(404, str(e))
    except RuntimeError as e:
        raise HTTPException(502, f"WeChat sync failed: {e}")
