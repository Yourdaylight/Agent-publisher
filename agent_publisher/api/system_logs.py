"""System logs API — query and manage structured operation logs."""
from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from agent_publisher.api.deps import get_db, get_current_user, require_admin, UserContext
from agent_publisher.models.system_log import SystemLog
from agent_publisher.schemas.system_log import SystemLogOut, SystemLogStats
from agent_publisher.services.system_log_service import SystemLogService

router = APIRouter(prefix="/api/system-logs", tags=["system-logs"])


async def _require_admin_user(user: UserContext = Depends(get_current_user)) -> UserContext:
    """Only admins can access system logs."""
    require_admin(user)
    return user


@router.get("", response_model=list[SystemLogOut])
async def list_logs(
    action: str | None = None,
    target_type: str | None = None,
    operator: str | None = None,
    status: str | None = None,
    keyword: str | None = None,
    start_time: datetime | None = None,
    end_time: datetime | None = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    _: UserContext = Depends(_require_admin_user),
):
    """Query system logs with filters. Admin only."""
    svc = SystemLogService(db)
    return await svc.query(
        action=action,
        target_type=target_type,
        operator=operator,
        status=status,
        start_time=start_time,
        end_time=end_time,
        keyword=keyword,
        limit=limit,
        offset=offset,
    )


@router.get("/stats", response_model=SystemLogStats)
async def get_log_stats(
    db: AsyncSession = Depends(get_db),
    _: UserContext = Depends(_require_admin_user),
):
    """Get system log statistics. Admin only."""
    svc = SystemLogService(db)
    stats = await svc.get_stats()
    return SystemLogStats(**stats)


@router.delete("/cleanup")
async def cleanup_logs(
    days: int = Query(90, ge=1, description="Delete logs older than N days"),
    db: AsyncSession = Depends(get_db),
    _: UserContext = Depends(_require_admin_user),
):
    """Delete logs older than N days. Admin only."""
    svc = SystemLogService(db)
    deleted = await svc.cleanup(days=days)
    return {"deleted": deleted, "message": f"已清理 {deleted} 条超过 {days} 天的日志"}
