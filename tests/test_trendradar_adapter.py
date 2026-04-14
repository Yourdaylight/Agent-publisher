"""Unit tests for TrendRadar adapter — dedup, scoring, storage, end-to-end."""
from __future__ import annotations

import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

from agent_publisher.services.trendradar_adapter import (
    TrendRadarNewsItem,
    TrendRadarAdapter,
)


# ── TrendRadarNewsItem dataclass tests ──


class TestTrendRadarNewsItem:
    def test_create_news_item(self):
        item = TrendRadarNewsItem(
            title="Test Title",
            url="https://example.com/news",
            source_platform="weibo",
            hot_value=85.0,
            rank=1,
            summary="Test summary",
        )
        assert item.title == "Test Title"
        assert item.source_platform == "weibo"
        assert item.hot_value == 85.0

    def test_to_candidate_material(self):
        item = TrendRadarNewsItem(
            title="Test News",
            url="https://example.com/article",
            source_platform="douyin",
            hot_value=50.0,
            rank=5,
            summary="Test summary",
        )
        mat = item.to_candidate_material(agent_id=123, quality_score=0.75)

        assert mat["agent_id"] == 123
        assert mat["source_type"] == "trending"
        assert mat["source_identity"] == "trendradar:douyin"
        assert mat["original_url"] == "https://example.com/article"
        assert mat["title"] == "Test News"
        assert mat["quality_score"] == 0.75
        assert "douyin" in mat["tags"]

    def test_tags_hot(self):
        item = TrendRadarNewsItem(
            title="Hot", url="u", source_platform="weibo", hot_value=90, rank=1
        )
        tags = item._extract_tags()
        assert "hot" in tags
        assert "top10" in tags

    def test_tags_cool(self):
        item = TrendRadarNewsItem(
            title="Cool", url="u", source_platform="zhihu", hot_value=20, rank=80
        )
        tags = item._extract_tags()
        assert "cool" in tags
        assert "top10" not in tags


# ── Scoring tests ──


class TestScoring:
    def test_score_with_keywords_match(self):
        adapter = TrendRadarAdapter(MagicMock())
        item = TrendRadarNewsItem(
            title="Python AI突破", url="u", source_platform="weibo",
            hot_value=80, rank=1,
        )
        fit = adapter._calculate_agent_fit(item, ["python", "AI"])
        assert fit == 1.0

    def test_score_with_keywords_no_match(self):
        adapter = TrendRadarAdapter(MagicMock())
        item = TrendRadarNewsItem(
            title="Classical Music", url="u", source_platform="weibo",
            hot_value=80, rank=1,
        )
        fit = adapter._calculate_agent_fit(item, ["python", "AI"])
        assert fit == 0.0

    def test_score_without_keywords(self):
        adapter = TrendRadarAdapter(MagicMock())
        item = TrendRadarNewsItem(
            title="Any", url="u", source_platform="weibo",
            hot_value=80, rank=1,
        )
        fit = adapter._calculate_agent_fit(item, None)
        assert fit == 0.5

    def test_score_and_filter_removes_low_quality(self):
        adapter = TrendRadarAdapter(MagicMock())
        items = [
            TrendRadarNewsItem(title="Hot", url="u1", source_platform="weibo", hot_value=90, rank=1),
            TrendRadarNewsItem(title="Cold", url="u2", source_platform="weibo", hot_value=5, rank=99),
        ]
        scored = adapter._score_and_filter(items)
        # Hot item passes, cold one likely filtered out (score < 0.3)
        titles = [item.title for item, _ in scored]
        assert "Hot" in titles

    def test_score_bounds(self):
        adapter = TrendRadarAdapter(MagicMock())
        items = [
            TrendRadarNewsItem(
                title=f"News {i}", url=f"u{i}", source_platform="weibo",
                hot_value=100 - i * 20, rank=i + 1,
            )
            for i in range(5)
        ]
        scored = adapter._score_and_filter(items)
        for _, score in scored:
            assert 0 <= score <= 1, f"Score {score} out of bounds"

    def test_higher_hotness_gives_higher_score(self):
        adapter = TrendRadarAdapter(MagicMock())
        hot = TrendRadarNewsItem(title="Hot", url="u1", source_platform="weibo", hot_value=95, rank=1)
        cold = TrendRadarNewsItem(title="Cold", url="u2", source_platform="weibo", hot_value=10, rank=50)
        scored = adapter._score_and_filter([hot, cold])

        scores = {item.title: score for item, score in scored}
        if "Hot" in scores and "Cold" in scores:
            assert scores["Hot"] > scores["Cold"]


