"""Tests for the HunyuanImageService wrapper."""
from __future__ import annotations

import base64
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from agent_publisher.services.image_service import HunyuanImageService


def test_base64_to_bytes():
    """base64_to_bytes should correctly decode."""
    original = b"hello world"
    encoded = base64.b64encode(original).decode()
    
    # Mock the HunyuanImageClient to have a base64_to_bytes method
    with patch('agent_publisher.services.image_service.HunyuanImageClient') as MockClient:
        MockClient.base64_to_bytes.return_value = original
        result = HunyuanImageService.base64_to_bytes(encoded)
        assert result == original


@pytest.mark.asyncio
async def test_submit_job_requires_credentials():
    """submit_job should forward to the underlying client."""
    with patch('agent_publisher.services.image_service.HunyuanImageClient') as MockClient:
        mock_client_instance = AsyncMock()
        mock_client_instance.submit_job = AsyncMock(return_value="job_123")
        MockClient.return_value = mock_client_instance
        
        svc = HunyuanImageService(secret_id="test_id", secret_key="test_key")
        result = await svc.submit_job("test prompt")
        
        assert result == "job_123"
        mock_client_instance.submit_job.assert_called_once_with("test prompt", "1024:1024")


@pytest.mark.asyncio
async def test_query_result():
    """query_result should forward to the underlying client."""
    with patch('agent_publisher.services.image_service.HunyuanImageClient') as MockClient:
        mock_client_instance = AsyncMock()
        mock_client_instance.query_result = AsyncMock(return_value={"Status": "Success"})
        MockClient.return_value = mock_client_instance
        
        svc = HunyuanImageService(secret_id="test_id", secret_key="test_key")
        result = await svc.query_result("job_123")
        
        assert result == {"Status": "Success"}
        mock_client_instance.query_result.assert_called_once_with("job_123")


@pytest.mark.asyncio
async def test_generate_image():
    """generate_image should forward to the underlying client."""
    with patch('agent_publisher.services.image_service.HunyuanImageClient') as MockClient:
        mock_client_instance = AsyncMock()
        mock_client_instance.generate = AsyncMock(return_value="image_url")
        MockClient.return_value = mock_client_instance
        
        svc = HunyuanImageService(secret_id="test_id", secret_key="test_key")
        result = await svc.generate_image("test prompt", resolution="1024:1024", max_wait=60)
        
        assert result == "image_url"
        mock_client_instance.generate.assert_called_once_with(
            "test prompt", 
            "1024:1024", 
            max_wait=60, 
            poll_interval=5
        )
