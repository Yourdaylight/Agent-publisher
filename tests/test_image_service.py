from __future__ import annotations

import base64

import pytest

from agent_publisher.services.image_service import HunyuanImageService, _sign_tc3


def test_sign_tc3_produces_valid_headers():
    """TC3 signing should produce required headers."""
    headers = _sign_tc3(
        secret_id="test_id",
        secret_key="test_key",
        action="SubmitTextToImageJob",
        payload={"Prompt": "test"},
        timestamp=1700000000,
    )
    assert "Authorization" in headers
    assert headers["X-TC-Action"] == "SubmitTextToImageJob"
    assert headers["X-TC-Version"] == "2022-12-29"
    assert "TC3-HMAC-SHA256" in headers["Authorization"]


def test_base64_to_bytes():
    """base64_to_bytes should correctly decode."""
    original = b"hello world"
    encoded = base64.b64encode(original).decode()
    result = HunyuanImageService.base64_to_bytes(encoded)
    assert result == original


@pytest.mark.asyncio
async def test_submit_job_requires_credentials():
    """submit_job with empty credentials should fail at API call."""
    svc = HunyuanImageService(secret_id="", secret_key="")
    with pytest.raises(Exception):
        await svc.submit_job("test prompt")
