"""Publish Records admin API."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from agent_publisher.api.deps import get_db, get_current_user, UserContext
from agent_publisher.models.account import Account
from agent_publisher.models.agent import Agent
from agent_publisher.models.article import Article
from agent_publisher.models.publish_record import PublishRecord
from agent_publisher.schemas.publish_record import PublishRecordOut

router = APIRouter(prefix="/api/publish-records", tags=["publish-records"])


def _user_publish_record_filter(user: UserContext):
    """Build a subquery for filtering publish records by user ownership.

    Chain: PublishRecord -> Article -> Agent -> Account.owner_email
    """
    if user.is_admin:
        return None
    return (
        select(PublishRecord.id)
        .join(Article, PublishRecord.article_id == Article.id)
        .join(Agent, Article.agent_id == Agent.id)
        .join(Account, Agent.account_id == Account.id)
        .where(Account.owner_email == user.email)
    ).scalar_subquery()


@router.get("", response_model=list[PublishRecordOut])
async def list_publish_records(
    article_id: int | None = None,
    action: str | None = None,
    status: str | None = None,
    limit: int = 50,
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
    user: UserContext = Depends(get_current_user),
):
    """List publish records with optional filters."""
    stmt = select(PublishRecord).order_by(PublishRecord.id.desc())
    if not user.is_admin:
        stmt = (
            stmt.join(Article, PublishRecord.article_id == Article.id)
            .join(Agent, Article.agent_id == Agent.id)
            .join(Account, Agent.account_id == Account.id)
            .where(Account.owner_email == user.email)
        )
    if article_id:
        stmt = stmt.where(PublishRecord.article_id == article_id)
    if action:
        stmt = stmt.where(PublishRecord.action == action)
    if status:
        stmt = stmt.where(PublishRecord.status == status)
    stmt = stmt.offset(offset).limit(limit)
    result = await db.execute(stmt)
    return result.scalars().all()


@router.get("/stats")
async def publish_stats(
    db: AsyncSession = Depends(get_db),
    user: UserContext = Depends(get_current_user),
):
    """Get publish stats summary."""
    if user.is_admin:
        total = (await db.execute(select(func.count(PublishRecord.id)))).scalar() or 0
        success = (
            await db.execute(
                select(func.count(PublishRecord.id)).where(PublishRecord.status == "success")
            )
        ).scalar() or 0
        failed = (
            await db.execute(
                select(func.count(PublishRecord.id)).where(PublishRecord.status == "failed")
            )
        ).scalar() or 0
        publishes = (
            await db.execute(
                select(func.count(PublishRecord.id)).where(PublishRecord.action == "publish")
            )
        ).scalar() or 0
        syncs = (
            await db.execute(
                select(func.count(PublishRecord.id)).where(PublishRecord.action == "sync")
            )
        ).scalar() or 0
    else:
        # Filter by user ownership chain
        base = (
            select(func.count(PublishRecord.id))
            .join(Article, PublishRecord.article_id == Article.id)
            .join(Agent, Article.agent_id == Agent.id)
            .join(Account, Agent.account_id == Account.id)
            .where(Account.owner_email == user.email)
        )
        total = (await db.execute(base)).scalar() or 0
        success = (await db.execute(base.where(PublishRecord.status == "success"))).scalar() or 0
        failed = (await db.execute(base.where(PublishRecord.status == "failed"))).scalar() or 0
        publishes = (await db.execute(base.where(PublishRecord.action == "publish"))).scalar() or 0
        syncs = (await db.execute(base.where(PublishRecord.action == "sync"))).scalar() or 0

    return {
        "total": total,
        "success": success,
        "failed": failed,
        "publishes": publishes,
        "syncs": syncs,
    }


@router.get("/{record_id}", response_model=PublishRecordOut)
async def get_publish_record(
    record_id: int,
    db: AsyncSession = Depends(get_db),
    user: UserContext = Depends(get_current_user),
):
    """Get a single publish record."""
    record = await db.get(PublishRecord, record_id)
    if not record:
        raise HTTPException(404, "Publish record not found")
    # Check ownership through Article -> Agent -> Account chain
    if not user.is_admin:
        article = await db.get(Article, record.article_id)
        if article:
            agent = await db.get(Agent, article.agent_id)
            if agent:
                account = await db.get(Account, agent.account_id)
                if not account or account.owner_email != user.email:
                    raise HTTPException(403, "Access denied")
    return record
