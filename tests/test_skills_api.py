from __future__ import annotations

import pytest


@pytest.mark.asyncio
async def test_skills_auth_admin_email_success(async_client):
    response = await async_client.post(
        "/api/skills/auth", json={"email": "zhenghuizli@tencent.com"}
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["email"] == "zhenghuizli@tencent.com"
    assert payload["is_admin"] is True
    assert "token" in payload


@pytest.mark.asyncio
async def test_skills_auth_whitelist_email_success(async_client):
    response = await async_client.post("/api/skills/auth", json={"email": "member@example.com"})
    assert response.status_code == 200
    payload = response.json()
    assert payload["email"] == "member@example.com"
    assert payload["is_admin"] is False
    assert "token" in payload


@pytest.mark.asyncio
async def test_skills_auth_unknown_email_rejected(async_client):
    response = await async_client.post("/api/skills/auth", json={"email": "outsider@example.com"})
    assert response.status_code == 403
    assert response.json()["detail"] == "该邮箱不在白名单中，请联系管理员"
