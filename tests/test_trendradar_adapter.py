"""Unit tests for TrendRadar adapter and integration layer."""
from __future__ import annotations

import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

from agent_publisher.services.trendradar_adapter import (
    TrendRadarNewsItem,
    TrendRadarAdapter,
)
from agent_publisher.services.trendradar_integration import (
    TrendRadarIntegration,
    get_trendradar_integration,
)


class TestTrendRadarNewsItem:
    """Tests for TrendRadarNewsItem dataclass."""

    def test_create_news_item(self):
        """Can create a TrendRadarNewsItem."""
        item = TrendRadarNewsItem(
            title="Test Title",
            url="https://example.com/news",
            source_platform="weibo",
            hot_value=1000,
            rank=1,
            summary="Test summary",
            image_url="https://example.com/image.jpg",
            author="Test Author",
            timestamp=datetime.now(timezone.utc),
            source_url="https://weibo.com/original",
            metadata={"key": "value"},
        )
        assert item.title == "Test Title"
        assert item.source_platform == "weibo"
        assert item.hot_value == 1000

    def test_to_candidate_material(self):
        """Converts TrendRadarNewsItem to CandidateMaterial format."""
        item = TrendRadarNewsItem(
            title="Test News",
            url="https://example.com/article",
            source_platform="douyin",
            hot_value=500,
            rank=5,
            summary="Test summary",
            image_url="https://example.com/img.jpg",
            author="Author Name",
            timestamp=datetime.now(timezone.utc),
            source_url="https://douyin.com/feed",
            metadata={"category": "technology"},
        )

        agent_id = 123
        quality_score = 0.75
        material_dict = item.to_candidate_material(agent_id, quality_score)

        assert material_dict["agent_id"] == 123
        assert material_dict["source_type"] == "trending"
        assert "trendradar:douyin" in material_dict["source_identity"]
        assert material_dict["original_url"] == "https://example.com/article"
        assert material_dict["title"] == "Test News"
        assert material_dict["summary"] == "Test summary"
        assert material_dict["quality_score"] == 0.75
        assert "douyin" in material_dict["tags"]


class TestTrendRadarAdapter:
    """Tests for TrendRadarAdapter scoring and filtering logic."""

    @pytest.mark.asyncio
    async def test_score_and_filter_empty_list(self):
        """Scoring empty list returns empty list."""
        db_session = MagicMock()
        adapter = TrendRadarAdapter(db_session)

        agent = MagicMock()
        agent.id = 1
        agent.name = "Test Agent"

        result = await adapter._score_and_filter(agent_id=1, items=[])
        assert result == []

    @pytest.mark.asyncio
    async def test_calculate_agent_fit_perfect_match(self):
        """Perfect keyword match gives high fit score."""
        db_session = MagicMock()
        adapter = TrendRadarAdapter(db_session)

        agent = MagicMock()
        agent.keywords = ["python", "programming"]

        item = TrendRadarNewsItem(
            title="Python Programming Tutorial",
            url="https://example.com/python",
            source_platform="weibo",
            hot_value=100,
            rank=1,
            summary="Learn Python",
            image_url="",
            author="",
            timestamp=datetime.now(timezone.utc),
            source_url="",
            metadata={},
        )

        fit_score = await adapter._calculate_agent_fit(agent, item)
        # Should be > 0.5 because keywords match
        assert fit_score > 0.5

    @pytest.mark.asyncio
    async def test_calculate_agent_fit_no_match(self):
        """No keyword match gives low fit score."""
        db_session = MagicMock()
        adapter = TrendRadarAdapter(db_session)

        agent = MagicMock()
        agent.keywords = ["blockchain", "crypto"]

        item = TrendRadarNewsItem(
            title="Classical Music Concert Tonight",
            url="https://example.com/music",
            source_platform="weibo",
            hot_value=100,
            rank=1,
            summary="Beautiful orchestra",
            image_url="",
            author="",
            timestamp=datetime.now(timezone.utc),
            source_url="",
            metadata={},
        )

        fit_score = await adapter._calculate_agent_fit(agent, item)
        # Should be <= 0.5 because no keywords match
        assert fit_score <= 0.5

    @pytest.mark.asyncio
    async def test_score_bounds(self):
        """Quality scores stay within valid bounds [0, 1]."""
        db_session = MagicMock()
        adapter = TrendRadarAdapter(db_session)

        items = [
            TrendRadarNewsItem(
                title=f"News {i}",
                url=f"https://example.com/news{i}",
                source_platform="weibo",
                hot_value=1000 - i * 100,
                rank=i + 1,
                summary=f"Summary {i}",
                image_url="",
                author="",
                timestamp=datetime.now(timezone.utc),
                source_url="",
                metadata={},
            )
            for i in range(5)
        ]

        agent = MagicMock()
        agent.id = 1
        agent.keywords = []

        scored = await adapter._score_and_filter(agent_id=1, items=items)

        for item, score in scored:
            assert 0 <= score <= 1, f"Score {score} out of bounds"


