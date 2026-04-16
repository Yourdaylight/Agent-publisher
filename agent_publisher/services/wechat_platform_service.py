"""WeChat Third-party Platform Service — 扫码授权公众号的核心逻辑.

实现微信第三方平台授权流程：
1. 接收 component_verify_ticket（微信每10分钟推送）
2. 获取 component_access_token
3. 获取 pre_auth_code（预授权码）
4. 构建扫码授权链接
5. 处理授权回调，换取 authorizer_access_token
6. 刷新 authorizer_access_token

前置配置:
- 在微信开放平台 https://open.weixin.qq.com 注册第三方平台
- 获取 component_appid, component_secret, token, aes_key
- 配置到 .env 中对应的 WECHAT_PLATFORM_* 变量
- 详见 docs/wechat-platform-setup.md
"""

from __future__ import annotations

import hashlib
import logging
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone

import httpx
from sqlalchemy import select

from agent_publisher.config import settings

logger = logging.getLogger(__name__)

PLATFORM_API_BASE = "https://api.weixin.qq.com/cgi-bin/component"

# In-memory cache for component_access_token
_component_token_cache: dict = {}  # {"token": str, "expires_at": float}


def _platform_client(timeout: int = 30) -> httpx.AsyncClient:
    """Create an httpx AsyncClient for WeChat Platform API calls."""
    proxy = settings.wechat_proxy.strip() or None
    kwargs: dict = {"timeout": timeout}
    if proxy:
        kwargs["proxy"] = proxy
    return httpx.AsyncClient(**kwargs)


class CryptoUtils:
    """WeChat message encryption/decryption utilities.

    Simplified implementation for component_verify_ticket decryption.
    Uses AES-CBC with the encoding_aes_key from the platform config.
    """

    @staticmethod
    def decrypt_message(xml_content: str, msg_signature: str, timestamp: str, nonce: str) -> str:
        """Decrypt a WeChat push message and return the plain XML.

        Args:
            xml_content: The raw XML body from WeChat push.
            msg_signature: The msg_signature query parameter for verification.
            timestamp: The timestamp query parameter.
            nonce: The nonce query parameter.

        Returns:
            Decrypted plain XML string.

        Raises:
            ValueError: If signature verification fails or decryption fails.
        """
        aes_key = settings.wechat_platform_aes_key.strip()
        token = settings.wechat_platform_token.strip()
        appid = settings.wechat_platform_appid.strip()

        if not aes_key or not token or not appid:
            raise ValueError("WeChat Platform config incomplete (token/aes_key/appid)")

        # Parse encrypted content from XML
        root = ET.fromstring(xml_content)
        encrypt = root.findtext("Encrypt", "")

        # Verify signature: sort(token, timestamp, nonce, encrypt) → SHA1
        sign_list = sorted([token, timestamp, nonce, encrypt])
        sign_str = "".join(sign_list)
        computed_sig = hashlib.sha1(sign_str.encode("utf-8")).hexdigest()

        if computed_sig != msg_signature:
            raise ValueError(
                f"Signature mismatch: computed={computed_sig}, expected={msg_signature}"
            )

        # Decode the AES key (append "=" to make base64-decodable 32-byte key)
        import base64

        decoded_key = base64.b64decode(aes_key + "=")
        iv = decoded_key[:16]

        # Decrypt with AES-CBC
        from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
        from cryptography.hazmat.backends import default_backend

        cipher = Cipher(algorithms.AES(decoded_key), modes.CBC(iv), backend=default_backend())
        decryptor = cipher.decryptor()
        encrypted_data = base64.b64decode(encrypt)
        decrypted = decryptor.update(encrypted_data) + decryptor.finalize()

        # Remove PKCS#7 padding
        pad_len = decrypted[-1]
        decrypted = decrypted[:-pad_len]

        # Format: 16-byte random + 4-byte msg_len (big-endian) + msg + appid
        msg_len = int.from_bytes(decrypted[16:20], byteorder="big")
        msg = decrypted[20 : 20 + msg_len].decode("utf-8")
        received_appid = decrypted[20 + msg_len :].decode("utf-8")

        if received_appid != appid:
            raise ValueError(f"AppID mismatch: received={received_appid}, expected={appid}")

        return msg


