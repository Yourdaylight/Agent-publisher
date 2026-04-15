"""Global settings API: manage LLM, image generation, and other configurations at runtime."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from agent_publisher.api.deps import get_current_user, require_admin, UserContext
from agent_publisher.config import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/settings", tags=["settings"])


async def _require_admin_user(user: UserContext = Depends(get_current_user)) -> UserContext:
    """Dependency: require admin privileges for all settings endpoints."""
    require_admin(user)
    return user


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


class MembershipContactSettingsUpdate(BaseModel):
    contact_wechat_qr: str | None = None
    contact_wechat_id: str | None = None
    contact_description: str | None = None


class AllSettings(BaseModel):
    default_llm_provider: str
    default_llm_model: str
    default_llm_api_key: str
    default_llm_base_url: str
    tencent_secret_id: str
    tencent_secret_key: str
    access_key_masked: str
    contact_wechat_qr: str
    contact_wechat_id: str
    contact_description: str
    wechat_proxy: str
    trending_refresh_interval: int


class WeChatProxyUpdate(BaseModel):
    wechat_proxy: str


class TrendingRefreshUpdate(BaseModel):
    interval_minutes: int  # 0 = disabled


def _mask(value: str) -> str:
    """Mask sensitive values, showing only first 4 and last 4 chars."""
    if len(value) <= 8:
        return "*" * len(value)
    return value[:4] + "*" * (len(value) - 8) + value[-4:]


@router.get("", response_model=AllSettings)
async def get_settings(_: UserContext = Depends(_require_admin_user)):
    """Get all current global settings (sensitive values masked). Admin only."""
    return AllSettings(
        default_llm_provider=settings.default_llm_provider,
        default_llm_model=settings.default_llm_model,
        default_llm_api_key=_mask(settings.default_llm_api_key)
        if settings.default_llm_api_key
        else "",
        default_llm_base_url=settings.default_llm_base_url,
        tencent_secret_id=_mask(settings.tencent_secret_id) if settings.tencent_secret_id else "",
        tencent_secret_key=_mask(settings.tencent_secret_key)
        if settings.tencent_secret_key
        else "",
        access_key_masked=_mask(settings.access_key),
        contact_wechat_qr=settings.contact_wechat_qr,
        contact_wechat_id=settings.contact_wechat_id,
        contact_description=settings.contact_description,
        wechat_proxy=settings.wechat_proxy,
        trending_refresh_interval=settings.trending_refresh_interval,
    )


@router.put("/llm")
async def update_llm_settings(
    req: LLMSettingsUpdate, _: UserContext = Depends(_require_admin_user)
):
    """Update default LLM settings at runtime. Admin only."""
    if req.default_llm_provider is not None:
        settings.default_llm_provider = req.default_llm_provider
    if req.default_llm_model is not None:
        settings.default_llm_model = req.default_llm_model
    if req.default_llm_api_key is not None:
        settings.default_llm_api_key = req.default_llm_api_key
    if req.default_llm_base_url is not None:
        settings.default_llm_base_url = req.default_llm_base_url
    logger.info(
        "LLM settings updated: provider=%s model=%s",
        settings.default_llm_provider,
        settings.default_llm_model,
    )
    return {"message": "LLM settings updated"}


@router.put("/image")
async def update_image_settings(
    req: ImageSettingsUpdate, _: UserContext = Depends(_require_admin_user)
):
    """Update Tencent Cloud image generation settings at runtime. Admin only."""
    if req.tencent_secret_id is not None:
        settings.tencent_secret_id = req.tencent_secret_id
    if req.tencent_secret_key is not None:
        settings.tencent_secret_key = req.tencent_secret_key
    logger.info("Image generation settings updated")
    return {"message": "Image settings updated"}


@router.put("/membership-contact")
async def update_membership_contact_settings(
    req: MembershipContactSettingsUpdate, _: UserContext = Depends(_require_admin_user)
):
    """Update membership contact / QR placeholder settings. Admin only."""
    if req.contact_wechat_qr is not None:
        settings.contact_wechat_qr = req.contact_wechat_qr
    if req.contact_wechat_id is not None:
        settings.contact_wechat_id = req.contact_wechat_id
    if req.contact_description is not None:
        settings.contact_description = req.contact_description
    logger.info("Membership contact settings updated")
    return {"message": "Membership contact settings updated"}


@router.put("/proxy")
async def update_wechat_proxy(
    req: WeChatProxyUpdate, _: UserContext = Depends(_require_admin_user)
):
    """Update WeChat API HTTP proxy at runtime. Admin only.

    Set to an empty string to disable the proxy.
    Only affects calls to the WeChat API (api.weixin.qq.com).
    """
    proxy = req.wechat_proxy.strip()
    if proxy and not (
        proxy.startswith("http://") or proxy.startswith("https://") or proxy.startswith("socks5://")
    ):
        raise HTTPException(
            status_code=400, detail="代理地址格式无效，应以 http://、https:// 或 socks5:// 开头"
        )
    settings.wechat_proxy = proxy
    logger.info("WeChat proxy updated: %s", proxy or "(disabled)")
    return {"message": "WeChat proxy updated", "wechat_proxy": proxy}


@router.put("/trending")
async def update_trending_settings(
    req: TrendingRefreshUpdate, _: UserContext = Depends(_require_admin_user)
):
    """Update trending hotspot auto-refresh interval. Admin only.

    interval_minutes=0 disables automatic refresh.
    Changes take effect immediately (scheduler job is updated at runtime).
    """
    if req.interval_minutes < 0:
        raise HTTPException(status_code=400, detail="interval_minutes 不能为负数")
    settings.trending_refresh_interval = req.interval_minutes
    from agent_publisher.scheduler import sync_trending_schedule

    sync_trending_schedule(req.interval_minutes)
    msg = (
        f"热榜每 {req.interval_minutes} 分钟自动刷新"
        if req.interval_minutes > 0
        else "热榜自动刷新已禁用"
    )
    logger.info("Trending refresh interval updated: %d minutes", req.interval_minutes)
    return {"message": msg, "interval_minutes": req.interval_minutes}


@router.put("/access-key")
async def update_access_key(req: AccessKeyUpdate, _: UserContext = Depends(_require_admin_user)):
    """Update the access key. Requires the current key for verification. Admin only."""
    if req.current_key != settings.access_key:
        raise HTTPException(status_code=403, detail="Current access key is incorrect")
    if len(req.new_key) < 6:
        raise HTTPException(status_code=400, detail="New access key must be at least 6 characters")
    settings.access_key = req.new_key
    logger.info("Access key updated")
    return {"message": "Access key updated. Please re-login with the new key."}
