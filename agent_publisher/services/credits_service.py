"""Credits billing service — balance queries, consumption, and recharge."""

from __future__ import annotations

import logging
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from agent_publisher.models.credits import CreditsBalance, CreditsTransaction

logger = logging.getLogger(__name__)

# Credits cost table
CREDITS_COST = {
    "generate_article": 10,
    "rewrite_paragraph": 2,
    "expand_content": 3,
    "ai_beautify": 3,
    "generate_image": 5,
    "generate_image_hd": 8,
    "generate_video": 20,
    "export_csv": 1,
}

DEFAULT_FREE_CREDITS = 50


class CreditsService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_or_create_balance(self, user_email: str) -> CreditsBalance:
        result = await self.session.execute(
            select(CreditsBalance).where(CreditsBalance.user_email == user_email)
        )
        balance = result.scalar_one_or_none()
        if balance is None:
            balance = CreditsBalance(
                user_email=user_email,
                total_credits=DEFAULT_FREE_CREDITS,
                used_credits=0,
                free_credits=DEFAULT_FREE_CREDITS,
                paid_credits=0,
            )
            self.session.add(balance)
            await self.session.commit()
            await self.session.refresh(balance)
        return balance

    async def check_balance(self, user_email: str, cost: int) -> dict:
        """Check if user has enough credits. Returns {ok, available, cost}."""
        balance = await self.get_or_create_balance(user_email)
        available = balance.available
        return {
            "ok": available >= cost,
            "available": available,
            "cost": cost,
            "shortfall": max(0, cost - available),
        }

    async def consume(
        self,
        user_email: str,
        operation_type: str,
        cost: int | None = None,
        reference_id: int | None = None,
        description: str = "",
    ) -> dict:
        """Consume credits. Returns {ok, available, cost, transaction_id}."""
        if cost is None:
            cost = CREDITS_COST.get(operation_type, 0)
        if cost <= 0:
            return {"ok": True, "available": 0, "cost": 0, "transaction_id": None}

        balance = await self.get_or_create_balance(user_email)
        available = balance.available
        if available < cost:
            return {
                "ok": False,
                "available": available,
                "cost": cost,
                "error": "Credits 不足",
            }

        balance.used_credits += cost
        new_available = balance.available

        tx = CreditsTransaction(
            user_email=user_email,
            operation_type=operation_type,
            credits_amount=-cost,
            balance_after=new_available,
            reference_id=reference_id,
            description=description or _default_description(operation_type),
        )
        self.session.add(tx)
        await self.session.commit()
        await self.session.refresh(tx)

        return {
            "ok": True,
            "available": new_available,
            "cost": cost,
            "transaction_id": tx.id,
        }

    async def refund(
        self,
        user_email: str,
        operation_type: str,
        cost: int,
        reference_id: int | None = None,
    ) -> None:
        """Refund credits (e.g. on generation failure)."""
        balance = await self.get_or_create_balance(user_email)
        balance.used_credits = max(0, balance.used_credits - cost)

        tx = CreditsTransaction(
            user_email=user_email,
            operation_type=f"refund_{operation_type}",
            credits_amount=cost,
            balance_after=balance.available,
            reference_id=reference_id,
            description=f"退回 {cost} Credits（{_default_description(operation_type)}失败）",
        )
        self.session.add(tx)
        await self.session.commit()

    async def recharge(
        self, user_email: str, amount: int, description: str = "充值"
    ) -> CreditsBalance:
        """Add paid credits."""
        balance = await self.get_or_create_balance(user_email)
        balance.paid_credits += amount
        balance.total_credits += amount

        tx = CreditsTransaction(
            user_email=user_email,
            operation_type="recharge",
            credits_amount=amount,
            balance_after=balance.available,
            description=description,
        )
        self.session.add(tx)
        await self.session.commit()
        await self.session.refresh(balance)
        return balance

    async def get_transactions(
        self, user_email: str, limit: int = 50, offset: int = 0
    ) -> list[CreditsTransaction]:
        result = await self.session.execute(
            select(CreditsTransaction)
            .where(CreditsTransaction.user_email == user_email)
            .order_by(CreditsTransaction.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return list(result.scalars().all())

    async def get_monthly_stats(self, user_email: str) -> dict:
        """Get current month consumption stats."""
        from datetime import datetime, timezone

        now = datetime.now(timezone.utc)
        month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

        result = await self.session.execute(
            select(CreditsTransaction).where(
                CreditsTransaction.user_email == user_email,
                CreditsTransaction.credits_amount < 0,
                CreditsTransaction.created_at >= month_start,
            )
        )
        txs = list(result.scalars().all())

        total_consumed = sum(abs(tx.credits_amount) for tx in txs)
        by_type: dict[str, int] = {}
        count_by_type: dict[str, int] = {}
        for tx in txs:
            by_type[tx.operation_type] = by_type.get(tx.operation_type, 0) + abs(tx.credits_amount)
            count_by_type[tx.operation_type] = count_by_type.get(tx.operation_type, 0) + 1

        return {
            "total_consumed": total_consumed,
            "by_type": by_type,
            "count_by_type": count_by_type,
            "transaction_count": len(txs),
        }


def _default_description(op: str) -> str:
    descriptions = {
        "generate_article": "AI 生成文章",
        "rewrite_paragraph": "AI 段落改写",
        "expand_content": "AI 扩写/缩写",
        "generate_image": "AI 配图",
        "generate_image_hd": "AI 高清配图",
        "generate_video": "视频生成",
        "export_csv": "热点导出",
    }
    return descriptions.get(op, op)
