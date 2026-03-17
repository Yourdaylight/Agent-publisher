from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from agent_publisher.api.deps import get_db, get_current_user, UserContext
from agent_publisher.models.account import Account
from agent_publisher.models.agent import Agent
from agent_publisher.models.article import Article
from agent_publisher.models.article_publish_relation import ArticlePublishRelation
from agent_publisher.models.publish_record import PublishRecord
from agent_publisher.schemas.article import (
    ArticleOut,
    ArticlePublishRequest,
    ArticlePublishResponse,
    ArticleSyncRequest,
    ArticleSyncResponse,
)
from agent_publisher.services.article_service import ArticleService
from agent_publisher.services.task_service import TaskService

router = APIRouter(prefix="/api/articles", tags=["articles"])


class ArticleUpdate(BaseModel):
    """Request body for updating an article."""
    title: str | None = None
    digest: str | None = None
    content: str | None = None
    html_content: str | None = None
    cover_image_url: str | None = None


class VariantGenerateRequest(BaseModel):
    """Request body for batch variant generation."""
    agent_ids: list[int]
    style_ids: list[str]


async def _get_article_with_ownership(
    article_id: int, user: UserContext, db: AsyncSession
) -> Article:
    """Fetch an article and verify ownership through Agent -> Account chain."""
    stmt = select(Article).where(Article.id == article_id).options(
        selectinload(Article.publish_relations).selectinload(
            ArticlePublishRelation.account
        ),
    )
    result = await db.execute(stmt)
    article = result.scalar_one_or_none()
    if not article:
        raise HTTPException(404, "Article not found")
    if not user.is_admin:
        agent = await db.get(Agent, article.agent_id)
        if not agent:
            raise HTTPException(404, "Agent not found")
        account = await db.get(Account, agent.account_id)
        if not account or account.owner_email != user.email:
            raise HTTPException(403, "Access denied")
    return article


@router.get("")
async def list_articles(
    agent_id: int | None = None,
    status: str | None = None,
    db: AsyncSession = Depends(get_db),
    user: UserContext = Depends(get_current_user),
):
    """List articles with publish_count, filtered by user ownership."""
    stmt = select(Article).order_by(Article.id.desc())
    if not user.is_admin:
        stmt = stmt.join(Agent).join(Account).where(Account.owner_email == user.email)
    if agent_id:
        stmt = stmt.where(Article.agent_id == agent_id)
    if status:
        stmt = stmt.where(Article.status == status)
    result = await db.execute(stmt)
    articles = result.scalars().all()

    # Batch fetch publish counts
    article_ids = [a.id for a in articles]
    publish_counts: dict[int, int] = {}
    if article_ids:
        count_stmt = (
            select(PublishRecord.article_id, func.count(PublishRecord.id))
            .where(PublishRecord.article_id.in_(article_ids))
            .group_by(PublishRecord.article_id)
        )
        count_result = await db.execute(count_stmt)
        publish_counts = dict(count_result.all())

    # Batch fetch variant counts
    variant_counts: dict[int, int] = {}
    if article_ids:
        variant_stmt = (
            select(Article.source_article_id, func.count(Article.id))
            .where(Article.source_article_id.in_(article_ids))
            .group_by(Article.source_article_id)
        )
        variant_result = await db.execute(variant_stmt)
        variant_counts = dict(variant_result.all())

    return [
        {
            "id": a.id,
            "agent_id": a.agent_id,
            "title": a.title,
            "digest": a.digest,
            "status": a.status,
            "created_at": a.created_at.isoformat() if a.created_at else None,
            "publish_count": publish_counts.get(a.id, 0),
            "source_article_id": a.source_article_id,
            "variant_style": a.variant_style,
            "variant_count": variant_counts.get(a.id, 0),
        }
        for a in articles
    ]


@router.get("/{article_id}", response_model=ArticleOut)
async def get_article(
    article_id: int,
    db: AsyncSession = Depends(get_db),
    user: UserContext = Depends(get_current_user),
):
    return await _get_article_with_ownership(article_id, user, db)


@router.post("/{article_id}/publish", response_model=ArticlePublishResponse)
async def publish_article(
    article_id: int,
    data: ArticlePublishRequest | None = None,
    db: AsyncSession = Depends(get_db),
    user: UserContext = Depends(get_current_user),
):
    await _get_article_with_ownership(article_id, user, db)
    article_svc = ArticleService(db)
    try:
        operator = user.email if not user.is_admin else "admin"
        return await article_svc.publish_article(
            article_id,
            operator=operator,
            target_account_ids=data.target_account_ids if data else None,
        )
    except ValueError as e:
        raise HTTPException(404, str(e))


