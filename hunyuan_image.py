"""
Hunyuan Text-to-Image — standalone reusable module.

Usage:
    1. As async library:

        from hunyuan_image import HunyuanImageClient

        client = HunyuanImageClient(secret_id="xxx", secret_key="yyy")
        url = await client.generate("a cute cat in space")

    2. As CLI:

        # via env vars
        export TENCENT_SECRET_ID=xxx
        export TENCENT_SECRET_KEY=yyy
        python hunyuan_image.py "a cute cat in space"

        # via args
        python hunyuan_image.py --secret-id xxx --secret-key yyy "a cute cat in space"

Dependencies:
    pip install tencentcloud-sdk-python-aiart
"""

from __future__ import annotations

import asyncio
import base64
import json
import logging
import os
from functools import partial
from typing import Any

from tencentcloud.common import credential
from tencentcloud.common.profile.client_profile import ClientProfile
from tencentcloud.common.profile.http_profile import HttpProfile
from tencentcloud.aiart.v20221229 import aiart_client, models

__all__ = ["HunyuanImageClient"]

logger = logging.getLogger(__name__)

# ─── Constants ────────────────────────────────────────────────────────
DEFAULT_REGION = "ap-guangzhou"
DEFAULT_ENDPOINT = "aiart.tencentcloudapi.com"
DEFAULT_RESOLUTION = "1024:1024"
DEFAULT_MAX_WAIT = 120  # seconds
DEFAULT_POLL_INTERVAL = 5  # seconds

# Job status codes returned by Tencent Cloud
_STATUS_COMPLETED = "5"
_STATUS_FAILED = "6"


