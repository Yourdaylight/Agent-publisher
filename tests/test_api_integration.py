"""API integration tests for core endpoints.

Tests are split into two tiers:

Tier A (ASGI-transport, no DB): auth + settings + stateless-validation
  - Uses httpx ASGITransport through conftest.async_client fixture.
  - These work even without a running server.

Tier B (live server, real DB): endpoints that hit the database
  - Requires AP_TEST_BASE_URL env var to be set (e.g. http://localhost:9099).
  - Skipped automatically when the server is not running.
  - Run with: AP_TEST_BASE_URL=http://localhost:9099 uv run pytest tests/test_api_integration.py

Usage:
  uv run pytest tests/test_api_integration.py           # Tier A only
  AP_TEST_BASE_URL=http://localhost:9099 uv run pytest   # Tier A + B
"""
from __future__ import annotations

import os
import pytest
import httpx


# ── Helpers ──────────────────────────────────────────────────────────────────

async def _admin_token(client) -> str:
    """Get admin token using the test access key."""
    resp = await client.post('/api/auth/login', json={'access_key': 'test-access-key'})
    assert resp.status_code == 200
    return resp.json()['token']


def _live_client() -> httpx.Client:
    """Synchronous client for Tier-B live-server tests."""
    base = os.environ.get('AP_TEST_BASE_URL', '')
    if not base:
        pytest.skip('AP_TEST_BASE_URL not set — skipping live-server test')
    access_key = os.environ.get('AP_ACCESS_KEY', 'agent-publisher-2024')
    c = httpx.Client(base_url=base, timeout=15)
    resp = c.post('/api/auth/login', json={'access_key': access_key})
    if resp.status_code != 200:
        pytest.skip(f'Live server login failed ({resp.status_code}) — skipping')
    c.headers.update({'Authorization': f'Bearer {resp.json()["token"]}'})
    return c


# ════════════════════════════════════════════════════════════════════════════════
# TIER A — ASGI transport (no real DB required)
# ════════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_version(async_client):
    r = await async_client.get('/api/version')
    assert r.status_code == 200
    assert 'version' in r.json()


@pytest.mark.asyncio
async def test_stats_requires_auth(async_client):
    r = await async_client.get('/api/stats')
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_hotspots_requires_auth(async_client):
    r = await async_client.get('/api/hotspots')
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_articles_requires_auth(async_client):
    r = await async_client.get('/api/articles')
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_slideshow_requires_auth(async_client):
    r = await async_client.post('/api/extensions/slideshow/generate', json={'article_id': 1})
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_settings_get(async_client):
    token = await _admin_token(async_client)
    r = await async_client.get('/api/settings', headers={'Authorization': f'Bearer {token}'})
    assert r.status_code == 200
    body = r.json()
    assert 'wechat_proxy' in body
    assert 'trending_refresh_interval' in body


@pytest.mark.asyncio
async def test_settings_proxy_valid(async_client):
    token = await _admin_token(async_client)
    r = await async_client.put(
        '/api/settings/proxy',
        json={'wechat_proxy': 'http://1.2.3.4:8080'},
        headers={'Authorization': f'Bearer {token}'},
    )
    assert r.status_code == 200
    assert r.json()['wechat_proxy'] == 'http://1.2.3.4:8080'


@pytest.mark.asyncio
async def test_settings_proxy_invalid_format(async_client):
    token = await _admin_token(async_client)
    r = await async_client.put(
        '/api/settings/proxy',
        json={'wechat_proxy': 'not-a-url'},
        headers={'Authorization': f'Bearer {token}'},
    )
    assert r.status_code == 400


@pytest.mark.asyncio
async def test_settings_trending(async_client):
    token = await _admin_token(async_client)
    r = await async_client.put(
        '/api/settings/trending',
        json={'interval_minutes': 30},
        headers={'Authorization': f'Bearer {token}'},
    )
    assert r.status_code == 200
    assert r.json()['interval_minutes'] == 30


@pytest.mark.asyncio
async def test_invite_codes_no_token_401(async_client):
    r = await async_client.get('/api/invite-codes')
    assert r.status_code == 401


# ════════════════════════════════════════════════════════════════════════════════
# TIER B — Live server (real DB, real process)
# Run:  AP_TEST_BASE_URL=http://localhost:9099 uv run pytest tests/test_api_integration.py -k tier_b
# ════════════════════════════════════════════════════════════════════════════════

def test_tier_b_stats():
    c = _live_client()
    r = c.get('/api/stats')
    assert r.status_code == 200
    for key in ('accounts', 'agents', 'articles', 'tasks'):
        assert key in r.json()


def test_tier_b_hotspots():
    c = _live_client()
    r = c.get('/api/hotspots?limit=3')
    assert r.status_code == 200
    body = r.json()
    assert 'items' in body and 'total' in body


def test_tier_b_articles():
    c = _live_client()
    r = c.get('/api/articles')
    assert r.status_code == 200
    assert isinstance(r.json(), list)


def test_tier_b_credits():
    c = _live_client()
    r = c.get('/api/credits/balance')
    assert r.status_code == 200
    assert 'available' in r.json()


def test_tier_b_style_presets():
    c = _live_client()
    r = c.get('/api/style-presets')
    assert r.status_code == 200
    presets = r.json()
    builtin = [p for p in presets if p.get('is_builtin')]
    assert len(builtin) > 0, 'No built-in style presets'


def test_tier_b_extensions():
    c = _live_client()
    r = c.get('/api/extensions')
    assert r.status_code == 200
    assert 'extensions' in r.json()


def test_tier_b_prompts():
    c = _live_client()
    r = c.get('/api/prompts')
    assert r.status_code == 200


def test_tier_b_invite_codes_crud():
    c = _live_client()
    # Create
    r = c.post('/api/invite-codes', json={'channel': 'ci-test', 'max_uses': 1, 'bonus_credits': 0})
    assert r.status_code == 200
    codes = r.json().get('codes', [])
    assert len(codes) == 1
    code_id = codes[0]['id']
    # Delete
    r = c.delete(f'/api/invite-codes/{code_id}')
    assert r.status_code == 200


def test_tier_b_articles_cover_missing():
    c = _live_client()
    r = c.post('/api/articles/99999/generate-cover')
    assert r.status_code == 404
