from __future__ import annotations

import pytest


@pytest.mark.asyncio
async def test_public_version_endpoint(async_client):
    response = await async_client.get("/api/version")
    assert response.status_code == 200
    assert "version" in response.json()


@pytest.mark.asyncio
async def test_admin_email_login_success(async_client):
    response = await async_client.post("/api/auth/login", json={"email": "zhenghuizli@tencent.com"})
    assert response.status_code == 200
    payload = response.json()
    assert payload["email"] == "zhenghuizli@tencent.com"
    assert payload["is_admin"] is True
    assert "token" in payload


@pytest.mark.asyncio
async def test_whitelist_email_login_success(async_client):
    response = await async_client.post("/api/auth/login", json={"email": "member@example.com"})
    assert response.status_code == 200
    payload = response.json()
    assert payload["email"] == "member@example.com"
    assert payload["is_admin"] is False
    assert "token" in payload


@pytest.mark.asyncio
async def test_unknown_email_login_rejected(async_client):
    response = await async_client.post("/api/auth/login", json={"email": "outsider@example.com"})
    assert response.status_code == 401
    assert response.json()["detail"] == "该邮箱不在白名单中，请联系管理员"


@pytest.mark.asyncio
async def test_access_key_login_success(async_client):
    response = await async_client.post("/api/auth/login", json={"access_key": "test-access-key"})
    assert response.status_code == 200
    payload = response.json()
    assert payload["email"] == "__admin__"
    assert payload["is_admin"] is True
    assert "token" in payload


@pytest.mark.asyncio
async def test_verify_and_me_for_email_token(async_client):
    login_response = await async_client.post(
        "/api/auth/login", json={"email": "zhenghuizli@tencent.com"}
    )
    token = login_response.json()["token"]
    headers = {"Authorization": f"Bearer {token}"}

    verify_response = await async_client.get("/api/auth/verify", headers=headers)
    assert verify_response.status_code == 200
    assert verify_response.json()["email"] == "zhenghuizli@tencent.com"
    assert verify_response.json()["is_admin"] is True

    me_response = await async_client.get("/api/auth/me", headers=headers)
    assert me_response.status_code == 200
    assert me_response.json() == {"email": "zhenghuizli@tencent.com", "is_admin": True}


@pytest.mark.asyncio
async def test_verify_invalid_token_rejected(async_client):
    response = await async_client.get(
        "/api/auth/verify", headers={"Authorization": "Bearer invalid-token"}
    )
    assert response.status_code == 401
