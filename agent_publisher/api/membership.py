from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from agent_publisher.api.deps import UserContext, get_current_user, get_db, require_admin
from agent_publisher.services.membership_service import MembershipService

router = APIRouter(prefix="/api/membership", tags=["membership"])


class CreateOrderRequest(BaseModel):
    plan_name: str


class ManualActivationRequest(BaseModel):
    user_email: str
    plan_name: str
    duration_days: int = 30


@router.get("/plans")
async def list_membership_plans(db: AsyncSession = Depends(get_db)):
    svc = MembershipService(db)
    plans = await svc.list_plans()
    return [
        {
            "id": item.id,
            "name": item.name,
            "display_name": item.display_name,
            "price_monthly": item.price_monthly,
            "price_yearly": item.price_yearly,
            "features": item.features or {},
            "sort_order": item.sort_order,
        }
        for item in plans
    ]


@router.get("/contact")
async def get_membership_contact():
    return MembershipService.get_contact_info()


@router.get("/current")
async def get_current_membership(
    db: AsyncSession = Depends(get_db),
    user: UserContext = Depends(get_current_user),
):
    svc = MembershipService(db)
    membership = await svc.get_current_membership(user.email)
    if not membership:
        return {
            "has_membership": False,
            "status": "free",
            "plan": {
                "name": "free",
                "display_name": "免费版",
            },
        }
    return {
        "has_membership": True,
        "status": membership.status,
        "payment_method": membership.payment_method,
        "started_at": membership.started_at.isoformat() if membership.started_at else None,
        "expires_at": membership.expires_at.isoformat() if membership.expires_at else None,
        "plan": {
            "name": membership.plan.name,
            "display_name": membership.plan.display_name,
            "features": membership.plan.features or {},
        },
    }


@router.post("/orders")
async def create_membership_order(
    data: CreateOrderRequest,
    db: AsyncSession = Depends(get_db),
    user: UserContext = Depends(get_current_user),
):
    svc = MembershipService(db)
    try:
        order = await svc.create_placeholder_order(user.email, data.plan_name)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    return {
        "order_id": order.id,
        "order_no": order.order_no,
        "status": order.status,
        "payment_method": order.payment_method,
        "contact": MembershipService.get_contact_info(),
        "message": "当前暂未接入自动支付，请联系管理员微信完成开通。",
    }


@router.post("/manual-activation")
async def manual_activate_membership(
    data: ManualActivationRequest,
    db: AsyncSession = Depends(get_db),
    user: UserContext = Depends(get_current_user),
):
    require_admin(user)
    svc = MembershipService(db)
    try:
        membership = await svc.activate_membership(data.user_email, data.plan_name, data.duration_days)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    return {
        "ok": True,
        "membership_id": membership.id,
        "user_email": membership.user_email,
        "status": membership.status,
    }
