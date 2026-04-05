from __future__ import annotations

import logging
import mimetypes
from datetime import datetime, timedelta, timezone

import httpx

logger = logging.getLogger(__name__)

WECHAT_API_BASE = "https://api.weixin.qq.com/cgi-bin"


def _wechat_client(timeout: int = 30) -> httpx.AsyncClient:
    """Create an httpx AsyncClient for WeChat API calls.

    If ``settings.wechat_proxy`` is configured, routes all requests through
    that HTTP proxy. Only WeChat API calls use this proxy — no other services
    are affected.
    """
    from agent_publisher.config import settings

    proxy = settings.wechat_proxy.strip() or None
    kwargs: dict = {"timeout": timeout}
    if proxy:
        kwargs["proxy"] = proxy
    return httpx.AsyncClient(**kwargs)


class WeChatService:
    @staticmethod
    async def get_access_token(appid: str, appsecret: str) -> tuple[str, datetime]:
        """Get or refresh access token. Returns (token, expires_at)."""
        url = f"{WECHAT_API_BASE}/token"
        params = {"grant_type": "client_credential", "appid": appid, "secret": appsecret}
        async with _wechat_client(timeout=30) as client:
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
        async with _wechat_client(timeout=60) as client:
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
        async with _wechat_client(timeout=60) as client:
            resp = await client.post(url, params=params, files=files)
            resp.raise_for_status()
            data = resp.json()

        if "errcode" in data and data["errcode"] != 0:
            raise RuntimeError(f"WeChat upload thumb error: {data}")

        return data.get("media_id", "")

    @staticmethod
    async def upload_article_image(
        access_token: str,
        image_data: bytes,
        filename: str = "image.png",
        content_type: str | None = None,
    ) -> str:
        """Upload an inline article image and return the WeChat-hosted image URL."""
        url = f"{WECHAT_API_BASE}/media/uploadimg"
        params = {"access_token": access_token}
        resolved_content_type = (
            content_type
            or mimetypes.guess_type(filename)[0]
            or "image/png"
        )
        files = {"media": (filename, image_data, resolved_content_type)}

        async with _wechat_client(timeout=60) as client:
            resp = await client.post(url, params=params, files=files)
            resp.raise_for_status()
            data = resp.json()

        WeChatService._check_wechat_error(data, "media/uploadimg")

        image_url = data.get("url", "")
        if not image_url:
            raise RuntimeError("WeChat media/uploadimg returned empty url")

        logger.info("Uploaded article image: filename=%s url=%s", filename, image_url)
        return image_url

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
        async with _wechat_client(timeout=60) as client:
            resp = await client.post(url, params=params, json=payload)
            resp.raise_for_status()
            data = resp.json()

        if "errcode" in data and data["errcode"] != 0:
            raise RuntimeError(f"WeChat draft error: {data}")

        media_id = data.get("media_id", "")
        logger.info("Draft created: media_id=%s", media_id)
        return media_id

    @staticmethod
    async def update_draft(
        access_token: str,
        media_id: str,
        articles: dict,
        index: int = 0,
    ) -> None:
        """
        Update an article in draft box.
        - media_id: the draft media_id returned by add_draft
        - index: position of the article in the draft (0-based)
        - articles: dict with fields to update (title, content, digest, thumb_media_id, etc.)
        """
        url = f"{WECHAT_API_BASE}/draft/update"
        params = {"access_token": access_token}
        payload = {
            "media_id": media_id,
            "index": index,
            "articles": articles,
        }
        async with _wechat_client(timeout=60) as client:
            resp = await client.post(url, params=params, json=payload)
            resp.raise_for_status()
            data = resp.json()

        if "errcode" in data and data["errcode"] != 0:
            raise RuntimeError(f"WeChat draft update error: {data}")

        logger.info("Draft updated: media_id=%s index=%d", media_id, index)

    # ------------------------------------------------------------------
    # WeChat error code mapping (common codes)
    # ------------------------------------------------------------------

    WECHAT_ERROR_MESSAGES = {
        48001: "该公众号没有此接口的权限（需要认证服务号或已认证订阅号）",
        40001: "access_token 无效或已过期，请刷新后重试",
        40003: "非法的 OpenID",
        61500: "日期格式错误或超出允许范围",
    }

    @staticmethod
    def _check_wechat_error(data: dict, context: str = "") -> None:
        """Check WeChat API response for errors and raise with friendly message."""
        errcode = data.get("errcode", 0)
        if errcode != 0:
            friendly = WeChatService.WECHAT_ERROR_MESSAGES.get(errcode, "")
            errmsg = data.get("errmsg", "")
            msg = f"WeChat {context} error {errcode}: {errmsg}"
            if friendly:
                msg += f" ({friendly})"
            raise RuntimeError(msg)

    @staticmethod
    def _split_date_range(begin_date: str, end_date: str, max_days: int) -> list[tuple[str, str]]:
        """Split a date range into chunks of max_days.

        Dates are strings in YYYY-MM-DD format.
        """
        from datetime import date as date_type

        begin = date_type.fromisoformat(begin_date)
        end = date_type.fromisoformat(end_date)
        chunks: list[tuple[str, str]] = []

        current = begin
        while current <= end:
            chunk_end = min(current + timedelta(days=max_days - 1), end)
            chunks.append((current.isoformat(), chunk_end.isoformat()))
            current = chunk_end + timedelta(days=1)

        return chunks

    # ------------------------------------------------------------------
    # Data statistics methods
    # ------------------------------------------------------------------

    @staticmethod
    async def get_user_summary(access_token: str, begin_date: str, end_date: str) -> list[dict]:
        """Get user subscribe/unsubscribe summary data.

        Calls datacube/getusersummary. Max span: 7 days.
        Automatically splits larger ranges into multiple requests.
        """
        chunks = WeChatService._split_date_range(begin_date, end_date, max_days=7)
        all_data: list[dict] = []

        async with _wechat_client(timeout=30) as client:
            for chunk_begin, chunk_end in chunks:
                url = f"{WECHAT_API_BASE.replace('/cgi-bin', '')}/datacube/getusersummary"
                params = {"access_token": access_token}
                payload = {"begin_date": chunk_begin, "end_date": chunk_end}
                resp = await client.post(url, params=params, json=payload)
                resp.raise_for_status()
                data = resp.json()
                WeChatService._check_wechat_error(data, "getusersummary")
                all_data.extend(data.get("list", []))

        logger.info("Got user summary: %d records (%s ~ %s)", len(all_data), begin_date, end_date)
        return all_data

    @staticmethod
    async def get_user_cumulate(access_token: str, begin_date: str, end_date: str) -> list[dict]:
        """Get cumulative user count data.

        Calls datacube/getusercumulate. Max span: 7 days.
        Automatically splits larger ranges.
        """
        chunks = WeChatService._split_date_range(begin_date, end_date, max_days=7)
        all_data: list[dict] = []

        async with _wechat_client(timeout=30) as client:
            for chunk_begin, chunk_end in chunks:
                url = f"{WECHAT_API_BASE.replace('/cgi-bin', '')}/datacube/getusercumulate"
                params = {"access_token": access_token}
                payload = {"begin_date": chunk_begin, "end_date": chunk_end}
                resp = await client.post(url, params=params, json=payload)
                resp.raise_for_status()
                data = resp.json()
                WeChatService._check_wechat_error(data, "getusercumulate")
                all_data.extend(data.get("list", []))

        logger.info("Got user cumulate: %d records (%s ~ %s)", len(all_data), begin_date, end_date)
        return all_data

    @staticmethod
    async def get_article_summary(access_token: str, begin_date: str, end_date: str) -> list[dict]:
        """Get article summary data (daily aggregated).

        Calls datacube/getarticlesummary. Max span: 1 day.
        Automatically splits larger ranges.
        """
        chunks = WeChatService._split_date_range(begin_date, end_date, max_days=1)
        all_data: list[dict] = []

        async with _wechat_client(timeout=30) as client:
            for chunk_begin, chunk_end in chunks:
                url = f"{WECHAT_API_BASE.replace('/cgi-bin', '')}/datacube/getarticlesummary"
                params = {"access_token": access_token}
                payload = {"begin_date": chunk_begin, "end_date": chunk_end}
                resp = await client.post(url, params=params, json=payload)
                resp.raise_for_status()
                data = resp.json()
                WeChatService._check_wechat_error(data, "getarticlesummary")
                all_data.extend(data.get("list", []))

        logger.info("Got article summary: %d records (%s ~ %s)", len(all_data), begin_date, end_date)
        return all_data

    @staticmethod
    async def get_article_total(access_token: str, begin_date: str, end_date: str) -> list[dict]:
        """Get article total data (per-article detail).

        Calls datacube/getarticletotal. Max span: 1 day.
        Automatically splits larger ranges.
        """
        chunks = WeChatService._split_date_range(begin_date, end_date, max_days=1)
        all_data: list[dict] = []

        async with _wechat_client(timeout=30) as client:
            for chunk_begin, chunk_end in chunks:
                url = f"{WECHAT_API_BASE.replace('/cgi-bin', '')}/datacube/getarticletotal"
                params = {"access_token": access_token}
                payload = {"begin_date": chunk_begin, "end_date": chunk_end}
                resp = await client.post(url, params=params, json=payload)
                resp.raise_for_status()
                data = resp.json()
                WeChatService._check_wechat_error(data, "getarticletotal")
                all_data.extend(data.get("list", []))

        logger.info("Got article total: %d records (%s ~ %s)", len(all_data), begin_date, end_date)
        return all_data

    @staticmethod
    async def get_followers(access_token: str, next_openid: str | None = None) -> dict:
        """Get follower list.

        Calls user/get. Returns {"total": int, "count": int, "data": {"openid": [...]}, "next_openid": str}.
        """
        url = f"{WECHAT_API_BASE}/user/get"
        params: dict = {"access_token": access_token}
        if next_openid:
            params["next_openid"] = next_openid

        async with _wechat_client(timeout=30) as client:
            resp = await client.get(url, params=params)
            resp.raise_for_status()
            data = resp.json()

        WeChatService._check_wechat_error(data, "user/get")
        logger.info("Got followers: total=%d count=%d", data.get("total", 0), data.get("count", 0))
        return data
