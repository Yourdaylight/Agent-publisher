from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from agent_publisher.api.deps import get_db, get_current_user, UserContext
from agent_publisher.models.llm_profile import LLMProfile
from agent_publisher.models.agent import Agent
from agent_publisher.schemas.llm_profile import (
    LLMProfileCreate,
    LLMProfileOut,
    LLMProfileUpdate,
)

router = APIRouter(prefix="/api/llm-profiles", tags=["llm-profiles"])


def _require_admin(user: UserContext) -> None:
    if not user.is_admin:
        raise HTTPException(403, "Admin access required")


@router.get("", response_model=list[LLMProfileOut])
async def list_profiles(
    db: AsyncSession = Depends(get_db),
    user: UserContext = Depends(get_current_user),
):
    result = await db.execute(select(LLMProfile).order_by(LLMProfile.id))
    profiles = result.scalars().all()
    return [LLMProfileOut.from_orm_masked(p) for p in profiles]


@router.post("", response_model=LLMProfileOut)
async def create_profile(
    data: LLMProfileCreate,
    db: AsyncSession = Depends(get_db),
    user: UserContext = Depends(get_current_user),
):
    _require_admin(user)
    profile = LLMProfile(**data.model_dump())
    # If set as default, clear other defaults
    if profile.is_default:
        await _clear_defaults(db)
    db.add(profile)
    await db.commit()
    await db.refresh(profile)
    return LLMProfileOut.from_orm_masked(profile)


@router.put("/{profile_id}", response_model=LLMProfileOut)
async def update_profile(
    profile_id: int,
    data: LLMProfileUpdate,
    db: AsyncSession = Depends(get_db),
    user: UserContext = Depends(get_current_user),
):
    _require_admin(user)
    profile = await db.get(LLMProfile, profile_id)
    if not profile:
        raise HTTPException(404, "LLM Profile not found")
    update_data = data.model_dump(exclude_unset=True)
    # If setting as default, clear other defaults first
    if update_data.get("is_default"):
        await _clear_defaults(db)
    for key, value in update_data.items():
        setattr(profile, key, value)
    await db.commit()
    await db.refresh(profile)
    return LLMProfileOut.from_orm_masked(profile)


@router.delete("/{profile_id}")
async def delete_profile(
    profile_id: int,
    db: AsyncSession = Depends(get_db),
    user: UserContext = Depends(get_current_user),
):
    _require_admin(user)
    profile = await db.get(LLMProfile, profile_id)
    if not profile:
        raise HTTPException(404, "LLM Profile not found")
    # Check if any agent references this profile
    result = await db.execute(select(Agent.id).where(Agent.llm_profile_id == profile_id).limit(1))
    if result.scalar():
        raise HTTPException(
            400,
            "Cannot delete: this profile is referenced by one or more Agents. "
            "Please update those Agents first.",
        )
    await db.delete(profile)
    await db.commit()
    return {"message": "LLM Profile deleted"}


@router.post("/{profile_id}/set-default", response_model=LLMProfileOut)
async def set_default(
    profile_id: int,
    db: AsyncSession = Depends(get_db),
    user: UserContext = Depends(get_current_user),
):
    _require_admin(user)
    profile = await db.get(LLMProfile, profile_id)
    if not profile:
        raise HTTPException(404, "LLM Profile not found")
    await _clear_defaults(db)
    profile.is_default = True
    await db.commit()
    await db.refresh(profile)
    return LLMProfileOut.from_orm_masked(profile)


async def _clear_defaults(db: AsyncSession) -> None:
    """Clear is_default on all profiles."""
    result = await db.execute(
        select(LLMProfile).where(LLMProfile.is_default == True)  # noqa: E712
    )
    for p in result.scalars().all():
        p.is_default = False
