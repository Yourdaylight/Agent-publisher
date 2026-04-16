from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from agent_publisher.api.deps import UserContext, get_current_user, get_db
from agent_publisher.models.user_preference import UserPreference

router = APIRouter(prefix="/api/user", tags=["preferences"])


class PreferenceBody(BaseModel):
    interest_keywords: list[str] = []
    preferred_platforms: list[str] = []
    blocked_keywords: list[str] = []


class PreferenceOut(BaseModel):
    interest_keywords: list[str]
    preferred_platforms: list[str]
    blocked_keywords: list[str]


@router.get("/preferences", response_model=PreferenceOut)
async def get_preferences(
    db: AsyncSession = Depends(get_db),
    user: UserContext = Depends(get_current_user),
):
    """Return the current user's preference (or empty defaults)."""
    result = await db.execute(
        select(UserPreference).where(UserPreference.user_email == user.email)
    )
    pref = result.scalar_one_or_none()
    if not pref:
        return PreferenceOut(interest_keywords=[], preferred_platforms=[], blocked_keywords=[])
    return PreferenceOut(
        interest_keywords=pref.interest_keywords or [],
        preferred_platforms=pref.preferred_platforms or [],
        blocked_keywords=pref.blocked_keywords or [],
    )


@router.put("/preferences", response_model=PreferenceOut)
async def save_preferences(
    data: PreferenceBody,
    db: AsyncSession = Depends(get_db),
    user: UserContext = Depends(get_current_user),
):
    """Create or update the current user's preference."""
    result = await db.execute(
        select(UserPreference).where(UserPreference.user_email == user.email)
    )
    pref = result.scalar_one_or_none()
    if pref:
        pref.interest_keywords = data.interest_keywords
        pref.preferred_platforms = data.preferred_platforms
        pref.blocked_keywords = data.blocked_keywords
    else:
        pref = UserPreference(
            user_email=user.email,
            interest_keywords=data.interest_keywords,
            preferred_platforms=data.preferred_platforms,
            blocked_keywords=data.blocked_keywords,
        )
        db.add(pref)
    await db.commit()
    await db.refresh(pref)
    return PreferenceOut(
        interest_keywords=pref.interest_keywords or [],
        preferred_platforms=pref.preferred_platforms or [],
        blocked_keywords=pref.blocked_keywords or [],
    )
