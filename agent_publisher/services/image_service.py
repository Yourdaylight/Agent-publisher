"""Hunyuan image service — thin wrapper over the standalone ``hunyuan_image`` module.

This keeps the original ``HunyuanImageService`` API unchanged so existing
callers (CLI, article_service, etc.) continue to work without modification.
"""

from __future__ import annotations

import logging

try:
    from hunyuan_image import HunyuanImageClient
except ImportError:
    HunyuanImageClient = None  # type: ignore[misc,assignment]
from agent_publisher.config import settings

logger = logging.getLogger(__name__)


class HunyuanImageService:
    """Project-level facade that reads credentials from ``settings`` by default."""

    def __init__(
        self,
        secret_id: str | None = None,
        secret_key: str | None = None,
    ):
        sid = secret_id or settings.tencent_secret_id
        skey = secret_key or settings.tencent_secret_key
        self._client = HunyuanImageClient(secret_id=sid, secret_key=skey)

    async def submit_job(self, prompt: str, resolution: str = "1024:1024") -> str:
        """Submit a text-to-image job. Returns JobId."""
        return await self._client.submit_job(prompt, resolution)

    async def query_result(self, job_id: str) -> dict:
        """Query the result of a text-to-image job."""
        return await self._client.query_result(job_id)

    async def generate_image(
        self,
        prompt: str,
        resolution: str = "1024:1024",
        max_wait: int = 120,
        poll_interval: int = 5,
    ) -> str:
        """Submit job and poll until completion. Returns image URL or base64 data."""
        return await self._client.generate(
            prompt, resolution, max_wait=max_wait, poll_interval=poll_interval
        )

    @staticmethod
    def base64_to_bytes(b64_data: str) -> bytes:
        """Convert base64 string to bytes (for uploading to WeChat)."""
        return HunyuanImageClient.base64_to_bytes(b64_data)
