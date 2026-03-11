from __future__ import annotations

import asyncio
import base64
import hashlib
import hmac
import json
import logging
import time
from datetime import datetime, timezone

import httpx

from agent_publisher.config import settings

logger = logging.getLogger(__name__)

HUNYUAN_HOST = "aiart.tencentcloudapi.com"
HUNYUAN_SERVICE = "aiart"
HUNYUAN_VERSION = "2022-12-29"
HUNYUAN_REGION = "ap-guangzhou"


def _sign_tc3(
    secret_id: str,
    secret_key: str,
    action: str,
    payload: dict,
    timestamp: int,
) -> dict[str, str]:
    """Generate Tencent Cloud TC3-HMAC-SHA256 signature headers."""
    date = datetime.fromtimestamp(timestamp, tz=timezone.utc).strftime("%Y-%m-%d")
    http_request_method = "POST"
    canonical_uri = "/"
    canonical_querystring = ""
    ct = "application/json"
    canonical_headers = f"content-type:{ct}\nhost:{HUNYUAN_HOST}\nx-tc-action:{action.lower()}\n"
    signed_headers = "content-type;host;x-tc-action"
    payload_str = json.dumps(payload)
    hashed_payload = hashlib.sha256(payload_str.encode()).hexdigest()
    canonical_request = (
        f"{http_request_method}\n{canonical_uri}\n{canonical_querystring}\n"
        f"{canonical_headers}\n{signed_headers}\n{hashed_payload}"
    )
    credential_scope = f"{date}/{HUNYUAN_SERVICE}/tc3_request"
    string_to_sign = (
        f"TC3-HMAC-SHA256\n{timestamp}\n{credential_scope}\n"
        + hashlib.sha256(canonical_request.encode()).hexdigest()
    )

    def _hmac_sha256(key: bytes, msg: str) -> bytes:
        return hmac.new(key, msg.encode(), hashlib.sha256).digest()

    secret_date = _hmac_sha256(f"TC3{secret_key}".encode(), date)
    secret_service = _hmac_sha256(secret_date, HUNYUAN_SERVICE)
    secret_signing = _hmac_sha256(secret_service, "tc3_request")
    signature = hmac.new(secret_signing, string_to_sign.encode(), hashlib.sha256).hexdigest()

    authorization = (
        f"TC3-HMAC-SHA256 Credential={secret_id}/{credential_scope}, "
        f"SignedHeaders={signed_headers}, Signature={signature}"
    )
    return {
        "Authorization": authorization,
        "Content-Type": ct,
        "Host": HUNYUAN_HOST,
        "X-TC-Action": action,
        "X-TC-Version": HUNYUAN_VERSION,
        "X-TC-Timestamp": str(timestamp),
        "X-TC-Region": HUNYUAN_REGION,
    }


class HunyuanImageService:
    def __init__(
        self,
        secret_id: str | None = None,
        secret_key: str | None = None,
    ):
        self.secret_id = secret_id or settings.tencent_secret_id
        self.secret_key = secret_key or settings.tencent_secret_key

    async def _call_api(self, action: str, payload: dict) -> dict:
        timestamp = int(time.time())
        headers = _sign_tc3(self.secret_id, self.secret_key, action, payload, timestamp)
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(
                f"https://{HUNYUAN_HOST}/",
                json=payload,
                headers=headers,
            )
            resp.raise_for_status()
        return resp.json()

    async def submit_job(self, prompt: str, resolution: str = "1024:1024") -> str:
        """Submit a text-to-image job. Returns JobId."""
        payload = {"Prompt": prompt, "Resolution": resolution, "Revise": 0, "LogoAdd": 0}
        data = await self._call_api("SubmitTextToImageJob", payload)
        response = data.get("Response", {})
        if "Error" in response:
            err = response["Error"]
            raise RuntimeError(
                f"Hunyuan API error: [{err.get('Code')}] {err.get('Message')}"
            )
        job_id = response["JobId"]
        logger.info("Hunyuan image job submitted: %s", job_id)
        return job_id

    async def query_result(self, job_id: str) -> dict:
        """Query the result of a text-to-image job."""
        payload = {"JobId": job_id}
        data = await self._call_api("QueryTextToImageJob", payload)
        response = data.get("Response", {})
        if "Error" in response:
            err = response["Error"]
            raise RuntimeError(
                f"Hunyuan API error: [{err.get('Code')}] {err.get('Message')}"
            )
        return response

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
