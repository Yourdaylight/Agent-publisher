from datetime import datetime, timezone, date, timedelta

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from agent_publisher.api.deps import get_db
from agent_publisher.models.account import Account
from agent_publisher.schemas.account import AccountCreate, AccountOut, AccountUpdate
from agent_publisher.services.wechat_service import WeChatService

router = APIRouter(prefix="/api/accounts", tags=["accounts"])


@router.post("", response_model=AccountOut)
async def create_account(data: AccountCreate, db: AsyncSession = Depends(get_db)):
    account = Account(**data.model_dump())
    db.add(account)
    await db.commit()
    await db.refresh(account)
    return account


@router.get("", response_model=list[AccountOut])
async def list_accounts(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Account).order_by(Account.id))
    return result.scalars().all()


@router.get("/{account_id}", response_model=AccountOut)
async def get_account(account_id: int, db: AsyncSession = Depends(get_db)):
    account = await db.get(Account, account_id)
    if not account:
        raise HTTPException(404, "Account not found")
    return account


@router.put("/{account_id}", response_model=AccountOut)
async def update_account(
    account_id: int, data: AccountUpdate, db: AsyncSession = Depends(get_db)
):
    account = await db.get(Account, account_id)
    if not account:
        raise HTTPException(404, "Account not found")
    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(account, key, value)
    await db.commit()
    await db.refresh(account)
    return account


@router.delete("/{account_id}")
async def delete_account(account_id: int, db: AsyncSession = Depends(get_db)):
    account = await db.get(Account, account_id)
    if not account:
        raise HTTPException(404, "Account not found")
    await db.delete(account)
    await db.commit()
    return {"ok": True}


async def _ensure_token(account: Account, db: AsyncSession) -> None:
    """Refresh access_token if expired."""
    now = datetime.now(tz=timezone.utc)
    token_expired = (
        not account.access_token
        or not account.token_expires_at
        or account.token_expires_at.replace(tzinfo=timezone.utc) < now
    )
    if token_expired:
        token, expires_at = await WeChatService.get_access_token(
            account.appid, account.appsecret
        )
        account.access_token = token
        account.token_expires_at = expires_at
        await db.commit()


@router.get("/{account_id}/followers")
async def get_account_followers(
    account_id: int,
    begin_date: str | None = None,
    end_date: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    """Get follower overview for an account."""
    account = await db.get(Account, account_id)
    if not account:
        raise HTTPException(404, "Account not found")

    await _ensure_token(account, db)

    if not end_date:
        end_date = (date.today() - timedelta(days=1)).isoformat()
    if not begin_date:
        begin_date = (date.fromisoformat(end_date) - timedelta(days=6)).isoformat()

    warnings: list[str] = []

    # Follower count
    followers_info: dict = {}
    try:
        followers_info = await WeChatService.get_followers(account.access_token)
    except RuntimeError as e:
        msg = str(e)
        if "48001" in msg:
            warnings.append("该公众号没有粉丝管理接口权限（需要认证服务号），无法获取粉丝总数")
        else:
            raise HTTPException(status_code=502, detail=msg)

    # Datacube stats
    user_summary: list[dict] = []
    user_cumulate: list[dict] = []
    try:
        user_summary = await WeChatService.get_user_summary(
            account.access_token, begin_date, end_date
        )
        user_cumulate = await WeChatService.get_user_cumulate(
            account.access_token, begin_date, end_date
        )
    except RuntimeError as e:
        msg = str(e)
        if "48001" in msg:
            warnings.append("该公众号没有数据统计接口权限（需要认证服务号），仅返回粉丝总数")
        else:
            raise HTTPException(status_code=502, detail=msg)

    result: dict = {
        "account_id": account_id,
        "account_name": account.name,
        "begin_date": begin_date,
        "end_date": end_date,
        "total_followers": followers_info.get("total", 0),
        "user_summary": user_summary,
        "user_cumulate": user_cumulate,
    }
    if warnings:
        result["warnings"] = warnings
    return result


@router.get("/{account_id}/article-stats")
async def get_account_article_stats(
    account_id: int,
    begin_date: str | None = None,
    end_date: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    """Get article statistics for an account."""
    account = await db.get(Account, account_id)
    if not account:
        raise HTTPException(404, "Account not found")

    await _ensure_token(account, db)

    if not end_date:
        end_date = (date.today() - timedelta(days=1)).isoformat()
    if not begin_date:
        begin_date = (date.fromisoformat(end_date) - timedelta(days=6)).isoformat()

    warnings: list[str] = []
    article_summary: list[dict] = []
    article_total: list[dict] = []
    try:
        article_summary = await WeChatService.get_article_summary(
            account.access_token, begin_date, end_date
        )
        article_total = await WeChatService.get_article_total(
            account.access_token, begin_date, end_date
        )
    except RuntimeError as e:
        msg = str(e)
        if "48001" in msg:
            warnings.append("该公众号没有文章统计接口权限（需要认证服务号），无法获取阅读/分享数据")
        else:
            raise HTTPException(status_code=502, detail=msg)

    result: dict = {
        "account_id": account_id,
        "account_name": account.name,
        "begin_date": begin_date,
        "end_date": end_date,
        "article_summary": article_summary,
        "article_total": article_total,
    }
    if warnings:
        result["warnings"] = warnings
    return result
