from __future__ import annotations

from collections.abc import AsyncGenerator
from dataclasses import dataclass

from fastapi import HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from agent_publisher.database import async_session_factory


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_factory() as session:
        yield session


@dataclass
class UserContext:
    """User identity extracted from the auth middleware."""

    email: str  # "__admin__" for access_key login, actual email for email login
    is_admin: bool


async def get_current_user(request: Request) -> UserContext:
    """Extract user identity from request.state (set by auth_middleware).

    The auth_middleware sets:
      - request.state.user_email: the authenticated user's email (or "__admin__" for access_key login)
      - request.state.is_admin: True if the user is an admin
    """
    email = getattr(request.state, "user_email", None)
    is_admin = getattr(request.state, "is_admin", False)
    if not email:
        raise HTTPException(status_code=401, detail="Authentication required")
    return UserContext(email=email, is_admin=is_admin)


def require_admin(user: UserContext) -> None:
    """Raise 403 if the user is not an admin."""
    if not user.is_admin:
        raise HTTPException(status_code=403, detail="Admin privileges required")


async def get_visible_emails(user: UserContext, db: AsyncSession) -> set[str]:
    """Return the set of owner emails whose articles the given user may see.

    - Admin: returns empty set (caller should treat as "no filter" / see everything)
    - Regular user: their own email + emails of all co-members across all groups they belong to
    """
    if user.is_admin:
        return set()  # signal: no restriction

    from agent_publisher.models.group import UserGroupMember

    # Find all groups the user belongs to
    group_result = await db.execute(
        select(UserGroupMember.group_id).where(UserGroupMember.email == user.email)
    )
    group_ids = [row[0] for row in group_result.all()]

    visible: set[str] = {user.email}
    if group_ids:
        member_result = await db.execute(
            select(UserGroupMember.email).where(UserGroupMember.group_id.in_(group_ids))
        )
        for (email,) in member_result.all():
            visible.add(email)

    return visible
