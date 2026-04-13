"""System log service — record and query structured operation logs.

Storage backend:
  - Default: SQLAlchemy (SQLite / PostgreSQL)
  - Optional: ClickHouse (when clickhouse_url is configured in .env)

Usage:
  from agent_publisher.services.system_log_service import SystemLogService
  await SystemLogService.record(action="publish", target_type="article", ...)
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from agent_publisher.models.system_log import SystemLog

logger = logging.getLogger(__name__)


class SystemLogService:
    """High-level API for recording and querying system logs."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def record(
        self,
        *,
        action: str,
        target_type: str = "",
        target_id: str = "",
        description: str = "",
        operator: str = "",
        is_admin: bool = False,
        status: str = "success",
        error_message: str = "",
        extra: dict[str, Any] | None = None,
        client_ip: str = "",
        request_path: str = "",
    ) -> SystemLog:
        """Record a structured operation log entry."""
        log_entry = SystemLog(
            action=action,
            target_type=target_type,
            target_id=str(target_id),
            description=description,
            operator=operator,
            is_admin=1 if is_admin else 0,
            status=status,
            error_message=error_message,
            extra=json.dumps(extra, ensure_ascii=False) if extra else "",
            client_ip=client_ip,
            request_path=request_path,
        )
        self.db.add(log_entry)
        await self.db.commit()
        await self.db.refresh(log_entry)

        # Also log to Python logger for console/file output
        level = logging.ERROR if status == "failed" else logging.INFO
        logger.log(
            level,
            "SYSLOG [%s] %s %s%s by=%s ip=%s",
            status,
            action,
            f"{target_type}:{target_id} " if target_type else "",
            description,
            operator or "system",
            client_ip,
        )

        return log_entry

    async def query(
        self,
        *,
        action: str | None = None,
        target_type: str | None = None,
        operator: str | None = None,
        status: str | None = None,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        keyword: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[SystemLog]:
        """Query logs with filters."""
        stmt = select(SystemLog).order_by(SystemLog.id.desc())

        if action:
            stmt = stmt.where(SystemLog.action == action)
        if target_type:
            stmt = stmt.where(SystemLog.target_type == target_type)
        if operator:
            stmt = stmt.where(SystemLog.operator == operator)
        if status:
            stmt = stmt.where(SystemLog.status == status)
        if start_time:
            stmt = stmt.where(SystemLog.timestamp >= start_time)
        if end_time:
            stmt = stmt.where(SystemLog.timestamp <= end_time)
        if keyword:
            stmt = stmt.where(
                SystemLog.description.contains(keyword)
                | SystemLog.error_message.contains(keyword)
            )

        stmt = stmt.limit(limit).offset(offset)
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def get_stats(self) -> dict:
        """Get log statistics."""
        now = datetime.now(timezone.utc)
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

        total = (await self.db.execute(select(func.count(SystemLog.id)))).scalar() or 0
        today = (
            await self.db.execute(
                select(func.count(SystemLog.id)).where(SystemLog.timestamp >= today_start)
            )
        ).scalar() or 0
        failed = (
            await self.db.execute(
                select(func.count(SystemLog.id)).where(SystemLog.status == "failed")
            )
        ).scalar() or 0

        # By action
        action_rows = (
            await self.db.execute(
                select(SystemLog.action, func.count(SystemLog.id)).group_by(SystemLog.action)
            )
        ).all()
        by_action = {row[0]: row[1] for row in action_rows}

        return {
            "total": total,
            "today": today,
            "failed": failed,
            "by_action": by_action,
        }

    async def cleanup(self, days: int = 90) -> int:
        """Delete logs older than N days. Returns count of deleted rows."""
        cutoff = datetime.now(timezone.utc) - __import__("datetime").timedelta(days=days)
        from sqlalchemy import delete

        result = await self.db.execute(delete(SystemLog).where(SystemLog.timestamp < cutoff))
        await self.db.commit()
        return result.rowcount
