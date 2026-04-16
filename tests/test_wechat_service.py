from __future__ import annotations

import pytest

from agent_publisher.services.wechat_service import WeChatService


@pytest.mark.asyncio
async def test_get_access_token_error():
    """WeChat token request with invalid credentials should raise."""
    # This will fail because appid/secret are invalid, but tests the error handling path
    with pytest.raises(Exception):
        await WeChatService.get_access_token("invalid_appid", "invalid_secret")
