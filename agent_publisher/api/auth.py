"""Authentication API: login, token verification, and IP ban logic."""
from __future__ import annotations

import hashlib
import logging
import re
import time
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Request, HTTPException
from pydantic import BaseModel, field_validator

from agent_publisher.api.deps import get_current_user, UserContext, get_db
from agent_publisher.api.skills import _create_skill_token, verify_skill_token
from agent_publisher.config import settings
from agent_publisher.database import async_session_factory

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/auth", tags=["auth"])

# In-memory IP ban tracking: { ip: { "attempts": int, "banned_until": float } }
_ip_records: dict[str, dict] = {}

MAX_ATTEMPTS = 5
BAN_DURATION = 600  # 10 minutes


async def _record_login_log(
    *, email: str, is_admin: bool, status: str, client_ip: str, error: str = ""
) -> None:
    """Record a login attempt to system_logs."""
    try:
        from agent_publisher.services.system_log_service import SystemLogService
        async with async_session_factory() as session:
            svc = SystemLogService(session)
            await svc.record(
                action="login",
                target_type="account",
                description="管理员登录" if is_admin else f"用户登录 {email}",
                operator=email,
                is_admin=is_admin,
                status=status,
                error_message=error,
                client_ip=client_ip,
                request_path="/api/auth/login",
            )
    except Exception as e:
        logger.warning("Failed to record login log: %s", e, exc_info=True)


def _get_client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def _check_ip_ban(ip: str) -> None:
    """Raise 403 if the IP is currently banned."""
    record = _ip_records.get(ip)
    if not record:
        return
    banned_until = record.get("banned_until", 0)
    if banned_until > time.time():
        remaining = int(banned_until - time.time())
        raise HTTPException(
            status_code=403,
            detail=f"IP banned due to too many failed attempts. Try again in {remaining}s.",
        )
    # Ban expired, reset
    if banned_until > 0:
        _ip_records.pop(ip, None)


def _record_failed_attempt(ip: str) -> None:
    """Record a failed login attempt and ban if threshold exceeded."""
    record = _ip_records.setdefault(ip, {"attempts": 0, "banned_until": 0})
    record["attempts"] = record.get("attempts", 0) + 1
    logger.warning("Failed login attempt from %s (count: %d)", ip, record["attempts"])
    if record["attempts"] >= MAX_ATTEMPTS:
        record["banned_until"] = time.time() + BAN_DURATION
        logger.warning("IP %s banned for %ds after %d failed attempts", ip, BAN_DURATION, record["attempts"])


def _reset_attempts(ip: str) -> None:
    _ip_records.pop(ip, None)


def _create_token(access_key: str) -> str:
    """Create a simple HMAC-based token. Not a full JWT, but sufficient for single-key auth."""
    secret = settings.get_jwt_secret()
    ts = str(int(time.time()))
    sig = hashlib.sha256(f"{secret}:{access_key}:{ts}".encode()).hexdigest()
    return f"{ts}.{sig}"


def verify_token(token: str) -> bool:
    """Verify the token is valid and not too old (30-day expiry)."""
    try:
        parts = token.split(".")
        if len(parts) != 2:
            return False
        ts_str, sig = parts
        ts = int(ts_str)
        # Check expiry (30 days)
        if time.time() - ts > 30 * 86400:
            return False
        # Verify signature
        secret = settings.get_jwt_secret()
        expected_sig = hashlib.sha256(f"{secret}:{settings.access_key}:{ts_str}".encode()).hexdigest()
        return sig == expected_sig
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Request / Response schemas
# ---------------------------------------------------------------------------

class LoginRequest(BaseModel):
    """Login request: provide either access_key (admin) or email (normal user)."""
    access_key: str | None = None
    email: str | None = None

    @field_validator("email")
    @classmethod
    def validate_email(cls, v: str | None) -> str | None:
        if v is None:
            return v
        v = v.strip().lower()
        if not re.match(r"^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$", v):
            raise ValueError("Invalid email address")
        return v


class LoginResponse(BaseModel):
    token: str
    message: str
    email: str | None = None
    is_admin: bool = False


