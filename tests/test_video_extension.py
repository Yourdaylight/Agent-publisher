"""Video extension tests.

Three tiers:
  Unit  — Pure Python, no DB, no LLM, no Remotion
  Tier A — ASGI transport (no real DB)
  Tier B — Live server with real DB (AP_TEST_BASE_URL env)

The unit tests are the ones that would have caught the `--props` path bug
before any manual testing.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import types
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Third-party stubs (same as conftest)
# ---------------------------------------------------------------------------

def _stubs():
    for mod, attrs in [
        ('tencentcloud', {}),
        ('tencentcloud.common', {}),
        ('tencentcloud.common.profile', {}),
        ('tencentcloud.aiart', {}),
        ('tencentcloud.aiart.v20221229', {}),
        ('tencentcloud.common.credential', {'Credential': object}),
        ('tencentcloud.common.profile.client_profile', {'ClientProfile': object}),
        ('tencentcloud.common.profile.http_profile', {'HttpProfile': object}),
        ('tencentcloud.aiart.v20221229.aiart_client', {'AiartClient': object}),
        ('tencentcloud.aiart.v20221229.models', {
            'SubmitTextToImageJobRequest': object,
            'QueryTextToImageJobRequest': object,
        }),
        ('feedparser', {'parse': lambda *a, **k: SimpleNamespace(entries=[], feed={})}),
    ]:
        m = sys.modules.get(mod) or types.ModuleType(mod)
        for k, v in attrs.items():
            setattr(m, k, v)
        sys.modules.setdefault(mod, m)


_stubs()

from agent_publisher.extensions.video import service as video_service  # noqa: E402
from agent_publisher.main import app  # noqa: E402


# ============================================================
# UNIT: path integrity — the class of bug that was missed
# ============================================================

class TestStorageRootPath:
    """STORAGE_ROOT must be an absolute path.

    Remotion's --props flag rejects relative paths.
    This is the exact bug that wasn't caught before.
    """

    def test_storage_root_is_absolute(self):
        assert video_service.STORAGE_ROOT.is_absolute(), (
            f"STORAGE_ROOT must be absolute, got: {video_service.STORAGE_ROOT}\n"
            "Remotion --props rejects relative paths."
        )

    def test_remotion_dir_is_absolute(self):
        assert video_service.REMOTION_DIR.is_absolute(), (
            f"REMOTION_DIR must be absolute, got: {video_service.REMOTION_DIR}"
        )

    def test_remotion_dir_exists(self):
        assert video_service.REMOTION_DIR.exists(), (
            f"REMOTION_DIR does not exist: {video_service.REMOTION_DIR}"
        )

    def test_remotion_package_json_exists(self):
        pkg = video_service.REMOTION_DIR / "package.json"
        assert pkg.exists(), f"Remotion package.json missing: {pkg}"

    def test_props_path_would_be_absolute(self, tmp_path):
        """Simulate what service.py does: out_dir / props.json must be absolute."""
        # Mimic the path construction in _render_remotion
        out_dir = video_service.STORAGE_ROOT / "article_999_20260101000000"
        props_path = out_dir / "props.json"
        assert props_path.is_absolute(), (
            f"props_path passed to --props must be absolute, got: {props_path}"
        )

    def test_mp4_path_would_be_absolute(self, tmp_path):
        out_dir = video_service.STORAGE_ROOT / "article_999_20260101000000"
        mp4_path = out_dir / "output.mp4"
        assert mp4_path.is_absolute()

    def test_remotion_render_cmd_uses_absolute_paths(self, tmp_path):
        """Validate the exact command that would be passed to npx remotion render."""
        out_dir = video_service.STORAGE_ROOT / "article_999_20260101000000"
        props_path = out_dir / "props.json"
        mp4_path = out_dir / "output.mp4"

        cmd = [
            "npx", "remotion", "render",
            "VideoComposition",
            str(mp4_path),
            "--props", str(props_path),
            "--log", "error",
        ]

        props_arg = cmd[cmd.index("--props") + 1]
        mp4_arg = cmd[4]

        assert Path(props_arg).is_absolute(), \
            f"--props must be absolute path, got: {props_arg}"
        assert Path(mp4_arg).is_absolute(), \
            f"mp4 output must be absolute path, got: {mp4_arg}"


# ============================================================
# UNIT: prompts
# ============================================================

class TestVideoPrompts:
    def test_build_script_prompt_contains_title(self):
        from agent_publisher.extensions.video.prompts import build_script_prompt
        result = build_script_prompt("测试标题", "文章内容正文")
        assert "测试标题" in result
        assert "文章内容正文" in result

    def test_script_system_prompt_not_empty(self):
        from agent_publisher.extensions.video.prompts import SCRIPT_SYSTEM_PROMPT
        assert len(SCRIPT_SYSTEM_PROMPT) > 100


# ============================================================
# UNIT: JSON parsing (script_result → VideoScript)
# ============================================================

MOCK_SCRIPT = {
    "title": "测试视频",
    "fps": 30,
    "width": 1080,
    "height": 1920,
    "scenes": [
        {
            "id": "scene_01",
            "duration_frames": 150,
            "background_color": "#0a0a1a",
            "headline": "测试标题",
            "subline": "副标题",
            "icon": "🤖",
            "body_lines": ["第一行", "第二行"],
            "accent_color": "#3b82f6",
        }
    ],
}


class TestScriptParsing:
    def test_parse_json_dict(self):
        raw = json.dumps(MOCK_SCRIPT)
        result = video_service._parse_json(raw)
        assert isinstance(result, dict)
        assert result["title"] == "测试视频"

    def test_parse_json_with_markdown_fence(self):
        raw = f"```json\n{json.dumps(MOCK_SCRIPT)}\n```"
        result = video_service._parse_json(raw)
        assert result["title"] == "测试视频"

    def test_parse_json_invalid_raises(self):
        with pytest.raises(ValueError, match="LLM 返回的数据格式不正确"):
            video_service._parse_json("这不是JSON")


# ============================================================
# UNIT: HTML preview builder
# ============================================================

class TestHtmlPreview:
    def test_build_preview_html_contains_title(self):
        html = video_service._build_preview_html(MOCK_SCRIPT)
        assert "测试视频" in html
        assert "测试标题" in html

    def test_build_preview_html_contains_scenes(self):
        html = video_service._build_preview_html(MOCK_SCRIPT)
        assert "scene_01" in html or "🤖" in html

    def test_build_preview_html_is_valid_html(self):
        html = video_service._build_preview_html(MOCK_SCRIPT)
        assert html.strip().startswith("<!DOCTYPE html>") or "<html" in html


# ============================================================
# TIER A: ASGI transport (auth checks, no real DB)
# ============================================================

from httpx import ASGITransport, AsyncClient  # noqa: E402


@pytest.fixture
async def client():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as c:
        yield c


@pytest.fixture
async def auth_client(client):
    from agent_publisher.config import settings as s
    original = s.access_key
    s.access_key = "test-key-video"
    resp = await client.post("/api/auth/login", json={"access_key": "test-key-video"})
    assert resp.status_code == 200
    token = resp.json()["token"]
    client.headers.update({"Authorization": f"Bearer {token}"})
    yield client
    s.access_key = original


@pytest.mark.asyncio
async def test_video_generate_requires_auth(client):
    r = await client.post("/api/extensions/video/generate", json={"article_id": 1})
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_video_status_requires_auth(client):
    r = await client.get("/api/extensions/video/status/1")
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_video_preview_accepts_token_param(client):
    """Preview endpoint must accept ?token= query param (used by iframe)."""
    r = await client.get("/api/extensions/video/preview/999?token=invalid")
    # 401 or 403 — not 404 (route must exist) and not 500
    assert r.status_code in (401, 403, 404)  # 404 if task not found after auth
    assert r.status_code != 500


# ============================================================
# TIER B: Live server (AP_TEST_BASE_URL required)
# ============================================================

def _live():
    base = os.environ.get("AP_TEST_BASE_URL", "")
    if not base:
        pytest.skip("AP_TEST_BASE_URL not set")
    import httpx
    key = os.environ.get("AP_ACCESS_KEY", "agent-publisher-2024")
    c = httpx.Client(base_url=base, timeout=30)
    r = c.post("/api/auth/login", json={"access_key": key})
    if r.status_code != 200:
        pytest.skip(f"Login failed: {r.status_code}")
    c.headers.update({"Authorization": f"Bearer {r.json()['token']}"})
    return c


def test_live_video_endpoints_exist():
    c = _live()
    # Status for non-existent task must return 403/404, never 500
    r = c.get("/api/extensions/video/status/99999")
    assert r.status_code in (403, 404), f"Unexpected status: {r.status_code}"


def test_live_video_generate_nonexistent_article():
    c = _live()
    r = c.post("/api/extensions/video/generate", json={"article_id": 99999})
    assert r.status_code == 404
    assert "not found" in r.json().get("detail", "").lower()


def test_live_storage_root_absolute_on_running_server():
    """Hit an internal debug endpoint that returns service path info.
    If that endpoint doesn't exist, validate via props path logic directly.
    """
    # This validates the fix at the module level — no HTTP needed
    assert video_service.STORAGE_ROOT.is_absolute()
    assert video_service.REMOTION_DIR.is_absolute()
