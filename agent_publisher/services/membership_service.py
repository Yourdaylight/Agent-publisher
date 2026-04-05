from __future__ import annotations

from datetime import datetime, timedelta, timezone
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from agent_publisher.config import settings
from agent_publisher.models.membership_plan import MembershipPlan
from agent_publisher.models.order import Order
from agent_publisher.models.user_membership import UserMembership

DEFAULT_MEMBERSHIP_PLANS = [
    {
        "name": "free",
        "display_name": "免费版",
        "price_monthly": 0,
        "price_yearly": 0,
        "sort_order": 0,
        "features": {
            "hotspot_export_daily": 20,
            "prompt_usage_monthly": 5,
            "draft_generation_daily": 1,
            "account_limit": 1,
            "support": "基础社区支持",
        },
    },
    {
        "name": "basic",
        "display_name": "基础版",
        "price_monthly": 59,
        "price_yearly": 499,
        "sort_order": 1,
        "features": {
            "hotspot_export_daily": 500,
            "prompt_usage_monthly": 50,
            "draft_generation_daily": 5,
            "account_limit": 2,
            "support": "微信协助",
        },
    },
    {
        "name": "pro",
        "display_name": "专业版",
        "price_monthly": 129,
        "price_yearly": 1299,
        "sort_order": 2,
        "features": {
            "hotspot_export_daily": 5000,
            "prompt_usage_monthly": 200,
            "draft_generation_daily": 15,
            "account_limit": 10,
            "support": "优先支持",
        },
    },
    {
        "name": "annual",
        "display_name": "年度版",
        "price_monthly": 999,
        "price_yearly": 999,
        "sort_order": 3,
        "features": {
            "hotspot_export_daily": 10000,
            "prompt_usage_monthly": 500,
            "draft_generation_daily": 30,
            "account_limit": 20,
            "support": "专属协助",
        },
    },
]


class MembershipService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def init_default_plans(self) -> None:
        for item in DEFAULT_MEMBERSHIP_PLANS:
            result = await self.session.execute(
                select(MembershipPlan).where(MembershipPlan.name == item["name"])
            )
            plan = result.scalar_one_or_none()
            if plan is None:
                self.session.add(MembershipPlan(**item))
            else:
                plan.display_name = item["display_name"]
                plan.price_monthly = item["price_monthly"]
                plan.price_yearly = item["price_yearly"]
                plan.features = item["features"]
                plan.sort_order = item["sort_order"]
                plan.is_active = True
        await self.session.commit()

    async def list_plans(self) -> list[MembershipPlan]:
        result = await self.session.execute(
            select(MembershipPlan).where(MembershipPlan.is_active.is_(True)).order_by(MembershipPlan.sort_order.asc())
        )
        return list(result.scalars().all())

    async def get_current_membership(self, user_email: str) -> UserMembership | None:
        result = await self.session.execute(
            select(UserMembership)
            .options(selectinload(UserMembership.plan))
            .where(UserMembership.user_email == user_email)
            .order_by(UserMembership.id.desc())
        )
        return result.scalars().first()

    async def create_placeholder_order(self, user_email: str, plan_name: str) -> Order:
        result = await self.session.execute(select(MembershipPlan).where(MembershipPlan.name == plan_name))
        plan = result.scalar_one_or_none()
        if not plan:
            raise ValueError("Membership plan not found")

        order = Order(
            order_no=f"AP{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}{uuid.uuid4().hex[:6].upper()}",
            user_email=user_email,
            plan_id=plan.id,
            amount=plan.price_yearly if plan.name == "annual" else plan.price_monthly,
            status="pending",
            payment_method="manual",
        )
        self.session.add(order)
        await self.session.commit()
        await self.session.refresh(order)
        return order

    async def activate_membership(self, user_email: str, plan_name: str, duration_days: int = 30) -> UserMembership:
        result = await self.session.execute(select(MembershipPlan).where(MembershipPlan.name == plan_name))
        plan = result.scalar_one_or_none()
        if not plan:
            raise ValueError("Membership plan not found")
        membership = UserMembership(
            user_email=user_email,
            plan_id=plan.id,
            status="active",
            payment_method="manual",
            started_at=datetime.now(timezone.utc),
            expires_at=datetime.now(timezone.utc) + timedelta(days=duration_days),
        )
        self.session.add(membership)
        await self.session.commit()
        await self.session.refresh(membership)
        return membership

    @staticmethod
    def get_contact_info() -> dict:
        return {
            "wechat_qr": settings.contact_wechat_qr,
            "wechat_id": settings.contact_wechat_id,
            "contact_description": settings.contact_description or "当前支付能力建设中，请联系管理员微信完成开通。",
            "qrcode_path": "storage/qrcode/contact.png",
        }
