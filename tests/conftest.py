from __future__ import annotations

import sys
import types
from types import SimpleNamespace

import pytest
from httpx import ASGITransport, AsyncClient


def _install_third_party_stubs() -> None:
    credential_module = types.ModuleType('tencentcloud.common.credential')
    credential_module.Credential = object
    client_profile_module = types.ModuleType('tencentcloud.common.profile.client_profile')
    client_profile_module.ClientProfile = object
    http_profile_module = types.ModuleType('tencentcloud.common.profile.http_profile')
    http_profile_module.HttpProfile = object
    aiart_client_module = types.ModuleType('tencentcloud.aiart.v20221229.aiart_client')
    aiart_client_module.AiartClient = object
    models_module = types.ModuleType('tencentcloud.aiart.v20221229.models')
    models_module.SubmitTextToImageJobRequest = object
    models_module.QueryTextToImageJobRequest = object
    feedparser_module = types.ModuleType('feedparser')
    feedparser_module.parse = lambda *_args, **_kwargs: SimpleNamespace(entries=[], feed={})

    sys.modules.setdefault('tencentcloud', types.ModuleType('tencentcloud'))
    sys.modules.setdefault('tencentcloud.common', types.ModuleType('tencentcloud.common'))
    sys.modules.setdefault('tencentcloud.common.profile', types.ModuleType('tencentcloud.common.profile'))
    sys.modules.setdefault('tencentcloud.aiart', types.ModuleType('tencentcloud.aiart'))
    sys.modules.setdefault('tencentcloud.aiart.v20221229', types.ModuleType('tencentcloud.aiart.v20221229'))
    sys.modules['feedparser'] = feedparser_module
    sys.modules['tencentcloud.common.credential'] = credential_module
    sys.modules['tencentcloud.common.profile.client_profile'] = client_profile_module
    sys.modules['tencentcloud.common.profile.http_profile'] = http_profile_module
    sys.modules['tencentcloud.aiart.v20221229.aiart_client'] = aiart_client_module
    sys.modules['tencentcloud.aiart.v20221229.models'] = models_module


_install_third_party_stubs()

from agent_publisher.api.auth import _ip_records
from agent_publisher.config import settings as app_settings
from agent_publisher.main import app


@pytest.fixture(autouse=True)
def reset_login_ip_ban() -> None:
    _ip_records.clear()


@pytest.fixture
def test_settings(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(app_settings, 'access_key', 'test-access-key')
    monkeypatch.setattr(app_settings, 'jwt_secret', 'test-jwt-secret')
    monkeypatch.setattr(app_settings, 'email_whitelist', 'member@example.com,testuser@example.com')
    monkeypatch.setattr(app_settings, 'admin_emails', 'admin@openclaw.com,zhenghuizli@tencent.com')
    return app_settings


@pytest.fixture
async def async_client(test_settings):
    async with AsyncClient(transport=ASGITransport(app=app), base_url='http://testserver') as client:
        yield client
