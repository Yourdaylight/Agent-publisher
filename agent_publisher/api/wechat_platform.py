"""WeChat Third-party Platform API — 扫码授权公众号的接口.

提供以下端点：
- GET  /api/wechat-platform/auth-url     获取扫码授权链接
- GET  /api/wechat-platform/auth-callback 授权回调（微信跳转）
- POST /api/wechat-platform/ticket-callback component_verify_ticket 推送回调
- POST /api/wechat-platform/event-callback  授权变更事件回调
- GET  /api/wechat-platform/status        查询平台配置状态
"""

from __future__ import annotations

import logging
from urllib.parse import quote_plus

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from agent_publisher.api.deps import get_db, get_current_user, UserContext
from agent_publisher.config import settings
from agent_publisher.models.account import Account
from agent_publisher.services.wechat_platform_service import (
    WeChatPlatformService,
    CryptoUtils,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/wechat-platform", tags=["wechat-platform"])


@router.get("/status")
async def platform_status(user: UserContext = Depends(get_current_user)):
    """Check if WeChat Platform is configured and ticket is available.

    Returns the current configuration status so the frontend can decide
    whether to show the scan-authorization entry point.
    """
    configured = WeChatPlatformService.is_configured()
    ticket_available = False
    if configured:
        ticket = await WeChatPlatformService.get_verify_ticket()
        ticket_available = ticket is not None

    return {
        "configured": configured,
        "ticket_available": ticket_available,
        "appid_configured": bool(settings.wechat_platform_appid.strip()),
    }


@router.get("/auth-url")
async def get_auth_url(user: UserContext = Depends(get_current_user)):
    """Generate the scan authorization URL and QR code link.

    Steps:
    1. Check platform is configured
    2. Get pre_auth_code
    3. Build auth URL with redirect_uri
    4. Return URL for frontend to display as QR code

    Returns:
        auth_url: The URL that renders a QR code page on WeChat
        h5_auth_url: Mobile-friendly auth URL
    """
    if not WeChatPlatformService.is_configured():
        raise HTTPException(
            status_code=400,
            detail="微信第三方平台未配置。请在 .env 中设置 WECHAT_PLATFORM_* 相关配置。"
            "详见 docs/wechat-platform-setup.md",
        )

    try:
        pre_auth_code = await WeChatPlatformService.get_pre_auth_code()
    except Exception as e:
        logger.error("Failed to get pre_auth_code: %s", e)
        raise HTTPException(
            status_code=502,
            detail=f"获取预授权码失败: {e}",
        )

    # Build redirect URI using server_host
    server_host = settings.get_server_host()
    port_part = f":{settings.port}" if settings.port not in (80, 443) else ""
    redirect_uri = f"https://{server_host}{port_part}/api/wechat-platform/auth-callback"

    auth_url = WeChatPlatformService.build_auth_url(
        pre_auth_code,
        quote_plus(redirect_uri),
        auth_type=1,  # 仅展示公众号
    )
    h5_auth_url = WeChatPlatformService.build_h5_auth_url(
        pre_auth_code, quote_plus(redirect_uri), auth_type=1
    )

    return {
        "auth_url": auth_url,
        "h5_auth_url": h5_auth_url,
        "pre_auth_code": pre_auth_code,
        "redirect_uri": redirect_uri,
    }


@router.get("/auth-callback")
async def auth_callback(
    auth_code: str = Query(..., description="Authorization code from WeChat"),
    expires_in: int = Query(600, description="Auth code expiration in seconds"),
    db: AsyncSession = Depends(get_db),
):
    """Handle the authorization callback from WeChat.

    After the account admin scans the QR code and confirms, WeChat redirects
    to this URL with auth_code. We exchange it for authorizer_access_token
    and create/update the Account record.

    Returns a simple HTML page indicating success or failure.
    """
    logger.info(
        "Auth callback received: auth_code=%s, expires_in=%d", auth_code[:8] + "...", expires_in
    )

    try:
        # Exchange auth_code for authorizer info
        auth_info = await WeChatPlatformService.handle_auth_callback(auth_code)
        authorizer_appid = auth_info["authorizer_appid"]
        authorizer_access_token = auth_info["authorizer_access_token"]
        authorizer_refresh_token = auth_info["authorizer_refresh_token"]
        expires_in_sec = auth_info["expires_in"]

        # Get authorizer detailed info (nickname, avatar, etc.)
        authorizer_detail = await WeChatPlatformService.get_authorizer_info(authorizer_appid)
        nick_name = authorizer_detail.get("nick_name", "")
        head_img = authorizer_detail.get("head_img", "")
        service_type_info = authorizer_detail.get("service_type_info", {})
        verify_type_info = authorizer_detail.get("verify_type_info", {})
        service_type = service_type_info.get("id", 0) if isinstance(service_type_info, dict) else 0
        verify_type = verify_type_info.get("id", 0) if isinstance(verify_type_info, dict) else 0
        authorizer_detail.get("user_name", "")  # 公众号原始ID

        # Calculate token expiry
        from datetime import datetime, timedelta, timezone

        expires_at = datetime.now(timezone.utc) + timedelta(seconds=expires_in_sec - 300)

        # Check if account already exists for this authorizer_appid
        result = await db.execute(
            select(Account).where(Account.authorizer_appid == authorizer_appid)
        )
        existing = result.scalar_one_or_none()

        # Determine owner_email from current user context (best-effort)
        # Auth callback is a redirect from WeChat so no auth header;
        # we assign to the first admin or leave empty for admin to claim.
        owner_email = ""
        try:
            from agent_publisher.config import settings as cfg

            admins = cfg.get_admin_emails()
            if admins:
                owner_email = sorted(admins)[0]
        except Exception:
            pass

        if existing:
            # Update existing account
            existing.auth_mode = "platform"
            existing.authorizer_access_token = authorizer_access_token
            existing.authorizer_refresh_token = authorizer_refresh_token
            existing.authorizer_token_expires_at = expires_at
            existing.access_token = authorizer_access_token
            existing.token_expires_at = expires_at
            existing.nick_name = nick_name
            existing.head_img = head_img
            existing.service_type = service_type
            existing.verify_type = verify_type
            if nick_name and not existing.name:
                existing.name = nick_name
            await db.commit()
            logger.info(
                "Updated existing account id=%d for authorizer_appid=%s",
                existing.id,
                authorizer_appid,
            )
        else:
            # Create new account
            account = Account(
                name=nick_name or authorizer_appid,
                appid=authorizer_appid,  # Use authorizer_appid as appid for API compatibility
                appsecret="",  # Not needed for platform mode
                owner_email=owner_email,
                auth_mode="platform",
                authorizer_appid=authorizer_appid,
                authorizer_access_token=authorizer_access_token,
                authorizer_refresh_token=authorizer_refresh_token,
                authorizer_token_expires_at=expires_at,
                access_token=authorizer_access_token,
                token_expires_at=expires_at,
                nick_name=nick_name,
                head_img=head_img,
                service_type=service_type,
                verify_type=verify_type,
            )
            db.add(account)
            await db.commit()
            await db.refresh(account)
            logger.info(
                "Created new account id=%d for authorizer_appid=%s", account.id, authorizer_appid
            )

        # Return a nice HTML success page
        display_name = nick_name or authorizer_appid
        html = f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><title>授权成功</title></head>
<body style="font-family:sans-serif;text-align:center;padding:60px 20px;">
<h2 style="color:#07c160;">✅ 授权成功！</h2>
<p>公众号 <strong>{display_name}</strong> 已成功授权给 Agent Publisher。</p>
<p style="color:#999;font-size:14px;">请返回 Agent Publisher 管理界面查看。</p>
<script>setTimeout(function(){{ window.close(); }}, 3000);</script>
</body>
</html>"""
        return Response(content=html, media_type="text/html; charset=utf-8")

    except Exception as e:
        logger.error("Auth callback failed: %s", e, exc_info=True)
        html = f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><title>授权失败</title></head>
<body style="font-family:sans-serif;text-align:center;padding:60px 20px;">
<h2 style="color:#e34d59;">❌ 授权失败</h2>
<p>{str(e)}</p>
<p style="color:#999;font-size:14px;">请返回 Agent Publisher 重试，或联系管理员。</p>
</body>
</html>"""
        return Response(content=html, media_type="text/html; charset=utf-8", status_code=400)


@router.post("/ticket-callback")
async def ticket_callback(request: Request):
    """Receive component_verify_ticket from WeChat.

    WeChat pushes component_verify_ticket every 10 minutes to this endpoint.
    The payload is encrypted XML that we need to decrypt.

    This endpoint must be publicly accessible via HTTPS and configured
    as the "授权事件接收URL" in the WeChat Open Platform settings.

    Query params: msg_signature, timestamp, nonce (for signature verification)
    Body: encrypted XML
    """
    msg_signature = request.query_params.get("msg_signature", "")
    timestamp = request.query_params.get("timestamp", "")
    nonce = request.query_params.get("nonce", "")

    body = await request.body()
    xml_content = body.decode("utf-8")

    logger.info(
        "Ticket callback received: signature=%s, timestamp=%s", msg_signature[:8] + "...", timestamp
    )

    try:
        # Decrypt the message
        plain_xml = CryptoUtils.decrypt_message(xml_content, msg_signature, timestamp, nonce)

        # Parse the decrypted XML to extract InfoType and ComponentVerifyTicket
        import xml.etree.ElementTree as ET

        root = ET.fromstring(plain_xml)
        info_type = root.findtext("InfoType", "")
        appid = root.findtext("AppId", "")

        logger.info("Ticket callback: InfoType=%s, AppId=%s", info_type, appid)

        if info_type == "component_verify_ticket":
            ticket = root.findtext("ComponentVerifyTicket", "")
            if ticket:
                await WeChatPlatformService.store_verify_ticket(ticket)
                logger.info("Stored component_verify_ticket successfully")
            else:
                logger.warning("component_verify_ticket is empty in the push message")

        elif info_type == "unauthorized":
            # Account unauthorized event
            authorizer_appid = root.findtext("AuthorizerAppid", "")
            logger.warning("Account unauthorized: authorizer_appid=%s", authorizer_appid)
            # Mark account as unauthorized in database
            from agent_publisher.database import async_session_factory

            async with async_session_factory() as session:
                result = await session.execute(
                    select(Account).where(Account.authorizer_appid == authorizer_appid)
                )
                account = result.scalar_one_or_none()
                if account:
                    account.auth_mode = "unauthorized"
                    account.authorizer_access_token = ""
                    account.authorizer_refresh_token = ""
                    account.access_token = ""
                    await session.commit()
                    logger.info("Marked account id=%d as unauthorized", account.id)

        elif info_type == "updateauthorized":
            # Authorization updated event
            authorizer_appid = root.findtext("AuthorizerAppid", "")
            authorization_code = root.findtext("AuthorizationCode", "")
            logger.info(
                "Authorization updated: appid=%s, code=%s",
                authorizer_appid,
                authorization_code[:8] + "...",
            )

        else:
            logger.info("Unhandled InfoType: %s", info_type)

    except ValueError as e:
        logger.error("Ticket callback decryption/signature failed: %s", e)
        return Response(content="success", media_type="text/plain")
    except Exception as e:
        logger.error("Ticket callback processing failed: %s", e, exc_info=True)
        return Response(content="success", media_type="text/plain")

    # WeChat expects "success" as response for all callback pushes
    return Response(content="success", media_type="text/plain")


@router.post("/event-callback")
async def event_callback(request: Request):
    """Handle authorization change events from WeChat.

    This endpoint serves as the "授权事件接收URL" for events like:
    - unauthorized: Account cancels authorization
    - updateauthorized: Authorization updated (permissions changed)
    - notify: Third-party platform ticket push

    Note: For simplicity, we handle both ticket and events in ticket-callback.
    This endpoint is kept for potential future separation.
    """
    msg_signature = request.query_params.get("msg_signature", "")
    timestamp = request.query_params.get("timestamp", "")
    nonce = request.query_params.get("nonce", "")

    body = await request.body()
    xml_content = body.decode("utf-8")

    try:
        plain_xml = CryptoUtils.decrypt_message(xml_content, msg_signature, timestamp, nonce)
        import xml.etree.ElementTree as ET

        root = ET.fromstring(plain_xml)
        info_type = root.findtext("InfoType", "")
        logger.info("Event callback: InfoType=%s", info_type)
    except Exception as e:
        logger.error("Event callback processing failed: %s", e)

    return Response(content="success", media_type="text/plain")