class WeChatPlatformService:
    """微信第三方平台服务 — 处理扫码授权流程."""

    @staticmethod
    def is_configured() -> bool:
        """Check if WeChat Platform is properly configured."""
        return bool(
            settings.wechat_platform_appid.strip()
            and settings.wechat_platform_secret.strip()
            and settings.wechat_platform_token.strip()
            and settings.wechat_platform_aes_key.strip()
        )

    @staticmethod
    async def store_verify_ticket(ticket: str) -> None:
        """Store component_verify_ticket to database."""
        from agent_publisher.database import async_session_factory
        from agent_publisher.models.platform_ticket import PlatformTicket

        async with async_session_factory() as session:
            # Keep only the latest ticket (delete old ones)
            result = await session.execute(select(PlatformTicket))
            old_tickets = result.scalars().all()
            for old in old_tickets:
                await session.delete(old)

            new_ticket = PlatformTicket(ticket=ticket)
            session.add(new_ticket)
            await session.commit()
            logger.info("Stored new component_verify_ticket")

    @staticmethod
    async def get_verify_ticket() -> str | None:
        """Get the latest component_verify_ticket from database."""
        from agent_publisher.database import async_session_factory
        from agent_publisher.models.platform_ticket import PlatformTicket

        async with async_session_factory() as session:
            result = await session.execute(
                select(PlatformTicket).order_by(PlatformTicket.received_at.desc()).limit(1)
            )
            ticket = result.scalar_one_or_none()
            if ticket:
                # Verify ticket is not too old (should be pushed every 10 min)
                age = datetime.now(timezone.utc) - ticket.received_at.replace(tzinfo=timezone.utc)
                if age > timedelta(minutes=15):
                    logger.warning("component_verify_ticket is older than 15 minutes")
                return ticket.ticket
        return None

    @staticmethod
    async def get_component_access_token() -> str:
        """Get component_access_token (cached in memory).

        Uses the component_verify_ticket to obtain the token.
        Token is valid for 2 hours; we cache it with a 1.5 hour TTL.
        """
        global _component_token_cache

        now = time.time()
        if _component_token_cache.get("expires_at", 0) > now:
            return _component_token_cache["token"]

        ticket = await WeChatPlatformService.get_verify_ticket()
        if not ticket:
            raise RuntimeError(
                "component_verify_ticket not available. "
                "Ensure WeChat Platform callback URL is correctly configured and "
                "WeChat is pushing tickets every 10 minutes."
            )

        url = f"{PLATFORM_API_BASE}/api_component_token"
        payload = {
            "component_appid": settings.wechat_platform_appid,
            "component_appsecret": settings.wechat_platform_secret,
            "component_verify_ticket": ticket,
        }

        async with _platform_client(timeout=30) as client:
            resp = await client.post(url, json=payload)
            resp.raise_for_status()
            data = resp.json()

        if "errcode" in data and data["errcode"] != 0:
            raise RuntimeError(
                f"Failed to get component_access_token: "
                f"errcode={data.get('errcode')} errmsg={data.get('errmsg')}"
            )

        token = data["component_access_token"]
        expires_in = data.get("expires_in", 7200)
        _component_token_cache = {
            "token": token,
            "expires_at": now + min(expires_in - 300, 5400),  # max 1.5h
        }

        logger.info("Got component_access_token, expires_in=%ds", expires_in)
        return token

    @staticmethod
    async def get_pre_auth_code() -> str:
        """Get pre_auth_code for building the authorization URL."""
        token = await WeChatPlatformService.get_component_access_token()
        url = f"{PLATFORM_API_BASE}/api_create_preauthcode"
        params = {"component_access_token": token}
        payload = {"component_appid": settings.wechat_platform_appid}

        async with _platform_client(timeout=30) as client:
            resp = await client.post(url, params=params, json=payload)
            resp.raise_for_status()
            data = resp.json()

        if "errcode" in data and data["errcode"] != 0:
            raise RuntimeError(
                f"Failed to get pre_auth_code: "
                f"errcode={data.get('errcode')} errmsg={data.get('errmsg')}"
            )

        pre_auth_code = data["pre_auth_code"]
        logger.info("Got pre_auth_code: %s", pre_auth_code[:10] + "...")
        return pre_auth_code

    @staticmethod
    def build_auth_url(pre_auth_code: str, redirect_uri: str, auth_type: int = 1) -> str:
        """Build the PC scan authorization URL.

        Args:
            pre_auth_code: Pre-authorization code from get_pre_auth_code().
            redirect_uri: Callback URL after authorization (HTTPS required).
            auth_type: Account type to show on auth page.
                1 = Only 公众号 (Official Account)
                2 = Only 小程序 (Mini Program)
                3 = Both 公众号 + 小程序

        Returns:
            Full authorization URL that displays a QR code for scanning.
        """
        return (
            f"https://mp.weixin.qq.com/cgi-bin/componentloginpage"
            f"?component_appid={settings.wechat_platform_appid}"
            f"&pre_auth_code={pre_auth_code}"
            f"&redirect_uri={redirect_uri}"
            f"&auth_type={auth_type}"
        )

    @staticmethod
    def build_h5_auth_url(
        pre_auth_code: str, redirect_uri: str, auth_type: int = 1, biz_appid: str = ""
    ) -> str:
        """Build the H5 (mobile) authorization URL.

        This URL can be opened directly in WeChat's built-in browser,
        allowing authorization without scanning a QR code.
        """
        base = (
            f"https://open.weixin.qq.com/wxaopen/safe/bindcomponent"
            f"?action=bindcomponent&no_scan=1"
            f"&component_appid={settings.wechat_platform_appid}"
            f"&pre_auth_code={pre_auth_code}"
            f"&redirect_uri={redirect_uri}"
            f"&auth_type={auth_type}"
        )
        if biz_appid:
            base += f"&biz_appid={biz_appid}"
        base += "#wechat_redirect"
        return base

    @staticmethod
    async def handle_auth_callback(auth_code: str) -> dict:
        """Process the authorization callback.

        Exchange auth_code for authorizer_access_token and authorizer info.

        Args:
            auth_code: The authorization code received from the callback.

        Returns:
            Dict with authorizer info:
            - authorizer_appid
            - authorizer_access_token
            - authorizer_refresh_token
            - expires_in
        """
        token = await WeChatPlatformService.get_component_access_token()
        url = f"{PLATFORM_API_BASE}/api_query_auth"
        params = {"component_access_token": token}
        payload = {
            "component_appid": settings.wechat_platform_appid,
            "authorization_code": auth_code,
        }

        async with _platform_client(timeout=30) as client:
            resp = await client.post(url, params=params, json=payload)
            resp.raise_for_status()
            data = resp.json()

        if "errcode" in data and data["errcode"] != 0:
            raise RuntimeError(
                f"Failed to query auth: errcode={data.get('errcode')} errmsg={data.get('errmsg')}"
            )

        auth_info = data.get("authorization_info", {})
        authorizer_appid = auth_info.get("authorizer_appid", "")
        authorizer_access_token = auth_info.get("authorizer_access_token", "")
        authorizer_refresh_token = auth_info.get("authorizer_refresh_token", "")
        expires_in = auth_info.get("expires_in", 7200)

        logger.info(
            "Authorization successful: authorizer_appid=%s, expires_in=%ds",
            authorizer_appid,
            expires_in,
        )

        return {
            "authorizer_appid": authorizer_appid,
            "authorizer_access_token": authorizer_access_token,
            "authorizer_refresh_token": authorizer_refresh_token,
            "expires_in": expires_in,
            "func_info": auth_info.get("func_info", []),
        }

    @staticmethod
    async def get_authorizer_info(authorizer_appid: str) -> dict:
        """Get authorizer's basic info (nickname, avatar, type, etc.).

        Args:
            authorizer_appid: The authorized account's AppID.

        Returns:
            Dict with authorizer info (nick_name, head_img, service_type, etc.)
        """
        token = await WeChatPlatformService.get_component_access_token()
        url = f"{PLATFORM_API_BASE}/api_get_authorizer_info"
        params = {"component_access_token": token}
        payload = {
            "component_appid": settings.wechat_platform_appid,
            "authorizer_appid": authorizer_appid,
        }

        async with _platform_client(timeout=30) as client:
            resp = await client.post(url, params=params, json=payload)
            resp.raise_for_status()
            data = resp.json()

        if "errcode" in data and data["errcode"] != 0:
            raise RuntimeError(
                f"Failed to get authorizer info: "
                f"errcode={data.get('errcode')} errmsg={data.get('errmsg')}"
            )

        authorizer_info = data.get("authorizer_info", {})
        logger.info("Got authorizer info: nick_name=%s", authorizer_info.get("nick_name", ""))
        return authorizer_info

    @staticmethod
    async def refresh_authorizer_token(
        authorizer_appid: str, authorizer_refresh_token: str
    ) -> tuple[str, datetime]:
        """Refresh the authorizer_access_token.

        Args:
            authorizer_appid: The authorized account's AppID.
            authorizer_refresh_token: The refresh token for the authorizer.

        Returns:
            Tuple of (new_access_token, expires_at).
        """
        token = await WeChatPlatformService.get_component_access_token()
        url = f"{PLATFORM_API_BASE}/api_authorizer_token"
        params = {"component_access_token": token}
        payload = {
            "component_appid": settings.wechat_platform_appid,
            "authorizer_appid": authorizer_appid,
            "authorizer_refresh_token": authorizer_refresh_token,
        }

        async with _platform_client(timeout=30) as client:
            resp = await client.post(url, params=params, json=payload)
            resp.raise_for_status()
            data = resp.json()

        if "errcode" in data and data["errcode"] != 0:
            raise RuntimeError(
                f"Failed to refresh authorizer token: "
                f"errcode={data.get('errcode')} errmsg={data.get('errmsg')}"
            )

        new_token = data["authorizer_access_token"]
        expires_in = data.get("expires_in", 7200)
        expires_at = datetime.now(timezone.utc) + timedelta(seconds=expires_in - 300)

        logger.info(
            "Refreshed authorizer_access_token for appid=%s, expires_in=%ds",
            authorizer_appid,
            expires_in,
        )
        return new_token, expires_at

    @staticmethod
    async def get_authorizer_list(offset: int = 0, count: int = 100) -> dict:
        """Get list of all authorized accounts.

        Args:
            offset: Start offset.
            count: Number of records to return (max 100).

        Returns:
            Dict with total_count and list of authorizer_appid.
        """
        token = await WeChatPlatformService.get_component_access_token()
        url = f"{PLATFORM_API_BASE}/api_get_authorizer_list"
        params = {"component_access_token": token}
        payload = {
            "component_appid": settings.wechat_platform_appid,
            "offset": offset,
            "count": count,
        }

        async with _platform_client(timeout=30) as client:
            resp = await client.post(url, params=params, json=payload)
            resp.raise_for_status()
            data = resp.json()

        if "errcode" in data and data["errcode"] != 0:
            raise RuntimeError(
                f"Failed to get authorizer list: "
                f"errcode={data.get('errcode')} errmsg={data.get('errmsg')}"
            )

        return data
