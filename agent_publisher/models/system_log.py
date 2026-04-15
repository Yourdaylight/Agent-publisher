"""System operation log model.

Stores structured operation logs for audit and debugging.
Supports both SQLite (default) and ClickHouse (when configured).
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from agent_publisher.models.base import Base


class SystemLog(Base):
    __tablename__ = "system_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )
    # 操作类型: login, publish, sync, create, update, delete, generate, error, system
    action: Mapped[str] = mapped_column(String(50), index=True)
    # 操作目标类型: account, agent, article, source, task, settings, material, etc.
    target_type: Mapped[str] = mapped_column(String(50), default="")
    # 操作目标 ID
    target_id: Mapped[str] = mapped_column(String(100), default="")
    # 操作描述（人类可读）
    description: Mapped[str] = mapped_column(String(500), default="")
    # 操作人邮箱
    operator: Mapped[str] = mapped_column(String(200), default="", index=True)
    # 操作人是否管理员
    is_admin: Mapped[bool] = mapped_column(Integer, default=0)
    # 状态: success / failed
    status: Mapped[str] = mapped_column(String(20), default="success", index=True)
    # 错误信息（仅在 failed 时有值）
    error_message: Mapped[str] = mapped_column(Text, default="")
    # 附加详情 JSON
    extra: Mapped[str] = mapped_column(Text, default="")
    # 客户端 IP
    client_ip: Mapped[str] = mapped_column(String(50), default="")
    # 请求路径
    request_path: Mapped[str] = mapped_column(String(500), default="")

    def __repr__(self) -> str:
        return f"<SystemLog id={self.id} action={self.action!r} operator={self.operator!r}>"