# ─── Client ───────────────────────────────────────────────────────────
class HunyuanImageClient:
    """Standalone async client for Tencent Hunyuan text-to-image generation.

    Parameters
    ----------
    secret_id : str
        Tencent Cloud SecretId. Falls back to env var ``TENCENT_SECRET_ID``.
    secret_key : str
        Tencent Cloud SecretKey. Falls back to env var ``TENCENT_SECRET_KEY``.
    region : str
        API region, default ``ap-guangzhou``.
    endpoint : str
        API endpoint, default ``aiart.tencentcloudapi.com``.
    """

    def __init__(
        self,
        secret_id: str | None = None,
        secret_key: str | None = None,
        region: str = DEFAULT_REGION,
        endpoint: str = DEFAULT_ENDPOINT,
    ):
        self.secret_id = secret_id or os.environ.get("TENCENT_SECRET_ID", "")
        self.secret_key = secret_key or os.environ.get("TENCENT_SECRET_KEY", "")
        if not self.secret_id or not self.secret_key:
            raise ValueError(
                "Tencent Cloud credentials required. "
                "Pass secret_id/secret_key or set TENCENT_SECRET_ID/TENCENT_SECRET_KEY env vars."
            )
        self.region = region
        self.endpoint = endpoint
        self._client: aiart_client.AiartClient | None = None

    # ── SDK client (lazy init) ────────────────────────────────────────

    def _get_client(self) -> aiart_client.AiartClient:
        """Lazily create and cache the Tencent Cloud Aiart client."""
        if self._client is None:
            cred = credential.Credential(self.secret_id, self.secret_key)
            http_profile = HttpProfile()
            http_profile.endpoint = self.endpoint
            client_profile = ClientProfile()
            client_profile.httpProfile = http_profile
            self._client = aiart_client.AiartClient(cred, self.region, client_profile)
        return self._client

    # ── Core API methods ──────────────────────────────────────────────

    async def submit_job(
        self,
        prompt: str,
        resolution: str = DEFAULT_RESOLUTION,
        *,
        revise: int = 0,
        logo_add: int = 0,
        extra_params: dict[str, Any] | None = None,
    ) -> str:
        """Submit a text-to-image job. Returns the JobId.

        Parameters
        ----------
        prompt : str
            Image description text.
        resolution : str
            Image resolution, e.g. ``"1024:1024"``.
        revise : int
            Whether to enable prompt revision (0=off, 1=on).
        logo_add : int
            Whether to add watermark (0=off, 1=on).
        extra_params : dict, optional
            Additional params forwarded to the API request.
        """
        req = models.SubmitTextToImageJobRequest()
        params: dict[str, Any] = {
            "Prompt": prompt,
            "Resolution": resolution,
            "Revise": revise,
            "LogoAdd": logo_add,
        }
        if extra_params:
            params.update(extra_params)
        req.from_json_string(json.dumps(params))

        loop = asyncio.get_running_loop()
        resp = await loop.run_in_executor(
            None, partial(self._get_client().SubmitTextToImageJob, req)
        )
        job_id: str = resp.JobId
        logger.info("Hunyuan image job submitted: %s", job_id)
        return job_id

    async def query_result(self, job_id: str) -> dict[str, Any]:
        """Query the result of a text-to-image job.

        Returns the full API response as a dict.
        """
        req = models.QueryTextToImageJobRequest()
        req.from_json_string(json.dumps({"JobId": job_id}))

        loop = asyncio.get_running_loop()
        resp = await loop.run_in_executor(
            None, partial(self._get_client().QueryTextToImageJob, req)
        )
        return json.loads(resp.to_json_string())

    async def generate(
        self,
        prompt: str,
        resolution: str = DEFAULT_RESOLUTION,
        *,
        max_wait: int = DEFAULT_MAX_WAIT,
        poll_interval: int = DEFAULT_POLL_INTERVAL,
        revise: int = 0,
        logo_add: int = 0,
        extra_params: dict[str, Any] | None = None,
    ) -> str:
        """Submit job, poll until completion, and return the image URL or base64 data.

        Parameters
        ----------
        prompt : str
            Image description.
        resolution : str
            Resolution string, default ``"1024:1024"``.
        max_wait : int
            Max seconds to wait before raising ``TimeoutError``.
        poll_interval : int
            Seconds between status polls.
        revise : int
            Enable prompt revision (0/1).
        logo_add : int
            Enable watermark (0/1).
        extra_params : dict, optional
            Extra API parameters.

        Returns
        -------
        str
            Image URL or base64-encoded image data.

        Raises
        ------
        RuntimeError
            If the job fails or completes with no image.
        TimeoutError
            If the job does not complete within ``max_wait`` seconds.
        """
        job_id = await self.submit_job(
            prompt,
            resolution,
            revise=revise,
            logo_add=logo_add,
            extra_params=extra_params,
        )

        elapsed = 0
        while elapsed < max_wait:
            await asyncio.sleep(poll_interval)
            elapsed += poll_interval
            result = await self.query_result(job_id)
            status = result.get("JobStatusCode")

            if status == _STATUS_COMPLETED:
                image = result.get("ResultImage", "")
                if isinstance(image, list):
                    image = image[0] if image else ""
                if image:
                    logger.info("Hunyuan image generated for job %s", job_id)
                    return image
                raise RuntimeError(f"Job {job_id} completed but no image returned")

            if status == _STATUS_FAILED:
                error_msg = result.get("JobErrorMsg", "Unknown error")
                raise RuntimeError(f"Image generation failed: {error_msg}")

            logger.debug("Job %s status: %s, waiting...", job_id, status)

        raise TimeoutError(
            f"Image generation timed out after {max_wait}s for job {job_id}"
        )

    # ── Utilities ─────────────────────────────────────────────────────

    @staticmethod
    def base64_to_bytes(b64_data: str) -> bytes:
        """Decode base64 image data to raw bytes."""
        return base64.b64decode(b64_data)


# ─── CLI Entry Point ──────────────────────────────────────────────────
def main() -> None:
    """Simple CLI for quick testing."""
    import argparse

    parser = argparse.ArgumentParser(description="Hunyuan Text-to-Image Generator")
    parser.add_argument("prompt", help="Image description text")
    parser.add_argument("--secret-id", default=None, help="Tencent Cloud SecretId")
    parser.add_argument("--secret-key", default=None, help="Tencent Cloud SecretKey")
    parser.add_argument("--region", default=DEFAULT_REGION, help="API region")
    parser.add_argument("--resolution", default=DEFAULT_RESOLUTION, help="Image resolution (e.g. 1024:1024)")
    parser.add_argument("--max-wait", type=int, default=DEFAULT_MAX_WAIT, help="Max wait seconds")
    parser.add_argument("--poll-interval", type=int, default=DEFAULT_POLL_INTERVAL, help="Poll interval seconds")
    parser.add_argument("-v", "--verbose", action="store_true", help="Verbose logging")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    client = HunyuanImageClient(
        secret_id=args.secret_id,
        secret_key=args.secret_key,
        region=args.region,
    )

    async def _run() -> str:
        return await client.generate(
            prompt=args.prompt,
            resolution=args.resolution,
            max_wait=args.max_wait,
            poll_interval=args.poll_interval,
        )

    result = asyncio.run(_run())
    if result.startswith("http"):
        print(f"Image URL: {result}")
    else:
        print(f"Image generated (base64, {len(result)} chars)")


if __name__ == "__main__":
    main()
