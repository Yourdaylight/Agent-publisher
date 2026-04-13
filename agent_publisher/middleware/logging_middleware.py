"""Logging middleware — automatically records API operations to system_logs table.

Records write operations (POST/PUT/PATCH/DELETE) with operator info extracted
from the auth middleware. Read operations (GET) are not logged to avoid noise.
"""
from __future__ import annotations

import logging
import time
from typing import Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger(__name__)

# Paths to skip (high-frequency, internal, or public)
SKIP_PREFIXES = (
    "/api/auth/login",
    "/api/auth/verify",
    "/api/auth/me",
    "/api/version",
    "/api/server-info",
    "/api/stats",
    "/api/system-logs",  # Don't log the log queries themselves
    "/api/tasks/",       # SSE streams
    "/api/extensions/",  # Extension polling
    "/assets/",
    "/favicon.ico",
)

# Map HTTP method + path prefix to (action, target_type)
ACTION_MAP: list[tuple[str, str, str, str]] = [
    # (method, path_prefix, action, target_type)
    ("POST", "/api/accounts", "create", "account"),
    ("PUT", "/api/accounts", "update", "account"),
    ("DELETE", "/api/accounts", "delete", "account"),
    ("POST", "/api/agents", "create", "agent"),
    ("PUT", "/api/agents", "update", "agent"),
    ("DELETE", "/api/agents", "delete", "agent"),
    ("POST", "/api/agents/", "generate", "agent"),  # /agents/{id}/generate
    ("POST", "/api/articles", "create", "article"),
    ("PUT", "/api/articles", "update", "article"),
    ("DELETE", "/api/articles", "delete", "article"),
    ("POST", "/api/articles/", "publish", "article"),
    ("POST", "/api/articles/", "sync", "article"),
    ("POST", "/api/sources", "create", "source"),
    ("PUT", "/api/sources", "update", "source"),
    ("DELETE", "/api/sources", "delete", "source"),
    ("POST", "/api/sources/", "collect", "source"),
    ("PUT", "/api/settings", "update", "settings"),
    ("PUT", "/api/settings/", "update", "settings"),
    ("POST", "/api/tasks/batch", "generate", "task"),
    ("POST", "/api/media", "create", "media"),
    ("DELETE", "/api/media/", "delete", "media"),
    ("POST", "/api/hotspots/", "generate", "article"),
    ("POST", "/api/invite-codes", "create", "invite_code"),
    ("PUT", "/api/invite-codes", "update", "invite_code"),
    ("DELETE", "/api/invite-codes", "delete", "invite_code"),
    ("POST", "/api/groups", "create", "group"),
    ("PUT", "/api/groups", "update", "group"),
    ("DELETE", "/api/groups", "delete", "group"),
    ("POST", "/api/groups/", "add_member", "group"),
    ("DELETE", "/api/groups/", "remove_member", "group"),
    ("POST", "/api/llm-profiles", "create", "llm_profile"),
    ("PUT", "/api/llm-profiles", "update", "llm_profile"),
    ("DELETE", "/api/llm-profiles", "delete", "llm_profile"),
    ("POST", "/api/prompts", "create", "prompt"),
    ("PUT", "/api/prompts", "update", "prompt"),
    ("DELETE", "/api/prompts", "delete", "prompt"),
    ("POST", "/api/style-presets", "create", "style_preset"),
    ("PUT", "/api/style-presets", "update", "style_preset"),
    ("DELETE", "/api/style-presets", "delete", "style_preset"),
    ("POST", "/api/credits/", "consume", "credits"),
    ("POST", "/api/membership/", "create", "order"),
    ("POST", "/api/wechat-platform/auth-url", "auth_scan", "account"),
]


def _match_action(method: str, path: str) -> tuple[str, str]:
    """Match request to (action, target_type)."""
    for m, prefix, action, target_type in ACTION_MAP:
        if method == m and path.startswith(prefix):
            return action, target_type
    return "", ""


class SystemLogMiddleware(BaseHTTPMiddleware):
    """Middleware that records write API operations as system logs."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Skip non-API and GET requests
        method = request.method
        path = request.url.path

        if method == "GET" or not path.startswith("/api/"):
            return await call_next(request)

        # Skip high-frequency / internal paths
        if any(path.startswith(p) for p in SKIP_PREFIXES):
            return await call_next(request)

        # Match action
        action, target_type = _match_action(method, path)
        if not action:
            return await call_next(request)

        # Execute request
        start_time = time.monotonic()
        response = await call_next(request)
        duration_ms = int((time.monotonic() - start_time) * 1000)

        # Only log if we have user info (from auth middleware)
        user_email = getattr(request.state, "user_email", None)
        is_admin = getattr(request.state, "is_admin", False)

        if not user_email:
            return response

        # Determine status
        status_code = response.status_code
        log_status = "success" if 200 <= status_code < 400 else "failed"

        # Build description
        description = _build_description(action, target_type, method, path)

        # Extract target_id from path (e.g., /api/accounts/123 -> 123)
        target_id = _extract_target_id(path, target_type)

        # Get client IP
        client_ip = request.client.host if request.client else ""
        forwarded = request.headers.get("x-forwarded-for", "")
        if forwarded:
            client_ip = forwarded.split(",")[0].strip()

        # Record log asynchronously (non-blocking)
        try:
            from agent_publisher.database import async_session_factory
            from agent_publisher.services.system_log_service import SystemLogService

            async with async_session_factory() as session:
                svc = SystemLogService(session)
                await svc.record(
                    action=action,
                    target_type=target_type,
                    target_id=target_id,
                    description=description,
                    operator=user_email or "system",
                    is_admin=is_admin,
                    status=log_status,
                    error_message="" if log_status == "success" else f"HTTP {status_code}",
                    extra={"duration_ms": duration_ms},
                    client_ip=client_ip,
                    request_path=path,
                )
        except Exception as e:
            # Never fail the request because of logging errors
            logger.warning("Failed to record system log: %s", e)

        return response


def _build_description(action: str, target_type: str, method: str, path: str) -> str:
    """Build a human-readable description for the log entry."""
    action_names = {
        "create": "创建", "update": "更新", "delete": "删除",
        "publish": "发布", "sync": "同步", "generate": "生成",
        "auth_scan": "扫码授权", "collect": "采集", "consume": "消耗",
        "add_member": "添加成员", "remove_member": "移除成员",
    }
    target_names = {
        "account": "公众号", "agent": "Agent", "article": "文章",
        "source": "数据源", "settings": "配置", "task": "任务",
        "media": "素材", "invite_code": "邀请码", "group": "权限组",
        "llm_profile": "LLM 配置", "prompt": "提示词", "style_preset": "风格预设",
        "credits": "Credits", "order": "订单",
    }

    act_text = action_names.get(action, action)
    tgt_text = target_names.get(target_type, target_type)

    return f"{act_text}{tgt_text}"


def _extract_target_id(path: str, target_type: str) -> str:
    """Extract target ID from URL path like /api/accounts/123.

    For POST requests creating new resources, the ID isn't in the URL.
    We return empty and let the detail be in the description.
    """
    parts = path.rstrip("/").split("/")
    # Look for numeric parts (not the port-like segments)
    for part in reversed(parts):
        if part.isdigit():
            return part
    # Try UUID-like segments
    import re
    uuid_pattern = re.compile(r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$', re.I)
    for part in reversed(parts):
        if uuid_pattern.match(part):
            return part
    return ""
