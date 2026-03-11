from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

import httpx

logger = logging.getLogger(__name__)

WECHAT_API_BASE = "https://api.weixin.qq.com/cgi-bin"


class WeChatService:
    @staticmethod
    async def get_access_token(appid: str, appsecret: str) -> tuple[str, datetime]:
        """Get or refresh access token. Returns (token, expires_at)."""
        url = f"{WECHAT_API_BASE}/token"
        params = {"grant_type": "client_credential", "appid": appid, "secret": appsecret}
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(url, params=params)
            resp.raise_for_status()
            data = resp.json()

        if "errcode" in data and data["errcode"] != 0:
            raise RuntimeError(
                f"WeChat token error: {data.get('errcode')} - {data.get('errmsg')}"
            )

        token = data["access_token"]
        expires_in = data.get("expires_in", 7200)
        expires_at = datetime.now(timezone.utc) + timedelta(seconds=expires_in - 300)
        logger.info("Got WeChat access token for appid=%s, expires_in=%ds", appid, expires_in)
        return token, expires_at

    @staticmethod
    async def upload_image(access_token: str, image_data: bytes, filename: str = "image.png") -> str:
        """Upload image as permanent material. Returns media_id."""
        url = f"{WECHAT_API_BASE}/material/add_material"
        params = {"access_token": access_token, "type": "image"}
        files = {"media": (filename, image_data, "image/png")}
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(url, params=params, files=files)
            resp.raise_for_status()
            data = resp.json()

        if "errcode" in data and data["errcode"] != 0:
            raise RuntimeError(f"WeChat upload error: {data}")

        media_id = data.get("media_id", "")
        image_url = data.get("url", "")
        logger.info("Uploaded image: media_id=%s url=%s", media_id, image_url)
        return media_id

    @staticmethod
    async def upload_thumb(access_token: str, image_data: bytes, filename: str = "thumb.jpg") -> str:
        """Upload thumb image. Returns thumb_media_id."""
        url = f"{WECHAT_API_BASE}/material/add_material"
        params = {"access_token": access_token, "type": "thumb"}
        files = {"media": (filename, image_data, "image/jpeg")}
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(url, params=params, files=files)
            resp.raise_for_status()
            data = resp.json()

        if "errcode" in data and data["errcode"] != 0:
            raise RuntimeError(f"WeChat upload thumb error: {data}")

        return data.get("media_id", "")

    @staticmethod
    async def add_draft(
        access_token: str,
        articles: list[dict],
    ) -> str:
        """
        Push articles to draft box. Each article dict should contain:
        - title, author, digest, content (html), thumb_media_id, content_source_url
        Returns media_id of the draft.
        """
        url = f"{WECHAT_API_BASE}/draft/add"
        params = {"access_token": access_token}
        payload = {"articles": articles}
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(url, params=params, json=payload)
            resp.raise_for_status()
            data = resp.json()

        if "errcode" in data and data["errcode"] != 0:
            raise RuntimeError(f"WeChat draft error: {data}")

        media_id = data.get("media_id", "")
        logger.info("Draft created: media_id=%s", media_id)
        return media_id
