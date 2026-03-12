"""Publish Records admin API."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from agent_publisher.api.deps import get_db
from agent_publisher.models.article import Article
from agent_publisher.models.publish_record import PublishRecord
from agent_publisher.schemas.publish_record import PublishRecordOut

router = APIRouter(prefix="/api/publish-records", tags=["publish-records"])


@router.get("", response_model=list[PublishRecordOut])
async def list_publish_records(
    article_id: int | None = None,
    action: str | None = None,
    status: str | None = None,
    limit: int = 50,
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
):
    """List publish records with optional filters."""
    stmt = select(PublishRecord).order_by(PublishRecord.id.desc())
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
async def publish_stats(db: AsyncSession = Depends(get_db)):
    """Get publish stats summary."""
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
    return {
        "total": total,
        "success": success,
        "failed": failed,
        "publishes": publishes,
        "syncs": syncs,
    }


@router.get("/{record_id}", response_model=PublishRecordOut)
async def get_publish_record(record_id: int, db: AsyncSession = Depends(get_db)):
    """Get a single publish record."""
    record = await db.get(PublishRecord, record_id)
    if not record:
        raise HTTPException(404, "Publish record not found")
    return record
