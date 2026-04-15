from __future__ import annotations

import sys
import types
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

# ---------------------------------------------------------------------------
# Third-party stubs — these modules are not available in the test environment
# ---------------------------------------------------------------------------
credential_module = types.ModuleType("tencentcloud.common.credential")
credential_module.Credential = object
client_profile_module = types.ModuleType("tencentcloud.common.profile.client_profile")
client_profile_module.ClientProfile = object
http_profile_module = types.ModuleType("tencentcloud.common.profile.http_profile")
http_profile_module.HttpProfile = object
aiart_client_module = types.ModuleType("tencentcloud.aiart.v20221229.aiart_client")
aiart_client_module.AiartClient = object
models_module = types.ModuleType("tencentcloud.aiart.v20221229.models")
models_module.SubmitTextToImageJobRequest = object
models_module.QueryTextToImageJobRequest = object
feedparser_module = types.ModuleType("feedparser")
feedparser_module.parse = lambda *_args, **_kwargs: SimpleNamespace(entries=[], feed={})

sys.modules.setdefault("tencentcloud", types.ModuleType("tencentcloud"))
sys.modules.setdefault("tencentcloud.common", types.ModuleType("tencentcloud.common"))
sys.modules.setdefault(
    "tencentcloud.common.profile", types.ModuleType("tencentcloud.common.profile")
)
sys.modules.setdefault("tencentcloud.aiart", types.ModuleType("tencentcloud.aiart"))
sys.modules.setdefault(
    "tencentcloud.aiart.v20221229", types.ModuleType("tencentcloud.aiart.v20221229")
)
sys.modules["feedparser"] = feedparser_module
sys.modules["tencentcloud.common.credential"] = credential_module
sys.modules["tencentcloud.common.profile.client_profile"] = client_profile_module
sys.modules["tencentcloud.common.profile.http_profile"] = http_profile_module
sys.modules["tencentcloud.aiart.v20221229.aiart_client"] = aiart_client_module
sys.modules["tencentcloud.aiart.v20221229.models"] = models_module

from agent_publisher.api.media import _serialize_media_asset  # noqa: E402
from agent_publisher.schemas.article import AccountScopedPublishResult  # noqa: E402
from agent_publisher.services.article_service import ArticleService  # noqa: E402


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_service() -> ArticleService:
    return ArticleService(session=AsyncMock())


# ===========================================================================
# 1. Body image upload failure raises RuntimeError per account
# ===========================================================================


@pytest.mark.asyncio
async def test_rewrite_body_images_raises_on_upload_failure():
    """Body image upload failure should raise RuntimeError for the account."""
    service = _make_service()
    article = SimpleNamespace(id=123)
    account = SimpleNamespace(id=7)

    async def fake_get(_model, item_id):
        if item_id == 123:
            return article
        return None

    service.session.get = AsyncMock(side_effect=fake_get)
    service._get_or_create_body_media_asset = AsyncMock(
        return_value=SimpleNamespace(id=55),
    )
    service._upload_article_body_image_for_account = AsyncMock(
        side_effect=RuntimeError("upload failed"),
    )

    with pytest.raises(RuntimeError, match="Body image upload failed for account 7"):
        await service._rewrite_wechat_body_images(
            account=account,
            access_token="token",
            html_content='<p><img src="https://example.com/body.png" /></p>',
            article_id=123,
        )


# ===========================================================================
# 2. Body image rewrite skips WeChat-hosted URLs
# ===========================================================================


@pytest.mark.asyncio
async def test_rewrite_body_images_skips_wechat_urls():
    """Images already hosted on WeChat CDN should not be re-uploaded."""
    service = _make_service()
    article = SimpleNamespace(id=10)

    service.session.get = AsyncMock(return_value=article)
    service._get_or_create_body_media_asset = AsyncMock()

    html = '<p><img src="https://mmbiz.qpic.cn/foo.png" /></p>'
    result = await service._rewrite_wechat_body_images(
        account=SimpleNamespace(id=1),
        access_token="tok",
        html_content=html,
        article_id=10,
    )
    # Should be unchanged
    assert result == html
    service._get_or_create_body_media_asset.assert_not_called()


# ===========================================================================
# 3. Body image rewrite caches repeated URLs
# ===========================================================================


@pytest.mark.asyncio
async def test_rewrite_body_images_caches_repeated_urls():
    """The same image URL in multiple <img> tags should only be uploaded once."""
    service = _make_service()
    article = SimpleNamespace(id=20)

    service.session.get = AsyncMock(return_value=article)
    service._get_or_create_body_media_asset = AsyncMock(
        return_value=SimpleNamespace(id=66),
    )
    service._upload_article_body_image_for_account = AsyncMock(
        return_value="https://mmbiz.qpic.cn/uploaded.png",
    )

    html = '<img src="https://example.com/a.png" /><img src="https://example.com/a.png" />'
    result = await service._rewrite_wechat_body_images(
        account=SimpleNamespace(id=1),
        access_token="tok",
        html_content=html,
        article_id=20,
    )
    assert result.count("https://mmbiz.qpic.cn/uploaded.png") == 2
    # Upload should only happen once due to caching
    assert service._upload_article_body_image_for_account.await_count == 1


