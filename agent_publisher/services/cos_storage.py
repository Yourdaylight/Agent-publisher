"""COS (Tencent Cloud Object Storage) storage backend for media assets.

When COS is configured (COS_SECRET_ID, COS_SECRET_KEY, COS_BUCKET, COS_REGION
are set), uploaded media is stored in COS instead of (or in addition to) local disk.

This makes media:
- Publicly accessible via CDN URL (can be used directly in WeChat article HTML)
- Durable across server restarts/redeploys
- Offloaded from server disk

Usage:
    storage = CosStorage()
    if storage.enabled:
        url = await storage.upload(content, filename, content_type)
        await storage.delete(key)
"""
from __future__ import annotations

import logging
import mimetypes
import uuid
from pathlib import Path

logger = logging.getLogger(__name__)


class CosStorage:
    """Thin async wrapper around qcloud_cos for media asset storage."""

    def __init__(self) -> None:
        from agent_publisher.config import settings

        secret_id = getattr(settings, "cos_secret_id", "") or ""
        secret_key = getattr(settings, "cos_secret_key", "") or ""
        self.bucket = getattr(settings, "cos_bucket", "") or ""
        self.region = getattr(settings, "cos_region", "ap-beijing") or "ap-beijing"
        self.base_url = getattr(settings, "cos_base_url", "") or ""
        self._client = None

        self.enabled = bool(secret_id and secret_key and self.bucket)
        if not self.enabled:
            return

        try:
            from qcloud_cos import CosConfig, CosS3Client  # type: ignore
            config = CosConfig(
                Region=self.region,
                SecretId=secret_id,
                SecretKey=secret_key,
                Scheme="https",
            )
            self._client = CosS3Client(config)
            logger.info(
                "CosStorage enabled: bucket=%s region=%s",
                self.bucket, self.region,
            )
        except ImportError:
            logger.warning(
                "qcloud_cos not installed. Run: uv add cos-python-sdk-v5. "
                "Falling back to local disk storage."
            )
            self.enabled = False

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def upload(
        self,
        content: bytes,
        filename: str,
        content_type: str | None = None,
        prefix: str = "media",
    ) -> tuple[str, str]:
        """Upload bytes to COS.

        Returns:
            (cos_key, public_url)
            cos_key: e.g. "media/abc123.png"
            public_url: either CDN URL (if cos_base_url set) or COS default URL
        """
        if not self.enabled or not self._client:
            raise RuntimeError("CosStorage is not enabled")

        ext = Path(filename).suffix or (
            mimetypes.guess_extension(content_type or "") or ".bin"
        )
        key = f"{prefix}/{uuid.uuid4().hex}{ext}"
        resolved_ct = content_type or mimetypes.guess_type(filename)[0] or "application/octet-stream"

        import asyncio
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(
            None,
            lambda: self._client.put_object(  # type: ignore[union-attr]
                Bucket=self.bucket,
                Body=content,
                Key=key,
                ContentType=resolved_ct,
                StorageClass="STANDARD",
            ),
        )

        url = self._build_url(key)
        logger.info("COS upload: key=%s size=%d url=%s", key, len(content), url)
        return key, url

    async def delete(self, key: str) -> None:
        """Delete an object from COS by key."""
        if not self.enabled or not self._client:
            return

        import asyncio
        loop = asyncio.get_event_loop()
        try:
            await loop.run_in_executor(
                None,
                lambda: self._client.delete_object(Bucket=self.bucket, Key=key),  # type: ignore[union-attr]
            )
            logger.info("COS delete: key=%s", key)
        except Exception as exc:
            logger.warning("COS delete failed for key=%s: %s", key, exc)

    async def get_url(self, key: str, expires: int = 3600) -> str:
        """Get a pre-signed URL for private objects (or public URL if bucket is public)."""
        if not self.enabled or not self._client:
            raise RuntimeError("CosStorage is not enabled")

        if self.base_url:
            return self._build_url(key)

        import asyncio
        loop = asyncio.get_event_loop()
        url = await loop.run_in_executor(
            None,
            lambda: self._client.get_presigned_url(  # type: ignore[union-attr]
                Method="GET",
                Bucket=self.bucket,
                Key=key,
                Expired=expires,
            ),
        )
        return url

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _build_url(self, key: str) -> str:
        """Build public URL for a COS key."""
        if self.base_url:
            base = self.base_url.rstrip("/")
            return f"{base}/{key}"
        # Default COS URL format
        return f"https://{self.bucket}.cos.{self.region}.myqcloud.com/{key}"


# Module-level singleton — lazily initialised
_cos_storage: CosStorage | None = None


def get_cos_storage() -> CosStorage:
    """Return the module-level CosStorage singleton."""
    global _cos_storage
    if _cos_storage is None:
        _cos_storage = CosStorage()
    return _cos_storage
