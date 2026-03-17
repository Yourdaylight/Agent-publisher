"""Regression tests for backward compatibility of multi-account publish.

Verifies that:
- Legacy migration script correctly creates relations from old data
- Default behavior (no target_account_ids) still works
- Old response fields remain available
- Schema models validate correctly
"""
from __future__ import annotations

import sys
import types
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

# ---------------------------------------------------------------------------
# Third-party stubs
# ---------------------------------------------------------------------------
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

from agent_publisher.schemas.article import (
    AccountScopedPublishResult,
    ArticlePublishRelationOut,
    ArticlePublishRequest,
    ArticlePublishResponse,
    ArticleSyncRequest,
    ArticleSyncResponse,
)


# ===========================================================================
# 1. Schema backward compatibility tests
# ===========================================================================

class TestArticlePublishRequestCompat:
    """Verify publish request accepts both old and new shapes."""

    def test_empty_body_is_valid(self):
        req = ArticlePublishRequest()
        assert req.target_account_ids is None

    def test_explicit_none(self):
        req = ArticlePublishRequest(target_account_ids=None)
        assert req.target_account_ids is None

    def test_explicit_ids(self):
        req = ArticlePublishRequest(target_account_ids=[1, 2, 3])
        assert req.target_account_ids == [1, 2, 3]


class TestArticleSyncRequestCompat:
    """Verify sync request accepts both old and new shapes."""

    def test_empty_body_is_valid(self):
        req = ArticleSyncRequest()
        assert req.target_account_ids is None

    def test_explicit_ids(self):
        req = ArticleSyncRequest(target_account_ids=[4, 5])
        assert req.target_account_ids == [4, 5]


class TestArticlePublishResponseCompat:
    """Verify response shape includes both old media_id and new per-account results."""

    def test_old_media_id_field_present(self):
        resp = ArticlePublishResponse(
            ok=True,
            article_id=1,
            overall_status='success',
            media_id='MEDIA_123',
            target_account_ids=[1],
            results=[
                AccountScopedPublishResult(
                    account_id=1,
                    account_name='Test',
                    status='success',
                    wechat_media_id='MEDIA_123',
                ),
            ],
        )
        assert resp.media_id == 'MEDIA_123'
        assert resp.ok is True
        assert len(resp.results) == 1

    def test_failed_response(self):
        resp = ArticlePublishResponse(
            ok=False,
            article_id=2,
            overall_status='failed',
            media_id='',
            target_account_ids=[1, 2],
            results=[
                AccountScopedPublishResult(
                    account_id=1, account_name='A', status='failed', error='network err',
                ),
                AccountScopedPublishResult(
                    account_id=2, account_name='B', status='failed', error='auth err',
                ),
            ],
        )
        assert resp.ok is False
        assert resp.overall_status == 'failed'


class TestArticleSyncResponseCompat:
    """Verify sync response shape."""

    def test_skipped_response(self):
        resp = ArticleSyncResponse(
            ok=False,
            article_id=3,
            overall_status='skipped',
            sync_status='skipped',
            target_account_ids=[5],
            results=[
                AccountScopedPublishResult(
                    account_id=5, account_name='C', status='skipped',
                    error='Draft media_id not found for this account',
                ),
            ],
        )
        assert resp.sync_status == 'skipped'
        assert resp.results[0].status == 'skipped'


class TestArticlePublishRelationOutCompat:
    """Verify relation output schema from_attributes works."""

    def test_from_dict(self):
        from datetime import datetime, timezone

        now = datetime.now(timezone.utc)
        out = ArticlePublishRelationOut(
            id=1,
            article_id=10,
            account_id=2,
            account_name='Test Account',
            wechat_media_id='M123',
            publish_status='success',
            sync_status='synced',
            last_error='',
            last_published_at=now,
            last_synced_at=now,
            created_at=now,
            updated_at=now,
        )
        assert out.account_name == 'Test Account'
        assert out.publish_status == 'success'


# ===========================================================================
# 2. Legacy migration script logic test
# ===========================================================================