# ===========================================================================
# 4. Aggregate result status logic
# ===========================================================================


class TestAggregateResultStatus:
    """Verify _aggregate_result_status for all status combinations."""

    def _make_result(self, status: str) -> AccountScopedPublishResult:
        return AccountScopedPublishResult(
            account_id=1,
            account_name="test",
            status=status,
        )

    def test_all_success(self):
        results = [self._make_result("success"), self._make_result("success")]
        assert ArticleService._aggregate_result_status(results) == "success"

    def test_all_failed(self):
        results = [self._make_result("failed"), self._make_result("failed")]
        assert ArticleService._aggregate_result_status(results) == "failed"

    def test_all_skipped(self):
        results = [self._make_result("skipped"), self._make_result("skipped")]
        assert ArticleService._aggregate_result_status(results) == "skipped"

    def test_partial_success_and_failed(self):
        results = [self._make_result("success"), self._make_result("failed")]
        assert ArticleService._aggregate_result_status(results) == "partial"

    def test_mixed_all_three(self):
        results = [
            self._make_result("success"),
            self._make_result("failed"),
            self._make_result("skipped"),
        ]
        assert ArticleService._aggregate_result_status(results) == "partial"

    def test_empty(self):
        assert ArticleService._aggregate_result_status([]) == "skipped"


# ===========================================================================
# 5. _resolve_target_accounts defaults to agent.account_id
# ===========================================================================


@pytest.mark.asyncio
async def test_resolve_target_accounts_defaults_to_agent_account():
    """When target_account_ids is None, should fall back to agent.account_id."""
    service = _make_service()
    agent = SimpleNamespace(account_id=42)
    account = SimpleNamespace(id=42, name="Default Account")

    service.session.get = AsyncMock(return_value=account)

    accounts = await service._resolve_target_accounts(agent, None)
    assert len(accounts) == 1
    assert accounts[0].id == 42


@pytest.mark.asyncio
async def test_resolve_target_accounts_explicit_ids():
    """When explicit account IDs are provided, should resolve those accounts."""
    service = _make_service()
    agent = SimpleNamespace(account_id=1)
    account_a = SimpleNamespace(id=2, name="Account A")
    account_b = SimpleNamespace(id=3, name="Account B")

    async def fake_get(_model, item_id):
        return {2: account_a, 3: account_b}.get(item_id)

    service.session.get = AsyncMock(side_effect=fake_get)

    accounts = await service._resolve_target_accounts(agent, [2, 3])
    assert len(accounts) == 2
    assert accounts[0].id == 2
    assert accounts[1].id == 3


@pytest.mark.asyncio
async def test_resolve_target_accounts_deduplicates():
    """Duplicate account IDs should be deduplicated."""
    service = _make_service()
    agent = SimpleNamespace(account_id=1)
    account = SimpleNamespace(id=5, name="Dup Account")

    service.session.get = AsyncMock(return_value=account)

    accounts = await service._resolve_target_accounts(agent, [5, 5, 5])
    assert len(accounts) == 1


@pytest.mark.asyncio
async def test_resolve_target_accounts_nonexistent_raises():
    """Non-existent account ID should raise ValueError."""
    service = _make_service()
    agent = SimpleNamespace(account_id=1)

    service.session.get = AsyncMock(return_value=None)

    with pytest.raises(ValueError, match="Account 999 not found"):
        await service._resolve_target_accounts(agent, [999])


# ===========================================================================
# 6. _is_wechat_image_url utility
# ===========================================================================


class TestIsWechatImageUrl:
    def test_mmbiz_url(self):
        assert ArticleService._is_wechat_image_url("https://mmbiz.qpic.cn/foo.png")

    def test_non_wechat_url(self):
        assert not ArticleService._is_wechat_image_url("https://example.com/img.png")

    def test_empty(self):
        assert not ArticleService._is_wechat_image_url("")

    def test_none(self):
        assert not ArticleService._is_wechat_image_url(None)


# ===========================================================================
# 7. _extract_media_id_from_download_url
# ===========================================================================


class TestExtractMediaId:
    def test_valid_download_url(self):
        assert ArticleService._extract_media_id_from_download_url("/api/media/42/download") == 42

    def test_invalid_url(self):
        assert (
            ArticleService._extract_media_id_from_download_url("https://example.com/img.png")
            is None
        )

    def test_empty(self):
        assert ArticleService._extract_media_id_from_download_url("") is None


# ===========================================================================
# 8. _build_article_body_source_key
# ===========================================================================


class TestBuildArticleBodySourceKey:
    def test_http_url(self):
        key = ArticleService._build_article_body_source_key("https://example.com/img.png")
        assert key == "https://example.com/img.png"

    def test_data_url_hashed(self):
        key = ArticleService._build_article_body_source_key(
            "data:image/png;base64,AAAA" + "A" * 200
        )
        assert key.startswith("inline:")
        assert len(key) > 20

    def test_local_download_url(self):
        key = ArticleService._build_article_body_source_key("/api/media/5/download")
        assert key == "/api/media/5/download"


