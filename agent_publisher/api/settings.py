"""Global settings API: manage LLM, image generation, and other configurations at runtime."""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from agent_publisher.api.auth import verify_token
from agent_publisher.config import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/settings", tags=["settings"])


def _require_auth(request: Request) -> None:
    """Dependency to require valid auth token."""
    auth_header = request.headers.get("authorization", "")
    if not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Authentication required")
    token = auth_header[7:]
    if not verify_token(token):
        raise HTTPException(status_code=401, detail="Invalid or expired token")


class LLMSettingsUpdate(BaseModel):
    default_llm_provider: str | None = None
    default_llm_model: str | None = None
    default_llm_api_key: str | None = None
    default_llm_base_url: str | None = None


class ImageSettingsUpdate(BaseModel):
    tencent_secret_id: str | None = None
    tencent_secret_key: str | None = None


class AccessKeyUpdate(BaseModel):
    current_key: str
    new_key: str


class AllSettings(BaseModel):
    default_llm_provider: str
    default_llm_model: str
    default_llm_api_key: str
    default_llm_base_url: str
    tencent_secret_id: str
    tencent_secret_key: str
    access_key_masked: str


def _mask(value: str) -> str:
    """Mask sensitive values, showing only first 4 and last 4 chars."""
    if len(value) <= 8:
        return "*" * len(value)
    return value[:4] + "*" * (len(value) - 8) + value[-4:]


@router.get("", response_model=AllSettings)
async def get_settings(_: None = Depends(_require_auth)):
    """Get all current global settings (sensitive values masked)."""
    return AllSettings(
        default_llm_provider=settings.default_llm_provider,
        default_llm_model=settings.default_llm_model,
        default_llm_api_key=_mask(settings.default_llm_api_key) if settings.default_llm_api_key else "",
        default_llm_base_url=settings.default_llm_base_url,
        tencent_secret_id=_mask(settings.tencent_secret_id) if settings.tencent_secret_id else "",
        tencent_secret_key=_mask(settings.tencent_secret_key) if settings.tencent_secret_key else "",
        access_key_masked=_mask(settings.access_key),
    )


@router.put("/llm")
async def update_llm_settings(req: LLMSettingsUpdate, _: None = Depends(_require_auth)):
    """Update default LLM settings at runtime."""
    if req.default_llm_provider is not None:
        settings.default_llm_provider = req.default_llm_provider
    if req.default_llm_model is not None:
        settings.default_llm_model = req.default_llm_model
    if req.default_llm_api_key is not None:
        settings.default_llm_api_key = req.default_llm_api_key
    if req.default_llm_base_url is not None:
        settings.default_llm_base_url = req.default_llm_base_url
    logger.info("LLM settings updated: provider=%s model=%s", settings.default_llm_provider, settings.default_llm_model)
    return {"message": "LLM settings updated"}


@router.put("/image")
async def update_image_settings(req: ImageSettingsUpdate, _: None = Depends(_require_auth)):
    """Update Tencent Cloud image generation settings at runtime."""
    if req.tencent_secret_id is not None:
        settings.tencent_secret_id = req.tencent_secret_id
    if req.tencent_secret_key is not None:
        settings.tencent_secret_key = req.tencent_secret_key
    logger.info("Image generation settings updated")
    return {"message": "Image settings updated"}


@router.put("/access-key")
async def update_access_key(req: AccessKeyUpdate, _: None = Depends(_require_auth)):
    """Update the access key. Requires the current key for verification."""
    if req.current_key != settings.access_key:
        raise HTTPException(status_code=403, detail="Current access key is incorrect")
    if len(req.new_key) < 6:
        raise HTTPException(status_code=400, detail="New access key must be at least 6 characters")
    settings.access_key = req.new_key
    logger.info("Access key updated")
    return {"message": "Access key updated. Please re-login with the new key."}
