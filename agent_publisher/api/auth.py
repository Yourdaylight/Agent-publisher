"""Authentication API: login, token verification, and IP ban logic."""
from __future__ import annotations

import hashlib
import logging
import re
import time
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Request, HTTPException
from pydantic import BaseModel, field_validator

from agent_publisher.api.deps import get_current_user, UserContext
from agent_publisher.api.skills import _create_skill_token, verify_skill_token
from agent_publisher.config import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/auth", tags=["auth"])

# In-memory IP ban tracking: { ip: { "attempts": int, "banned_until": float } }
_ip_records: dict[str, dict] = {}

MAX_ATTEMPTS = 5
BAN_DURATION = 600  # 10 minutes


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
            raise HTTPException(status_code=401, detail="Email not in whitelist")
        _reset_attempts(ip)
        token = _create_skill_token(email)
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
            raise HTTPException(status_code=401, detail="Invalid access key")
        _reset_attempts(ip)
        token = _create_token(req.access_key)
        return LoginResponse(
            token=token,
            message="Login successful",
            email="__admin__",
            is_admin=True,
        )

    raise HTTPException(status_code=400, detail="Either access_key or email is required")


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