class TestTrendRadarIntegration:
    """Tests for TrendRadarIntegration orchestration layer."""

    @pytest.mark.asyncio
    async def test_initialize_available(self):
        """Initialize successfully when TrendRadar available."""
        db_session = MagicMock()
        integration = TrendRadarIntegration(db_session, available=True)

        # Should not raise
        await integration.initialize()

    @pytest.mark.asyncio
    async def test_initialize_unavailable(self):
        """Initialize handles unavailable TrendRadar gracefully."""
        db_session = MagicMock()
        integration = TrendRadarIntegration(db_session, available=False)

        # Should not raise, just logs warning
        await integration.initialize()

    @pytest.mark.asyncio
    async def test_feature_flag_disabled_uses_fallback(self):
        """When feature flag disabled, uses fallback."""
        db_session = AsyncMock()
        integration = TrendRadarIntegration(db_session, available=True)

        agent = MagicMock()
        agent.id = 1
        agent.name = "Test Agent"

        bindings = []

        # Mock the fallback path
        with patch.object(integration, '_collect_with_trending_service', new_callable=AsyncMock) as mock_fallback:
            mock_fallback.return_value = [1, 2, 3]

            # With feature flag disabled (default)
            result = await integration.collect_trending_with_fallback(agent, bindings)

            # Should call fallback
            mock_fallback.assert_called_once()

    @pytest.mark.asyncio
    async def test_error_handling_fallback(self):
        """On TrendRadar error, automatically falls back."""
        db_session = AsyncMock()
        integration = TrendRadarIntegration(db_session, available=True)

        agent = MagicMock()
        agent.id = 1
        agent.name = "Test Agent"

        bindings = []

        # Mock TrendRadar path to fail
        with patch.object(integration, '_collect_with_trendradar', new_callable=AsyncMock) as mock_tr:
            with patch.object(integration, '_collect_with_trending_service', new_callable=AsyncMock) as mock_fallback:
                mock_tr.side_effect = Exception("TrendRadar unavailable")
                mock_fallback.return_value = [4, 5, 6]

                # Should not raise, just return fallback result
                result = await integration.collect_trending_with_fallback(agent, bindings)

                # Fallback should be called
                mock_fallback.assert_called_once()


class TestGetTrendRadarIntegration:
    """Tests for factory function."""

    def test_get_trendradar_integration_returns_instance(self):
        """Factory returns TrendRadarIntegration instance."""
        db_session = MagicMock()
        integration = get_trendradar_integration(db_session)

        assert isinstance(integration, TrendRadarIntegration)
        assert integration.session is db_session


class TestScoringAlgorithm:
    """Tests for the scoring algorithm with realistic scenarios."""

    @pytest.mark.asyncio
    async def test_hotness_influence_on_score(self):
        """Higher hotness gives higher base score."""
        db_session = MagicMock()
        adapter = TrendRadarAdapter(db_session)

        hot_item = TrendRadarNewsItem(
            title="Hot News",
            url="https://example.com/hot",
            source_platform="weibo",
            hot_value=10000,  # Very hot
            rank=1,
            summary="",
            image_url="",
            author="",
            timestamp=datetime.now(timezone.utc),
            source_url="",
            metadata={},
        )

        cold_item = TrendRadarNewsItem(
            title="Cold News",
            url="https://example.com/cold",
            source_platform="weibo",
            hot_value=100,  # Not very hot
            rank=500,
            summary="",
            image_url="",
            author="",
            timestamp=datetime.now(timezone.utc),
            source_url="",
            metadata={},
        )

        agent = MagicMock()
        agent.id = 1
        agent.keywords = []

        items = [hot_item, cold_item]
        scored = await adapter._score_and_filter(agent_id=1, items=items)

        # Hot item should have higher score
        hot_score = next(score for item, score in scored if "hot" in item.title.lower())
        cold_score = next(score for item, score in scored if "cold" in item.title.lower())

        assert hot_score > cold_score

    @pytest.mark.asyncio
    async def test_recency_influence_on_score(self):
        """More recent items get higher scores."""
        from datetime import timedelta

        db_session = MagicMock()
        adapter = TrendRadarAdapter(db_session)

        now = datetime.now(timezone.utc)
        recent_item = TrendRadarNewsItem(
            title="Recent News",
            url="https://example.com/recent",
            source_platform="weibo",
            hot_value=100,
            rank=1,
            summary="",
            image_url="",
            author="",
            timestamp=now,  # Now
            source_url="",
            metadata={},
        )

        old_item = TrendRadarNewsItem(
            title="Old News",
            url="https://example.com/old",
            source_platform="weibo",
            hot_value=100,
            rank=1,
            summary="",
            image_url="",
            author="",
            timestamp=now - timedelta(hours=24),  # 1 day old
            source_url="",
            metadata={},
        )

        agent = MagicMock()
        agent.id = 1
        agent.keywords = []

        items = [recent_item, old_item]
        scored = await adapter._score_and_filter(agent_id=1, items=items)

        recent_score = next(score for item, score in scored if "recent" in item.title.lower())
        old_score = next(score for item, score in scored if "old" in item.title.lower())

        # Recent should score higher
        assert recent_score >= old_score


# Run all tests
if __name__ == "__main__":
    pytest.main([__file__, "-v"])