# ===========================================================================
# 9. Media asset serialization — upload status aggregation
# ===========================================================================


def test_serialize_media_asset_failed_status_priority():
    """If any mapping is 'failed', overall status should be 'failed'."""
    media_asset = SimpleNamespace(
        id=1,
        filename="body.png",
        stored_filename="stored.png",
        content_type="image/png",
        file_size=1024,
        tags=["article"],
        description="body image",
        owner_email="tester@example.com",
        source_kind="article_body",
        source_url="https://example.com/body.png",
        article_id=88,
        created_at=None,
        wechat_mappings=[
            SimpleNamespace(
                id=11,
                account_id=2,
                wechat_url="",
                upload_status="failed",
                error_message="network error",
                uploaded_at=None,
                created_at=None,
                updated_at=None,
            ),
            SimpleNamespace(
                id=12,
                account_id=1,
                wechat_url="https://mmbiz.qq.com/success.png",
                upload_status="success",
                error_message="",
                uploaded_at=None,
                created_at=None,
                updated_at=None,
            ),
        ],
    )

    payload = _serialize_media_asset(media_asset)
    assert payload["latest_upload_status"] == "failed"
    # Mappings should be sorted by account_id
    assert [m["account_id"] for m in payload["wechat_mappings"]] == [1, 2]
    assert payload["wechat_mappings"][0]["upload_status"] == "success"
    assert payload["wechat_mappings"][1]["error_message"] == "network error"


def test_serialize_media_asset_processing_over_success():
    """If any mapping is 'processing', overall should be 'processing' (not 'success')."""
    media_asset = SimpleNamespace(
        id=3,
        filename="cover.png",
        stored_filename="c.png",
        content_type="image/png",
        file_size=2048,
        tags=[],
        description="",
        owner_email="",
        source_kind="article_cover",
        source_url="",
        article_id=99,
        created_at=None,
        wechat_mappings=[
            SimpleNamespace(
                id=31,
                account_id=9,
                wechat_url="ok.png",
                upload_status="success",
                error_message="",
                uploaded_at=None,
                created_at=None,
                updated_at=None,
            ),
            SimpleNamespace(
                id=32,
                account_id=10,
                wechat_url="",
                upload_status="processing",
                error_message="",
                uploaded_at=None,
                created_at=None,
                updated_at=None,
            ),
        ],
    )
    payload = _serialize_media_asset(media_asset)
    assert payload["latest_upload_status"] == "processing"


def test_serialize_media_asset_all_pending():
    """If all mappings are 'pending', overall should be 'pending'."""
    media_asset = SimpleNamespace(
        id=4,
        filename="f.png",
        stored_filename="f.png",
        content_type="image/png",
        file_size=512,
        tags=[],
        description="",
        owner_email="",
        source_kind="manual",
        source_url="",
        article_id=None,
        created_at=None,
        wechat_mappings=[
            SimpleNamespace(
                id=41,
                account_id=1,
                wechat_url="",
                upload_status="pending",
                error_message="",
                uploaded_at=None,
                created_at=None,
                updated_at=None,
            ),
        ],
    )
    payload = _serialize_media_asset(media_asset)
    assert payload["latest_upload_status"] == "pending"


def test_serialize_media_asset_no_mappings():
    """Empty wechat_mappings should have empty latest_upload_status."""
    media_asset = SimpleNamespace(
        id=5,
        filename="orphan.png",
        stored_filename="o.png",
        content_type="image/png",
        file_size=256,
        tags=[],
        description="",
        owner_email="",
        source_kind="manual",
        source_url="",
        article_id=None,
        created_at=None,
        wechat_mappings=[],
    )
    payload = _serialize_media_asset(media_asset)
    assert payload["latest_upload_status"] == ""
    assert payload["wechat_mappings"] == []


# ===========================================================================
# 10. _build_wechat_draft_article truncates long author names
# ===========================================================================


def test_build_wechat_draft_article_truncates_author():
    service = _make_service()
    article = SimpleNamespace(title="Test", digest="d", content="c", html_content="<p>c</p>")
    agent = SimpleNamespace(name="VeryLongAgentNameThatExceedsLimit")

    draft = service._build_wechat_draft_article(
        article=article,
        agent=agent,
        html_content="<p>hello</p>",
        thumb_media_id="thumb123",
    )
    assert len(draft["author"]) <= 8
    assert draft["thumb_media_id"] == "thumb123"


def test_build_wechat_draft_article_no_thumb():
    service = _make_service()
    article = SimpleNamespace(title="T", digest="d", content="c", html_content="")
    agent = SimpleNamespace(name="Agent")

    draft = service._build_wechat_draft_article(
        article=article,
        agent=agent,
        html_content="<p>hi</p>",
        thumb_media_id="",
    )
    assert "thumb_media_id" not in draft
