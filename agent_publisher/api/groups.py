"""User Group API: manage permission groups (admin only)."""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, field_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from agent_publisher.api.deps import get_db, get_current_user, require_admin, UserContext
from agent_publisher.models.group import UserGroup, UserGroupMember

router = APIRouter(prefix="/api/groups", tags=["groups"])


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class GroupCreate(BaseModel):
    name: str
    description: str = ""

    @field_validator("name")
    @classmethod
    def name_not_empty(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Group name must not be empty")
        return v


class GroupUpdate(BaseModel):
    name: str | None = None
    description: str | None = None


class MemberAdd(BaseModel):
    email: str

    @field_validator("email")
    @classmethod
    def lower_email(cls, v: str) -> str:
        return v.strip().lower()


class GroupMemberOut(BaseModel):
    id: int
    group_id: int
    email: str
    added_at: datetime

    model_config = {"from_attributes": True}


class GroupOut(BaseModel):
    id: int
    name: str
    description: str
    created_by: str
    created_at: datetime
    members: list[GroupMemberOut] = []

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _get_group(group_id: int, db: AsyncSession) -> UserGroup:
    result = await db.execute(
        select(UserGroup).where(UserGroup.id == group_id).options(selectinload(UserGroup.members))
    )
    group = result.scalar_one_or_none()
    if not group:
        raise HTTPException(404, "Group not found")
    return group


# ---------------------------------------------------------------------------
# Endpoints (admin-only write, any authenticated user can read their own groups)
# ---------------------------------------------------------------------------


@router.get("", response_model=list[GroupOut])
async def list_groups(
    db: AsyncSession = Depends(get_db),
    user: UserContext = Depends(get_current_user),
):
    """List groups. Admin sees all; regular users see only groups they belong to."""
    stmt = select(UserGroup).options(selectinload(UserGroup.members)).order_by(UserGroup.id)
    result = await db.execute(stmt)
    groups = result.scalars().all()
    if user.is_admin:
        return groups
    # Regular users only see groups they are a member of
    return [g for g in groups if any(m.email == user.email for m in g.members)]


@router.post("", response_model=GroupOut)
async def create_group(
    data: GroupCreate,
    db: AsyncSession = Depends(get_db),
    user: UserContext = Depends(get_current_user),
):
    """Create a new permission group. Admin only."""
    require_admin(user)
    # Check duplicate name
    existing = await db.execute(select(UserGroup).where(UserGroup.name == data.name))
    if existing.scalar_one_or_none():
        raise HTTPException(409, f"Group '{data.name}' already exists")

    group = UserGroup(
        name=data.name,
        description=data.description,
        created_by=user.email,
    )
    db.add(group)
    await db.commit()
    await db.refresh(group)
    # Reload with members
    return await _get_group(group.id, db)


@router.get("/{group_id}", response_model=GroupOut)
async def get_group(
    group_id: int,
    db: AsyncSession = Depends(get_db),
    user: UserContext = Depends(get_current_user),
):
    """Get a group by ID."""
    group = await _get_group(group_id, db)
    # Non-admin can only view groups they belong to
    if not user.is_admin and not any(m.email == user.email for m in group.members):
        raise HTTPException(403, "Access denied")
    return group


@router.put("/{group_id}", response_model=GroupOut)
async def update_group(
    group_id: int,
    data: GroupUpdate,
    db: AsyncSession = Depends(get_db),
    user: UserContext = Depends(get_current_user),
):
    """Update a group's name or description. Admin only."""
    require_admin(user)
    group = await _get_group(group_id, db)
    if data.name is not None:
        data.name = data.name.strip()
        if not data.name:
            raise HTTPException(400, "Group name must not be empty")
        # Check name collision (excluding self)
        dup = await db.execute(
            select(UserGroup).where(UserGroup.name == data.name, UserGroup.id != group_id)
        )
        if dup.scalar_one_or_none():
            raise HTTPException(409, f"Group '{data.name}' already exists")
        group.name = data.name
    if data.description is not None:
        group.description = data.description
    await db.commit()
    return await _get_group(group_id, db)


@router.delete("/{group_id}")
async def delete_group(
    group_id: int,
    db: AsyncSession = Depends(get_db),
    user: UserContext = Depends(get_current_user),
):
    """Delete a group and all its memberships. Admin only."""
    require_admin(user)
    group = await _get_group(group_id, db)
    await db.delete(group)
    await db.commit()
    return {"ok": True}


@router.post("/{group_id}/members", response_model=GroupMemberOut)
async def add_member(
    group_id: int,
    data: MemberAdd,
    db: AsyncSession = Depends(get_db),
    user: UserContext = Depends(get_current_user),
):
    """Add a user email to a group. Admin only."""
    require_admin(user)
    await _get_group(group_id, db)  # existence check

    # Duplicate check
    dup = await db.execute(
        select(UserGroupMember).where(
            UserGroupMember.group_id == group_id,
            UserGroupMember.email == data.email,
        )
    )
    if dup.scalar_one_or_none():
        raise HTTPException(409, f"'{data.email}' is already a member of this group")

    member = UserGroupMember(group_id=group_id, email=data.email)
    db.add(member)
    await db.commit()
    await db.refresh(member)
    return member


@router.delete("/{group_id}/members/{email}")
async def remove_member(
    group_id: int,
    email: str,
    db: AsyncSession = Depends(get_db),
    user: UserContext = Depends(get_current_user),
):
    """Remove a user email from a group. Admin only."""
    require_admin(user)
    email = email.strip().lower()
    result = await db.execute(
        select(UserGroupMember).where(
            UserGroupMember.group_id == group_id,
            UserGroupMember.email == email,
        )
    )
    member = result.scalar_one_or_none()
    if not member:
        raise HTTPException(404, f"'{email}' is not a member of this group")
    await db.delete(member)
    await db.commit()
    return {"ok": True}
