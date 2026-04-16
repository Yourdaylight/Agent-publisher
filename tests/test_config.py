from __future__ import annotations

from agent_publisher.config import settings as app_settings


def test_admin_email_is_recognized(test_settings):
    assert app_settings.is_admin("zhenghuizli@tencent.com") is True
    assert app_settings.is_email_allowed("zhenghuizli@tencent.com") is True


def test_whitelist_email_is_allowed(test_settings):
    assert app_settings.is_admin("member@example.com") is False
    assert app_settings.is_email_allowed("member@example.com") is True


def test_unknown_email_is_rejected(test_settings):
    assert app_settings.is_admin("outsider@example.com") is False
    assert app_settings.is_email_allowed("outsider@example.com") is False
