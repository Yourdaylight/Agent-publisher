from __future__ import annotations

import asyncio
import base64
import json
import logging
from functools import partial

from tencentcloud.common import credential
from tencentcloud.common.profile.client_profile import ClientProfile
from tencentcloud.common.profile.http_profile import HttpProfile
from tencentcloud.aiart.v20221229 import aiart_client, models

from agent_publisher.config import settings

logger = logging.getLogger(__name__)

HUNYUAN_REGION = "ap-guangzhou"


class HunyuanImageService:
    def __init__(
        self,
        secret_id: str | None = None,
        secret_key: str | None = None,
    ):
        self.secret_id = secret_id or settings.tencent_secret_id
        self.secret_key = secret_key or settings.tencent_secret_key
        self._client: aiart_client.AiartClient | None = None

    def _get_client(self) -> aiart_client.AiartClient:
        """Lazily create and cache the Tencent Cloud Aiart client."""
        if self._client is None:
            cred = credential.Credential(self.secret_id, self.secret_key)
            http_profile = HttpProfile()
            http_profile.endpoint = "aiart.tencentcloudapi.com"
            client_profile = ClientProfile()
            client_profile.httpProfile = http_profile
            self._client = aiart_client.AiartClient(cred, HUNYUAN_REGION, client_profile)
        return self._client

    async def submit_job(self, prompt: str, resolution: str = "1024:1024") -> str:
        """Submit a text-to-image job. Returns JobId."""
        req = models.SubmitTextToImageJobRequest()
        params = {"Prompt": prompt, "Resolution": resolution, "Revise": 0, "LogoAdd": 0}
        req.from_json_string(json.dumps(params))

        loop = asyncio.get_event_loop()
        resp = await loop.run_in_executor(
            None, partial(self._get_client().SubmitTextToImageJob, req)
        )
        job_id = resp.JobId
        logger.info("Hunyuan image job submitted: %s", job_id)
        return job_id

    async def query_result(self, job_id: str) -> dict:
        """Query the result of a text-to-image job."""
        req = models.QueryTextToImageJobRequest()
        req.from_json_string(json.dumps({"JobId": job_id}))

        loop = asyncio.get_event_loop()
        resp = await loop.run_in_executor(
            None, partial(self._get_client().QueryTextToImageJob, req)
        )
        # Convert SDK response to dict for easier access
        return json.loads(resp.to_json_string())

    async def generate_image(
        self,
        prompt: str,
        resolution: str = "1024:1024",
        max_wait: int = 120,
        poll_interval: int = 5,
    ) -> str:
        """Submit job and poll until completion. Returns image URL or base64 data."""
        job_id = await self.submit_job(prompt, resolution)

        elapsed = 0
        while elapsed < max_wait:
            await asyncio.sleep(poll_interval)
            elapsed += poll_interval
            result = await self.query_result(job_id)
            job_status = result.get("JobStatusCode")

            if job_status == "5":  # completed
                result_image = result.get("ResultImage", "")
                # ResultImage may be a list of URLs; extract the first one
                if isinstance(result_image, list):
                    result_image = result_image[0] if result_image else ""
                if result_image:
                    logger.info("Hunyuan image generated successfully for job %s", job_id)
                    return result_image
                raise RuntimeError(f"Job {job_id} completed but no image returned")

            if job_status == "6":  # failed
                error_msg = result.get("JobErrorMsg", "Unknown error")
                raise RuntimeError(f"Image generation failed: {error_msg}")

            logger.debug("Job %s status: %s, waiting...", job_id, job_status)

        raise TimeoutError(f"Image generation timed out after {max_wait}s for job {job_id}")

    @staticmethod
    def base64_to_bytes(b64_data: str) -> bytes:
        """Convert base64 string to bytes (for uploading to WeChat)."""
        return base64.b64decode(b64_data)