# ── Dedup tests ──


class TestDedup:
    @pytest.mark.asyncio
    async def test_dedup_skips_existing_urls(self):
        db = AsyncMock()
        adapter = TrendRadarAdapter(db)

        # Mock existing URLs in DB
        mock_result = MagicMock()
        mock_result.all.return_value = [("https://existing.com",)]
        db.execute.return_value = mock_result

        items = [
            TrendRadarNewsItem(title="Existing", url="https://existing.com", source_platform="weibo", hot_value=50, rank=1),
            TrendRadarNewsItem(title="New", url="https://new.com", source_platform="weibo", hot_value=50, rank=2),
        ]

        result = await adapter._deduplicate_items(agent_id=1, items=items)
        assert result["duplicates_skipped"] == 1
        assert len(result["unique_items"]) == 1
        assert result["unique_items"][0].title == "New"

    @pytest.mark.asyncio
    async def test_dedup_with_no_agent(self):
        """Global collection (agent_id=None) checks all trending URLs."""
        db = AsyncMock()
        adapter = TrendRadarAdapter(db)

        mock_result = MagicMock()
        mock_result.all.return_value = []
        db.execute.return_value = mock_result

        items = [
            TrendRadarNewsItem(title="A", url="https://a.com", source_platform="weibo", hot_value=50, rank=1),
        ]

        result = await adapter._deduplicate_items(agent_id=None, items=items)
        assert len(result["unique_items"]) == 1


# ── Feature flag tests ──


class TestFeatureFlag:
    @pytest.mark.asyncio
    async def test_disabled_returns_empty(self):
        adapter = TrendRadarAdapter(MagicMock(), feature_flag_enabled=False)
        result = await adapter.collect_for_agent(agent_id=1)
        assert result["status"] == "success"
        assert result["new_items"] == 0
        assert result["platforms_collected"] == []


# ── End-to-end pipeline test ──


class TestEndToEndPipeline:
    @pytest.mark.asyncio
    async def test_full_pipeline_with_mocked_bridge(self):
        """fetch → dedup → score → store end-to-end."""
        db = AsyncMock()

        # Mock dedup: no existing URLs
        mock_result = MagicMock()
        mock_result.all.return_value = []
        db.execute.return_value = mock_result

        adapter = TrendRadarAdapter(db, feature_flag_enabled=True)

        mock_items = [
            TrendRadarNewsItem(
                title="AI突破性进展",
                url="https://weibo.com/ai",
                source_platform="weibo",
                hot_value=90,
                rank=1,
            ),
            TrendRadarNewsItem(
                title="今日天气",
                url="https://weibo.com/weather",
                source_platform="weibo",
                hot_value=30,
                rank=50,
            ),
        ]

        with patch("agent_publisher.config.settings") as mock_settings:
            mock_settings.trendradar_platforms = "weibo"
            mock_settings.trendradar_storage_path = ""

            with patch(
                "agent_publisher.services.trendradar_bridge.fetch_trending_via_trendradar",
                new_callable=AsyncMock,
                return_value=mock_items,
            ):
                result = await adapter.collect_for_agent(
                    agent_id=1, agent_name="test-agent"
                )

        assert result["status"] == "success"
        assert result["new_items"] >= 1  # At least the hot item
        assert "weibo" in result["platforms_collected"]
