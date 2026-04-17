"""Tests for the preferences API endpoints."""
from __future__ import annotations

import pytest


async def _get_admin_token(client) -> str:
    """Get admin token using the test access key."""
    resp = await client.post("/api/auth/login", json={"access_key": "test-access-key"})
    assert resp.status_code == 200
    return resp.json()["token"]


@pytest.mark.asyncio
async def test_get_preferences_requires_auth(async_client):
    """GET /user/preferences should require authentication."""
    response = await async_client.get("/api/user/preferences")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_save_preferences_requires_auth(async_client):
    """PUT /user/preferences should require authentication."""
    response = await async_client.put(
        "/api/user/preferences",
        json={
            "interest_keywords": ["AI"],
            "preferred_platforms": [],
            "blocked_keywords": [],
        },
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_save_preferences_creates_new(async_client):
    """PUT /user/preferences should create new preference record."""
    token = await _get_admin_token(async_client)
    response = await async_client.put(
        "/api/user/preferences",
        json={
            "interest_keywords": ["AI", "区块链"],
            "preferred_platforms": ["weibo", "douyin"],
            "blocked_keywords": ["广告"],
        },
        headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["interest_keywords"] == ["AI", "区块链"]
    assert data["preferred_platforms"] == ["weibo", "douyin"]
    assert data["blocked_keywords"] == ["广告"]


@pytest.mark.asyncio
async def test_save_preferences_updates_existing(async_client):
    """PUT /user/preferences should update existing preference record."""
    token = await _get_admin_token(async_client)
    
    # First save
    response1 = await async_client.put(
        "/api/user/preferences",
        json={
            "interest_keywords": ["AI"],
            "preferred_platforms": ["weibo"],
            "blocked_keywords": [],
        },
        headers={"Authorization": f"Bearer {token}"}
    )
    assert response1.status_code == 200

    # Update with different values
    response2 = await async_client.put(
        "/api/user/preferences",
        json={
            "interest_keywords": ["AI", "金融"],
            "preferred_platforms": ["douyin", "zhihu"],
            "blocked_keywords": ["垃圾"],
        },
        headers={"Authorization": f"Bearer {token}"}
    )
    assert response2.status_code == 200
    data = response2.json()
    assert data["interest_keywords"] == ["AI", "金融"]
    assert data["preferred_platforms"] == ["douyin", "zhihu"]
    assert data["blocked_keywords"] == ["垃圾"]


@pytest.mark.asyncio
async def test_get_preferences_returns_saved_values(async_client):
    """GET /user/preferences should return previously saved values."""
    token = await _get_admin_token(async_client)
    
    # Save preferences
    await async_client.put(
        "/api/user/preferences",
        json={
            "interest_keywords": ["机器学习"],
            "preferred_platforms": ["小红书"],
            "blocked_keywords": ["营销"],
        },
        headers={"Authorization": f"Bearer {token}"}
    )

    # Retrieve them
    response = await async_client.get(
        "/api/user/preferences",
        headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["interest_keywords"] == ["机器学习"]
    assert data["preferred_platforms"] == ["小红书"]
    assert data["blocked_keywords"] == ["营销"]


@pytest.mark.asyncio
async def test_save_preferences_empty_lists(async_client):
    """PUT /user/preferences should accept empty lists to clear preferences."""
    token = await _get_admin_token(async_client)
    
    # Save some preferences first
    await async_client.put(
        "/api/user/preferences",
        json={
            "interest_keywords": ["AI"],
            "preferred_platforms": ["weibo"],
            "blocked_keywords": ["ad"],
        },
        headers={"Authorization": f"Bearer {token}"}
    )

    # Clear them
    response = await async_client.put(
        "/api/user/preferences",
        json={
            "interest_keywords": [],
            "preferred_platforms": [],
            "blocked_keywords": [],
        },
        headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["interest_keywords"] == []
    assert data["preferred_platforms"] == []
    assert data["blocked_keywords"] == []


@pytest.mark.asyncio
async def test_save_preferences_partial_update(async_client):
    """PUT /user/preferences should allow partial updates."""
    token = await _get_admin_token(async_client)
    
    # Save initial preferences
    await async_client.put(
        "/api/user/preferences",
        json={
            "interest_keywords": ["AI"],
            "preferred_platforms": ["weibo"],
            "blocked_keywords": ["ad"],
        },
        headers={"Authorization": f"Bearer {token}"}
    )

    # Update only interest_keywords
    response = await async_client.put(
        "/api/user/preferences",
        json={
            "interest_keywords": ["机器学习"],
            "preferred_platforms": ["weibo"],  # Keep same
            "blocked_keywords": ["ad"],  # Keep same
        },
        headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["interest_keywords"] == ["机器学习"]
    assert data["preferred_platforms"] == ["weibo"]
    assert data["blocked_keywords"] == ["ad"]


@pytest.mark.asyncio
async def test_save_preferences_with_duplicates(async_client):
    """PUT /user/preferences should accept lists with duplicates (no dedup server-side)."""
    token = await _get_admin_token(async_client)
    
    response = await async_client.put(
        "/api/user/preferences",
        json={
            "interest_keywords": ["AI", "AI"],  # Duplicates
            "preferred_platforms": ["weibo", "weibo"],
            "blocked_keywords": [],
        },
        headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 200
    data = response.json()
    # Server stores as-is (no dedup)
    assert "AI" in data["interest_keywords"]


@pytest.mark.asyncio
async def test_save_preferences_with_special_characters(async_client):
    """PUT /user/preferences should handle special characters."""
    token = await _get_admin_token(async_client)
    
    response = await async_client.put(
        "/api/user/preferences",
        json={
            "interest_keywords": ["AI 人工智能", "区块链#NFT", "元宇宙🌐"],
            "preferred_platforms": ["微博", "抖音"],
            "blocked_keywords": ["广告&营销"],
        },
        headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 200
    data = response.json()
    assert "AI 人工智能" in data["interest_keywords"]
    assert "元宇宙🌐" in data["interest_keywords"]


@pytest.mark.asyncio
async def test_save_preferences_with_long_strings(async_client):
    """PUT /user/preferences should handle long keyword strings."""
    token = await _get_admin_token(async_client)
    
    long_keyword = "a" * 1000  # Very long keyword
    response = await async_client.put(
        "/api/user/preferences",
        json={
            "interest_keywords": [long_keyword],
            "preferred_platforms": [],
            "blocked_keywords": [],
        },
        headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 200
    data = response.json()
    assert long_keyword in data["interest_keywords"]
