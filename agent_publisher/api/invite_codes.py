"""Admin CRUD API for invite codes."""

from __future__ import annotations

import logging
import random
import string
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from agent_publisher.api.deps import get_current_user, get_db, UserContext
from agent_publisher.models.invite_code import InviteCode, InviteRedemption

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/invite-codes", tags=["invite-codes"])


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class InviteCodeCreate(BaseModel):
    channel: str = "open"
    max_uses: int = 0
    bonus_credits: int = 100
    expires_at: datetime | None = None
    note: str = ""
    count: int = 1  # batch generate


class InviteCodeUpdate(BaseModel):
    channel: str | None = None
    max_uses: int | None = None
    bonus_credits: int | None = None
    expires_at: datetime | None = None
    is_active: bool | None = None
    note: str | None = None


def _generate_code(channel: str) -> str:
    """Generate invite code like AP-WECHAT-A3X7."""
    suffix = "".join(random.choices(string.ascii_uppercase + string.digits, k=4))
    return f"AP-{channel.upper()}-{suffix}"


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("")
async def list_invite_codes(
    db: AsyncSession = Depends(get_db),
    user: UserContext = Depends(get_current_user),
):
    """List all invite codes (admin only)."""
    if not user.is_admin:
        raise HTTPException(status_code=403, detail="需要管理员权限")
    result = await db.execute(select(InviteCode).order_by(InviteCode.id.desc()))
    codes = result.scalars().all()
    return [
        {
            "id": c.id,
            "code": c.code,
            "channel": c.channel,
            "max_uses": c.max_uses,
            "used_count": c.used_count,
            "bonus_credits": c.bonus_credits,
            "expires_at": c.expires_at.isoformat() if c.expires_at else None,
            "is_active": c.is_active,
            "created_by": c.created_by,
            "note": c.note,
            "created_at": c.created_at.isoformat() if c.created_at else None,
        }
        for c in codes
    ]


@router.post("")
async def create_invite_codes(
    req: InviteCodeCreate,
    db: AsyncSession = Depends(get_db),
    user: UserContext = Depends(get_current_user),
):
    """Create one or more invite codes (admin only)."""
    if not user.is_admin:
        raise HTTPException(status_code=403, detail="需要管理员权限")

    count = min(req.count, 100)  # max 100 at a time
    created = []
    for _ in range(count):
        # Ensure unique code
        for _attempt in range(10):
            code = _generate_code(req.channel)
            existing = await db.execute(select(InviteCode).where(InviteCode.code == code))
            if not existing.scalar_one_or_none():
                break
        else:
            raise HTTPException(status_code=500, detail="无法生成唯一邀请码，请重试")

        invite = InviteCode(
            code=code,
            channel=req.channel,
            max_uses=req.max_uses,
            bonus_credits=req.bonus_credits,
            expires_at=req.expires_at,
            created_by=user.email,
            note=req.note,
        )
        db.add(invite)
        created.append(code)

    await db.commit()
    return {"created": created, "count": len(created)}


@router.put("/{code_id}")
async def update_invite_code(
    code_id: int,
    req: InviteCodeUpdate,
    db: AsyncSession = Depends(get_db),
    user: UserContext = Depends(get_current_user),
):
    """Update an invite code (admin only)."""
    if not user.is_admin:
        raise HTTPException(status_code=403, detail="需要管理员权限")

    result = await db.execute(select(InviteCode).where(InviteCode.id == code_id))
    invite = result.scalar_one_or_none()
    if not invite:
        raise HTTPException(status_code=404, detail="邀请码不存在")

    for field, value in req.model_dump(exclude_unset=True).items():
        setattr(invite, field, value)
    await db.commit()
    return {"ok": True}


@router.delete("/{code_id}")
async def delete_invite_code(
    code_id: int,
    db: AsyncSession = Depends(get_db),
    user: UserContext = Depends(get_current_user),
):
    """Delete an invite code (admin only)."""
    if not user.is_admin:
        raise HTTPException(status_code=403, detail="需要管理员权限")

    result = await db.execute(select(InviteCode).where(InviteCode.id == code_id))
    invite = result.scalar_one_or_none()
    if not invite:
        raise HTTPException(status_code=404, detail="邀请码不存在")

    await db.delete(invite)
    await db.commit()
    return {"ok": True}


@router.get("/stats")
async def invite_stats(
    db: AsyncSession = Depends(get_db),
    user: UserContext = Depends(get_current_user),
):
    """Get invite code statistics (admin only)."""
    if not user.is_admin:
        raise HTTPException(status_code=403, detail="需要管理员权限")

    total_result = await db.execute(select(func.count()).select_from(InviteCode))
    total_codes = total_result.scalar() or 0

    active_result = await db.execute(
        select(func.count()).select_from(InviteCode).where(InviteCode.is_active)
    )
    active_codes = active_result.scalar() or 0

    total_redemptions_result = await db.execute(select(func.count()).select_from(InviteRedemption))
    total_redemptions = total_redemptions_result.scalar() or 0

    unique_users_result = await db.execute(
        select(func.count(func.distinct(InviteRedemption.user_email)))
    )
    unique_users = unique_users_result.scalar() or 0

    # Per-channel breakdown
    channel_result = await db.execute(
        select(InviteCode.channel, func.sum(InviteCode.used_count)).group_by(InviteCode.channel)
    )
    by_channel = {row[0]: row[1] or 0 for row in channel_result.all()}

    return {
        "total_codes": total_codes,
        "active_codes": active_codes,
        "total_redemptions": total_redemptions,
        "unique_users": unique_users,
        "by_channel": by_channel,
    }


@router.get("/{code_id}/redemptions")
async def get_redemptions(
    code_id: int,
    db: AsyncSession = Depends(get_db),
    user: UserContext = Depends(get_current_user),
):
    """Get redemption records for a specific invite code (admin only)."""
    if not user.is_admin:
        raise HTTPException(status_code=403, detail="需要管理员权限")

    result = await db.execute(
        select(InviteRedemption)
        .where(InviteRedemption.invite_code_id == code_id)
        .order_by(InviteRedemption.created_at.desc())
    )
    redemptions = result.scalars().all()
    return [
        {
            "id": r.id,
            "user_email": r.user_email,
            "ip_address": r.ip_address,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in redemptions
    ]