@router.put("/{article_id}", response_model=ArticleOut)
async def update_article(
    article_id: int,
    data: ArticleUpdate,
    db: AsyncSession = Depends(get_db),
    user: UserContext = Depends(get_current_user),
):
    """Update article fields (title, digest, content, html_content, cover_image_url).

    When Markdown content is modified, html_content is automatically re-rendered
    via wenyan.
    """
    await _get_article_with_ownership(article_id, user, db)
    updates = data.model_dump(exclude_none=True)
    if not updates:
        raise HTTPException(400, "No fields to update")

    article_svc = ArticleService(db)
    try:
        await article_svc.update_article(article_id, updates)
        # Re-fetch with eager-loaded relations for response serialization
        return await _get_article_with_ownership(article_id, user, db)
    except ValueError as e:
        raise HTTPException(404, str(e))


@router.post("/{article_id}/sync", response_model=ArticleSyncResponse)
async def sync_article(
    article_id: int,
    data: ArticleSyncRequest | None = None,
    db: AsyncSession = Depends(get_db),
    user: UserContext = Depends(get_current_user),
):
    """Sync local article edits to WeChat draft box."""
    await _get_article_with_ownership(article_id, user, db)
    article_svc = ArticleService(db)
    try:
        operator = user.email if not user.is_admin else "admin"
        return await article_svc.sync_article_to_draft(
            article_id,
            operator=operator,
            target_account_ids=data.target_account_ids if data else None,
        )
    except ValueError as e:
        raise HTTPException(404, str(e))
    except RuntimeError as e:
        raise HTTPException(502, f"WeChat sync failed: {e}")


@router.get("/{article_id}/publish-records")
async def get_article_publish_records(
    article_id: int,
    db: AsyncSession = Depends(get_db),
    user: UserContext = Depends(get_current_user),
):
    """Get publish records for a specific article."""
    await _get_article_with_ownership(article_id, user, db)
    stmt = (
        select(PublishRecord)
        .where(PublishRecord.article_id == article_id)
        .order_by(PublishRecord.id.desc())
    )
    result = await db.execute(stmt)
    records = result.scalars().all()
    return [
        {
            "id": r.id,
            "article_id": r.article_id,
            "action": r.action,
            "wechat_media_id": r.wechat_media_id,
            "status": r.status,
            "operator": r.operator,
            "error_message": r.error_message,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in records
    ]


@router.post("/{article_id}/variants")
async def generate_variants(
    article_id: int,
    data: VariantGenerateRequest,
    db: AsyncSession = Depends(get_db),
    user: UserContext = Depends(get_current_user),
):
    """Initiate batch variant generation for an article."""
    await _get_article_with_ownership(article_id, user, db)

    if not data.style_ids:
        raise HTTPException(400, "At least one style_id is required")
    if not data.agent_ids:
        raise HTTPException(400, "At least one agent_id is required")

    task_svc = TaskService(db)
    try:
        task = await task_svc.run_batch_variants(
            source_article_id=article_id,
            agent_ids=data.agent_ids,
            style_ids=data.style_ids,
        )
    except ValueError as e:
        raise HTTPException(400, str(e))

    return {"ok": True, "batch_task_id": task.id, "total": len(data.agent_ids)}


@router.get("/{article_id}/variants")
async def list_article_variants(
    article_id: int,
    db: AsyncSession = Depends(get_db),
    user: UserContext = Depends(get_current_user),
):
    """List all variant articles derived from the given source article."""
    await _get_article_with_ownership(article_id, user, db)

    from agent_publisher.models.agent import Agent

    stmt = (
        select(Article)
        .where(Article.source_article_id == article_id)
        .order_by(Article.id.desc())
    )
    result = await db.execute(stmt)
    variants = result.scalars().all()

    # Batch-load agent names
    agent_ids = list({v.agent_id for v in variants})
    agent_names: dict[int, str] = {}
    if agent_ids:
        agent_result = await db.execute(
            select(Agent.id, Agent.name).where(Agent.id.in_(agent_ids))
        )
        agent_names = dict(agent_result.all())

    return [
        {
            "id": v.id,
            "agent_id": v.agent_id,
            "agent_name": agent_names.get(v.agent_id, ""),
            "title": v.title,
            "digest": v.digest,
            "status": v.status,
            "variant_style": v.variant_style,
            "created_at": v.created_at.isoformat() if v.created_at else None,
        }
        for v in variants
    ]
