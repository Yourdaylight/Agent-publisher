"""Authentication API: login, token verification, and IP ban logic."""
from __future__ import annotations

import hashlib
import logging
import time
from datetime import datetime, timezone

from fastapi import APIRouter, Request, HTTPException
from pydantic import BaseModel

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


class LoginRequest(BaseModel):
    access_key: str


class LoginResponse(BaseModel):
    token: str
    message: str


@router.post("/login", response_model=LoginResponse)
async def login(req: LoginRequest, request: Request):
    ip = _get_client_ip(request)
    _check_ip_ban(ip)

    if req.access_key != settings.access_key:
        _record_failed_attempt(ip)
        raise HTTPException(status_code=401, detail="Invalid access key")

    _reset_attempts(ip)
    token = _create_token(req.access_key)
    return LoginResponse(token=token, message="Login successful")


@router.get("/verify")
async def verify(request: Request):
    """Verify the current token from Authorization header."""
    auth_header = request.headers.get("authorization", "")
    if not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing token")
    token = auth_header[7:]
    if not verify_token(token):
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    return {"valid": True}
