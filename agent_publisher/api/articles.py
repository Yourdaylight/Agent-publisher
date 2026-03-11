from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from agent_publisher.api.deps import get_db
from agent_publisher.models.article import Article
from agent_publisher.schemas.article import ArticleBrief, ArticleOut
from agent_publisher.services.article_service import ArticleService

router = APIRouter(prefix="/api/articles", tags=["articles"])


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