class UserInfoResponse(BaseModel):
    email: str
    is_admin: bool


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("/login", response_model=LoginResponse)
async def login(req: LoginRequest, request: Request):
    """Login with either access_key (admin) or email (normal user).

    - access_key login: returns an admin token (ts.sig format)
    - email login: checks whitelist, returns a skill token (ts|email|sig format)
    """
    ip = _get_client_ip(request)
    _check_ip_ban(ip)

    if req.email:
        # Email-based login
        email = req.email.strip().lower()
        if not settings.is_email_allowed(email):
            _record_failed_attempt(ip)
            await _record_login_log(email=email, is_admin=settings.is_admin(email), status="failed", error="邮箱不在白名单", client_ip=ip)
            raise HTTPException(status_code=401, detail="该邮箱不在白名单中，请联系管理员")
        _reset_attempts(ip)
        token = _create_skill_token(email)
        await _record_login_log(email=email, is_admin=settings.is_admin(email), status="success", client_ip=ip)
        return LoginResponse(
            token=token,
            message="Login successful",
            email=email,
            is_admin=settings.is_admin(email),
        )

    if req.access_key:
        # Admin access_key login
        if req.access_key != settings.access_key:
            _record_failed_attempt(ip)
            await _record_login_log(email="__admin__", is_admin=True, status="failed", error="密钥错误", client_ip=ip)
            raise HTTPException(status_code=401, detail="Invalid access key")
        _reset_attempts(ip)
        token = _create_token(req.access_key)
        await _record_login_log(email="__admin__", is_admin=True, status="success", client_ip=ip)
        return LoginResponse(
            token=token,
            message="Login successful",
            email="__admin__",
            is_admin=True,
        )




@router.get("/verify")
async def verify(request: Request):
    """Verify the current token from Authorization header (supports both token types)."""
    auth_header = request.headers.get("authorization", "")
    if not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing token")
    token = auth_header[7:]

    # Try skill/email token first (contains "|")
    if "|" in token:
        email = verify_skill_token(token)
        if not email:
            raise HTTPException(status_code=401, detail="Invalid or expired token")
        return {"valid": True, "email": email, "is_admin": settings.is_admin(email)}

    # Admin token
    if not verify_token(token):
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    return {"valid": True, "email": "__admin__", "is_admin": True}


@router.get("/me", response_model=UserInfoResponse)
async def get_me(user: UserContext = Depends(get_current_user)):
    """Return the current authenticated user's identity."""
    return UserInfoResponse(email=user.email, is_admin=user.is_admin)


# ---------------------------------------------------------------------------
# Invite Code Login (public endpoint)
# ---------------------------------------------------------------------------

class InviteLoginRequest(BaseModel):
    code: str
    email: str

    @field_validator("email")
    @classmethod
    def validate_email(cls, v: str) -> str:
        v = v.strip().lower()
        if not re.match(r"^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$", v):
            raise ValueError("Invalid email address")
        return v


@router.post("/invite", response_model=LoginResponse)
async def invite_login(req: InviteLoginRequest, request: Request):
    """Login via invite code. Auto-registers user and grants bonus credits."""
    from sqlalchemy import select, func as sa_func
    from agent_publisher.models.invite_code import InviteCode, InviteRedemption
    from agent_publisher.services.credits_service import CreditsService

    ip = _get_client_ip(request)
    _check_ip_ban(ip)
    email = req.email.strip().lower()

    async with async_session_factory() as session:
        # 1. Validate invite code
        result = await session.execute(
            select(InviteCode).where(InviteCode.code == req.code, InviteCode.is_active == True)
        )
        invite = result.scalar_one_or_none()
        if not invite:
            _record_failed_attempt(ip)
            raise HTTPException(status_code=400, detail="邀请码无效或已停用")

        if invite.expires_at and invite.expires_at < datetime.now(timezone.utc):
            raise HTTPException(status_code=400, detail="邀请码已过期")

        if invite.max_uses > 0 and invite.used_count >= invite.max_uses:
            raise HTTPException(status_code=400, detail="邀请码已达到使用上限")

        # 2. Rate limit: max 5 activations per IP per 24h
        day_ago = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
        ip_count_result = await session.execute(
            select(sa_func.count()).where(
                InviteRedemption.ip_address == ip,
                InviteRedemption.created_at >= day_ago,
            )
        )
        ip_count = ip_count_result.scalar() or 0
        if ip_count >= 5:
            raise HTTPException(status_code=429, detail="同一 IP 每日最多激活 5 次邀请码")

        # 3. Check if email already registered
        is_existing_user = settings.is_email_allowed(email)

        if not is_existing_user:
            # New user: add to runtime whitelist
            settings.add_to_whitelist(email)

            # Create credits account with bonus
            credits_svc = CreditsService(session)
            await credits_svc.get_or_create_balance(email)
            await credits_svc.recharge(email, invite.bonus_credits, f"邀请码 {invite.code} 激活奖励")

        # 4. Record redemption and update usage count
        invite.used_count += 1
        session.add(InviteRedemption(
            invite_code_id=invite.id,
            user_email=email,
            ip_address=ip,
        ))
        await session.commit()

        # 5. Issue token
        _reset_attempts(ip)
        token = _create_skill_token(email)
        return LoginResponse(
            token=token,
            message=f"欢迎！已获得 {invite.bonus_credits} AI 创作积分" if not is_existing_user else "登录成功",
            email=email,
            is_admin=settings.is_admin(email),
        )