@pytest.mark.asyncio
async def test_migrate_creates_relations_for_legacy_articles():
    """Verify migration creates ArticlePublishRelation for articles with wechat_media_id."""
    from unittest.mock import patch

    # Mock the database imports inside the migrate function
    fake_article = SimpleNamespace(
        id=100,
        agent_id=10,
        wechat_media_id='LEGACY_MEDIA_1',
        published_at=None,
    )
    fake_agent = SimpleNamespace(id=10, account_id=5)

    session = AsyncMock()

    # First execute: find articles with wechat_media_id
    article_result = MagicMock()
    article_result.scalars.return_value.all.return_value = [fake_article]

    # Second execute: check existing relations (none found)
    rel_result = MagicMock()
    rel_result.scalars.return_value.first.return_value = None

    session.execute = AsyncMock(side_effect=[article_result, rel_result])
    session.get = AsyncMock(return_value=fake_agent)
    session.add = MagicMock()
    session.commit = AsyncMock()

    from scripts.migrate_legacy_publish_relations import migrate

    summary = await migrate(session, dry_run=False)

    assert summary['total_articles'] == 1
    assert summary['created'] == 1
    assert summary['skipped'] == 0
    assert summary['errors'] == 0
    session.add.assert_called_once()
    session.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_migrate_skips_articles_with_existing_relations():
    """Verify migration skips articles that already have a relation."""
    fake_article = SimpleNamespace(
        id=200,
        agent_id=20,
        wechat_media_id='LEGACY_MEDIA_2',
        published_at=None,
    )
    existing_relation = SimpleNamespace(
        id=999,
        article_id=200,
        account_id=5,
    )

    session = AsyncMock()

    article_result = MagicMock()
    article_result.scalars.return_value.all.return_value = [fake_article]

    rel_result = MagicMock()
    rel_result.scalars.return_value.first.return_value = existing_relation

    session.execute = AsyncMock(side_effect=[article_result, rel_result])
    session.commit = AsyncMock()

    from scripts.migrate_legacy_publish_relations import migrate

    summary = await migrate(session, dry_run=False)

    assert summary['total_articles'] == 1
    assert summary['created'] == 0
    assert summary['skipped'] == 1
    session.add.assert_not_called()


@pytest.mark.asyncio
async def test_migrate_dry_run_does_not_commit():
    """Verify dry_run mode does not commit changes."""
    fake_article = SimpleNamespace(
        id=300,
        agent_id=30,
        wechat_media_id='LEGACY_MEDIA_3',
        published_at=None,
    )
    fake_agent = SimpleNamespace(id=30, account_id=8)

    session = AsyncMock()

    article_result = MagicMock()
    article_result.scalars.return_value.all.return_value = [fake_article]

    rel_result = MagicMock()
    rel_result.scalars.return_value.first.return_value = None

    session.execute = AsyncMock(side_effect=[article_result, rel_result])
    session.get = AsyncMock(return_value=fake_agent)
    session.add = MagicMock()
    session.commit = AsyncMock()

    from scripts.migrate_legacy_publish_relations import migrate

    summary = await migrate(session, dry_run=True)

    assert summary['created'] == 1
    session.add.assert_not_called()  # Dry run should not add
    session.commit.assert_not_awaited()  # Dry run should not commit


@pytest.mark.asyncio
async def test_migrate_handles_missing_agent():
    """Verify migration handles articles whose agent no longer exists."""
    fake_article = SimpleNamespace(
        id=400,
        agent_id=40,
        wechat_media_id='LEGACY_MEDIA_4',
        published_at=None,
    )

    session = AsyncMock()

    article_result = MagicMock()
    article_result.scalars.return_value.all.return_value = [fake_article]

    rel_result = MagicMock()
    rel_result.scalars.return_value.first.return_value = None

    session.execute = AsyncMock(side_effect=[article_result, rel_result])
    session.get = AsyncMock(return_value=None)  # Agent not found
    session.commit = AsyncMock()

    from scripts.migrate_legacy_publish_relations import migrate

    summary = await migrate(session, dry_run=False)

    assert summary['errors'] == 1
    assert summary['created'] == 0


# ===========================================================================
# 3. Default target account fallback regression
# ===========================================================================

@pytest.mark.asyncio
async def test_resolve_defaults_when_no_target_ids():
    """When target_account_ids is None, should use agent.account_id."""
    from agent_publisher.services.article_service import ArticleService

    service = ArticleService(session=AsyncMock())
    agent = SimpleNamespace(account_id=7)
    account = SimpleNamespace(id=7, name='Default')

    service.session.get = AsyncMock(return_value=account)

    accounts = await service._resolve_target_accounts(agent, None)
    assert len(accounts) == 1
    assert accounts[0].id == 7


@pytest.mark.asyncio
async def test_resolve_defaults_when_empty_list():
    """When target_account_ids is empty list, should also use agent.account_id."""
    from agent_publisher.services.article_service import ArticleService

    service = ArticleService(session=AsyncMock())
    agent = SimpleNamespace(account_id=3)
    account = SimpleNamespace(id=3, name='Fallback')

    service.session.get = AsyncMock(return_value=account)

    accounts = await service._resolve_target_accounts(agent, [])
    assert len(accounts) == 1
    assert accounts[0].id == 3
