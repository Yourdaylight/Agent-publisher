"""Credits API — balance, transactions, check, consume."""

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from agent_publisher.api.deps import get_db, get_current_user, UserContext
from agent_publisher.services.credits_service import CreditsService, CREDITS_COST

router = APIRouter(prefix="/api/credits", tags=["credits"])


class CreditsCheckRequest(BaseModel):
    operation_type: str
    cost: int | None = None


class CreditsConsumeRequest(BaseModel):
    operation_type: str
    cost: int | None = None
    reference_id: int | None = None
    description: str = ""


class CreditsRechargeRequest(BaseModel):
    amount: int
    description: str = "手动充值"


@router.get("/balance")
async def get_balance(
    db: AsyncSession = Depends(get_db),
    user: UserContext = Depends(get_current_user),
):
    svc = CreditsService(db)
    balance = await svc.get_or_create_balance(user.email)
    stats = await svc.get_monthly_stats(user.email)
    return {
        "available": balance.available,
        "free_credits": balance.free_credits,
        "paid_credits": balance.paid_credits,
        "used_credits": balance.used_credits,
        "total_credits": balance.total_credits,
        "monthly_stats": stats,
    }


@router.get("/transactions")
async def get_transactions(
    limit: int = 50,
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
    user: UserContext = Depends(get_current_user),
):
    svc = CreditsService(db)
    txs = await svc.get_transactions(user.email, limit=limit, offset=offset)
    return [
        {
            "id": tx.id,
            "operation_type": tx.operation_type,
            "credits_amount": tx.credits_amount,
            "balance_after": tx.balance_after,
            "reference_id": tx.reference_id,
            "description": tx.description,
            "created_at": tx.created_at.isoformat() if tx.created_at else None,
        }
        for tx in txs
    ]


@router.post("/check")
async def check_credits(
    data: CreditsCheckRequest,
    db: AsyncSession = Depends(get_db),
    user: UserContext = Depends(get_current_user),
):
    cost = data.cost or CREDITS_COST.get(data.operation_type, 0)
    svc = CreditsService(db)
    return await svc.check_balance(user.email, cost)


@router.post("/consume")
async def consume_credits(
    data: CreditsConsumeRequest,
    db: AsyncSession = Depends(get_db),
    user: UserContext = Depends(get_current_user),
):
    svc = CreditsService(db)
    return await svc.consume(
        user.email,
        operation_type=data.operation_type,
        cost=data.cost,
        reference_id=data.reference_id,
        description=data.description,
    )


@router.post("/recharge")
async def recharge_credits(
    data: CreditsRechargeRequest,
    db: AsyncSession = Depends(get_db),
    user: UserContext = Depends(get_current_user),
):
    svc = CreditsService(db)
    balance = await svc.recharge(user.email, data.amount, data.description)
    return {
        "ok": True,
        "available": balance.available,
        "paid_credits": balance.paid_credits,
    }


@router.get("/cost-table")
async def get_cost_table():
    """Public endpoint returning the credits cost for each operation."""
    return CREDITS_COST
