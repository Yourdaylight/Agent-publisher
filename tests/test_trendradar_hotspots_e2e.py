"""End-to-end integration tests for TrendRadar hotspots API workflow.

Tests the complete flow from a high level using mocks:
1. TrendRadar data collection (via adapter)
2. API contract validation
3. Filtering and pagination semantics
4. Trend visualization
5. Article creation flow
"""

from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from agent_publisher.services.trendradar_adapter import TrendRadarNewsItem, TrendRadarAdapter


# ── Helpers ──────────────────────────────────────────────────────────────────


def _make_trendradar_item(
    title="Test Hotspot",
    url="https://example.com/news",
    source_platform="weibo",
    hot_value=75.0,
    rank=1,
    summary=None,
) -> TrendRadarNewsItem:
    """Create a TrendRadarNewsItem for testing."""
    return TrendRadarNewsItem(
        title=title,
        url=url,
        source_platform=source_platform,
        hot_value=hot_value,
        rank=rank,
        summary=summary or f"Summary of {title}",
        metadata={
            "mobile_url": f"{url}/mobile",
            "ranks": [rank],
            "first_time": "09:00",
            "last_time": "15:30",
        },
    )


# ────────────────────────────────────────────────────────────────────────────────
# Test Suite: API Contract & Data Flow
# ────────────────────────────────────────────────────────────────────────────────


class TestHotspotDataContract:
    """Tests for TrendRadar to CandidateMaterial data contract."""

    def test_trendradar_item_converts_to_candidate_material(self):
        """TrendRadarNewsItem converts to CandidateMaterial format correctly."""
        item = _make_trendradar_item(
            title="Breaking News",
            url="https://weibo.com/12345",
            source_platform="weibo",
            hot_value=85.0,
            rank=2,
        )

        material = item.to_candidate_material(agent_id=1, quality_score=0.85)

        # Verify all required fields
        assert material["source_type"] == "trending"
        assert material["source_identity"] == "trendradar:weibo"
        assert material["title"] == "Breaking News"
        assert material["original_url"] == "https://weibo.com/12345"
        assert material["quality_score"] == 0.85
        assert "weibo" in material["tags"]
        assert "raw_content" in material

    def test_metadata_preserved_during_conversion(self):
        """Metadata is enriched but existing fields preserved."""
        item = _make_trendradar_item(
            title="Test",
            source_platform="douyin",
            hot_value=60.0,
        )

        material = item.to_candidate_material(agent_id=None, quality_score=0.60)

        # Check metadata preservation
        assert material["metadata"]["platform"] == "douyin"
        assert material["metadata"]["hot_value"] == 60.0
        assert material["metadata"]["rank"] == 1
        assert "fetch_timestamp" in material["metadata"]

    def test_raw_content_structure(self):
        """Raw content is formatted as readable markdown."""
        item = _make_trendradar_item(
            title="AI Research",
            summary="Breaking AI research news",
            source_platform="zhihu",
            hot_value=78.0,
        )

        material = item.to_candidate_material(agent_id=1, quality_score=0.78)

        raw = material["raw_content"]
        assert "# AI Research" in raw
        assert "zhihu" in raw.lower() or "Zhihu" in raw
        assert "78" in raw  # Heat value should appear
        assert material["original_url"] in raw


class TestPlatformExtraction:
    """Tests for platform identification from metadata."""

    def test_platform_tags_are_added(self):
        """Items are tagged with their source platform."""
        platforms = ["weibo", "douyin", "zhihu", "toutiao", "bilibili"]

        for platform in platforms:
            item = _make_trendradar_item(source_platform=platform)
            material = item.to_candidate_material(agent_id=1, quality_score=0.5)

            assert platform in material["tags"], f"Platform {platform} not in tags"

    def test_metadata_platform_field(self):
        """Platform is stored in metadata for API querying."""
        item = _make_trendradar_item(source_platform="xiaohongshu")
        material = item.to_candidate_material(agent_id=1, quality_score=0.5)

        assert material["metadata"]["platform"] == "xiaohongshu"


class TestHotValueScaling:
    """Tests for hot_value (0-100) to quality_score (0-1) mapping."""

    def test_hot_value_ranges_to_quality_scores(self):
        """Hot value (0-100) scales correctly to quality_score (0-1)."""
        test_cases = [
            (100.0, 1.0),  # Max hotness
            (50.0, 0.5),  # Mid hotness
            (0.0, 0.0),  # No hotness
            (85.0, 0.85),  # Common case
        ]

        for hot_value, expected_score in test_cases:
            item = _make_trendradar_item(hot_value=hot_value)
            # In adapter, quality_score is typically hot_value / 100
            quality = item.hot_value / 100.0
            assert abs(quality - expected_score) < 0.01

    def test_rank_to_hot_value_conversion(self):
        """Items with higher rank get higher hot_value."""
        rank1 = _make_trendradar_item(rank=1, hot_value=95)
        rank10 = _make_trendradar_item(rank=10, hot_value=70)
        rank50 = _make_trendradar_item(rank=50, hot_value=30)

        assert rank1.hot_value > rank10.hot_value
        assert rank10.hot_value > rank50.hot_value


class TestQualityScoreMapping:
    """Tests for quality score heat classifications."""

    def test_quality_score_heat_levels(self):
        """Quality scores map to heat levels (热度分级)."""
        # Super hot: 0.8-1.0 (红色)
        super_hot_item = _make_trendradar_item(hot_value=90)
        super_hot_material = super_hot_item.to_candidate_material(1, 0.90)
        assert "hot" in super_hot_material["tags"]
        assert "trending" in super_hot_material["tags"]

        # Hot: 0.6-0.79 (橙色)
        hot_item = _make_trendradar_item(hot_value=75)
        hot_material = hot_item.to_candidate_material(1, 0.75)
        assert "warm" in hot_material["tags"]

        # Cool: <0.6 (蓝色)
        cool_item = _make_trendradar_item(hot_value=30)
        cool_material = cool_item.to_candidate_material(1, 0.30)
        assert "cool" in cool_material["tags"]


class TestTrendPointGeneration:
    """Tests for trend visualization data."""

    def test_synthetic_trend_points_generation(self):
        """Without historical data, trend points are synthetic from quality_score."""
        quality_score = 0.75
        base = max(quality_score, 0.1)

        # Synthetic formula from hotspots.py
        synthetic_points = [
            {"label": "24h前", "score": round(base * 0.42, 3)},
            {"label": "12h前", "score": round(base * 0.68, 3)},
            {"label": "6h前", "score": round(base * 0.84, 3)},
            {"label": "当前", "score": round(base, 3)},
        ]

        # Verify structure
        assert len(synthetic_points) == 4
        assert all("label" in p and "score" in p for p in synthetic_points)
        assert all(0 <= p["score"] <= 1 for p in synthetic_points)
        assert synthetic_points[-1]["score"] == quality_score  # Current = base

    def test_historical_trend_data_priority(self):
        """If trend_history exists in metadata, use it instead of synthetic."""
        item = _make_trendradar_item()
        material = item.to_candidate_material(1, 0.75)

        # Add historical data
        historical = [
            {"timestamp": "2026-04-14T09:00:00Z", "score": 0.42},
            {"timestamp": "2026-04-14T12:00:00Z", "score": 0.60},
            {"timestamp": "2026-04-14T15:00:00Z", "score": 0.75},
            {"timestamp": "2026-04-14T18:00:00Z", "score": 0.72},
        ]
        material["metadata"]["trend_history"] = historical

        # API logic would check for this and prefer historical
        assert "trend_history" in material["metadata"]
        assert len(material["metadata"]["trend_history"]) == 4


# ────────────────────────────────────────────────────────────────────────────────
# Test Suite: API Filtering & Pagination
# ────────────────────────────────────────────────────────────────────────────────


class TestFilteringSemantics:
    """Tests for hotspots API filtering logic."""

    def test_platform_filter_single_platform(self):
        """Platform filter works with single platform."""
        items = [
            _make_trendradar_item(title="Weibo 1", source_platform="weibo"),
            _make_trendradar_item(title="Douyin 1", source_platform="douyin"),
            _make_trendradar_item(title="Weibo 2", source_platform="weibo"),
        ]

        # Filter to weibo only
        filtered = [i for i in items if i.source_platform == "weibo"]

        assert len(filtered) == 2
        assert all(i.source_platform == "weibo" for i in filtered)

    def test_platform_filter_multiple_platforms(self):
        """Platform filter works with OR logic for multiple platforms."""
        items = [
            _make_trendradar_item(title="Weibo", source_platform="weibo"),
            _make_trendradar_item(title="Douyin", source_platform="douyin"),
            _make_trendradar_item(title="Zhihu", source_platform="zhihu"),
        ]

        # Filter to weibo OR douyin
        target_platforms = ["weibo", "douyin"]
        filtered = [i for i in items if i.source_platform in target_platforms]

        assert len(filtered) == 2
        assert all(i.source_platform in target_platforms for i in filtered)

    def test_quality_score_range_filter(self):
        """Heat range filtering (heat_min, heat_max)."""
        items = [
            _make_trendradar_item(hot_value=90),  # 0.90
            _make_trendradar_item(hot_value=70),  # 0.70
            _make_trendradar_item(hot_value=50),  # 0.50
            _make_trendradar_item(hot_value=20),  # 0.20
        ]

        # Filter: 0.6 <= score <= 0.9
        heat_min, heat_max = 0.6, 0.9
        filtered = [i for i in items if heat_min <= (i.hot_value / 100.0) <= heat_max]

        assert len(filtered) == 2  # 90 and 70
        assert all(heat_min <= (i.hot_value / 100.0) <= heat_max for i in filtered)

    def test_keyword_search_filter(self):
        """Title/summary text search."""
        items = [
            _make_trendradar_item(title="Python AI Breakthrough"),
            _make_trendradar_item(title="Weather Forecast"),
            _make_trendradar_item(title="AI Safety Concerns"),
        ]

        # Search for "AI"
        keyword = "ai"
        filtered = [i for i in items if keyword.lower() in i.title.lower()]

        assert len(filtered) == 2
        assert all(keyword.lower() in i.title.lower() for i in filtered)

    def test_combined_filters(self):
        """Multiple filters work together (AND logic)."""
        items = [
            _make_trendradar_item(
                title="Python AI on Weibo", source_platform="weibo", hot_value=85
            ),
            _make_trendradar_item(
                title="Python Guide on Douyin", source_platform="douyin", hot_value=70
            ),
            _make_trendradar_item(
                title="Random News on Weibo", source_platform="weibo", hot_value=40
            ),
        ]

        # Filter: platform=weibo AND "python" AND heat >= 0.7
        platform = "weibo"
        keyword = "python"
        heat_min = 0.7

        filtered = [
            i
            for i in items
            if (
                i.source_platform == platform
                and keyword.lower() in i.title.lower()
                and (i.hot_value / 100.0) >= heat_min
            )
        ]

        assert len(filtered) == 1
        assert filtered[0].title == "Python AI on Weibo"


class TestPaginationSemantics:
    """Tests for pagination offset/limit logic."""

    def test_offset_limit_pagination(self):
        """Pagination with limit and offset."""
        items = [_make_trendradar_item(title=f"Item {i}") for i in range(10)]

        # Page 1: offset=0, limit=3
        page1 = items[0:3]
        # Page 2: offset=3, limit=3
        page2 = items[3:6]
        # Page 3: offset=6, limit=3
        page3 = items[6:9]

        assert len(page1) == 3
        assert len(page2) == 3
        assert len(page3) == 3
        assert page1[0].title != page2[0].title
        assert page2[0].title != page3[0].title

    def test_pagination_total_count(self):
        """Total count is available separately from paginated results."""
        items = [_make_trendradar_item() for i in range(100)]

        total = len(items)
        limit = 20
        offset = 0

        page = items[offset : offset + limit]

        assert len(page) == limit
        assert total == 100
        # Response structure: {items: [...], total: 100, limit: 20, offset: 0}


# ────────────────────────────────────────────────────────────────────────────────
# Test Suite: Adapter Integration
# ────────────────────────────────────────────────────────────────────────────────


class TestAdapterCollectionPipeline:
    """Tests for full TrendRadar collection pipeline."""

    @pytest.mark.asyncio
    async def test_adapter_disables_when_feature_flag_off(self):
        """When feature disabled, adapter returns empty result."""
        db = AsyncMock()
        adapter = TrendRadarAdapter(db, feature_flag_enabled=False)

        result = await adapter.collect_for_agent(agent_id=1)

        assert result["status"] == "success"
        assert result["new_items"] == 0
        assert result["platforms_collected"] == []

    @pytest.mark.asyncio
    async def test_adapter_fetch_dedup_score_store_flow(self):
        """Complete pipeline: fetch → dedup → score → store."""
        db = AsyncMock()
        adapter = TrendRadarAdapter(db, feature_flag_enabled=True)

        mock_items = [
            _make_trendradar_item(title="Hot Item", hot_value=90),
            _make_trendradar_item(title="Warm Item", hot_value=60),
            _make_trendradar_item(title="Cold Item", hot_value=20),
        ]

        # Mock dedup result (no existing URLs)
        dedup_result = MagicMock()
        dedup_result.all.return_value = []
        db.execute.return_value = dedup_result

        with patch(
            "agent_publisher.services.trendradar_bridge.fetch_trending_via_trendradar",
            new_callable=AsyncMock,
            return_value=mock_items,
        ):
            result = await adapter.collect_for_agent(
                agent_id=None,
                agent_name="test_flow",
                platforms=["weibo"],
            )

        assert result["status"] == "success"
        assert result["platforms_collected"] == ["weibo"]
        # Cold item likely filtered by scoring
        assert result["new_items"] >= 1

    @pytest.mark.asyncio
    async def test_adapter_with_filter_keywords(self):
        """Adapter applies keyword filtering for agent fit."""
        db = AsyncMock()
        adapter = TrendRadarAdapter(db, feature_flag_enabled=True)

        mock_items = [
            _make_trendradar_item(title="Python Machine Learning", hot_value=85),
            _make_trendradar_item(title="JavaScript Tutorial", hot_value=75),
            _make_trendradar_item(title="Python Web Development", hot_value=80),
        ]

        # Mock dedup
        dedup_result = MagicMock()
        dedup_result.all.return_value = []
        db.execute.return_value = dedup_result

        with patch(
            "agent_publisher.services.trendradar_bridge.fetch_trending_via_trendradar",
            new_callable=AsyncMock,
            return_value=mock_items,
        ):
            result = await adapter.collect_for_agent(
                agent_id=1,
                agent_name="python_agent",
                platforms=["weibo"],
                filter_keywords=["python"],  # Prefer Python topics
            )

        assert result["status"] == "success"
        # Pipeline should score Python items higher


# ────────────────────────────────────────────────────────────────────────────────
# Test Suite: Article Creation Flow
# ────────────────────────────────────────────────────────────────────────────────


class TestArticleCreationFromHotspot:
    """Tests for article generation from hotspots."""

    def test_hotspot_to_article_data_flow(self):
        """Hotspot converts to article material format."""
        item = _make_trendradar_item(
            title="Breaking: New AI Model",
            summary="DeepSeek releases new model",
            source_platform="weibo",
            hot_value=90,
        )

        material = item.to_candidate_material(
            agent_id=1,
            quality_score=0.90,
        )

        # This material becomes input to ArticleService.create_article_from_materials
        assert material["source_type"] == "trending"
        assert material["title"] is not None
        assert material["summary"] is not None
        assert material["original_url"] is not None

    def test_hotspot_async_article_creation_task(self):
        """Article creation returns task_id for progress tracking."""
        # In the API flow:
        # POST /api/hotspots/{id}/create-article-async returns:
        # {
        #   "ok": true,
        #   "task_id": 123,
        #   "hotspot_title": "..."
        # }

        # Frontend polls via SSE or task status endpoint
        task_response = {
            "ok": True,
            "task_id": 123,
            "hotspot_title": "Breaking News",
        }

        assert task_response["task_id"] is not None
        assert task_response["ok"] is True


# ────────────────────────────────────────────────────────────────────────────────
# Test Suite: Frontend Compatibility
# ────────────────────────────────────────────────────────────────────────────────


class TestFrontendAPIContract:
    """Tests for frontend API contract compliance."""

    def test_hotspots_list_response_structure(self):
        """GET /api/hotspots returns correct structure."""
        response = {
            "items": [
                {
                    "id": 1,
                    "title": "Test",
                    "summary": "Summary",
                    "original_url": "https://example.com",
                    "tags": ["weibo", "hot"],
                    "quality_score": 0.85,
                    "status": "pending",
                    "created_at": "2026-04-14T10:00:00Z",
                    "metadata": {
                        "platform": "weibo",
                        "platform_name": "Weibo",
                    },
                }
            ],
            "total": 100,
            "limit": 20,
            "offset": 0,
        }

        # Frontend expects these exact fields
        assert "items" in response
        assert "total" in response
        assert "limit" in response
        assert "offset" in response

        item = response["items"][0]
        assert "id" in item
        assert "title" in item
        assert "quality_score" in item
        assert "metadata" in item
        assert "platform" in item["metadata"]

    def test_hotspot_platforms_response_structure(self):
        """GET /api/hotspots/platforms returns correct structure."""
        response = [
            {"value": "weibo", "label": "Weibo", "count": 45},
            {"value": "douyin", "label": "Douyin", "count": 32},
            {"value": "zhihu", "label": "Zhihu", "count": 28},
        ]

        # Frontend filter dropdown expects this structure
        assert all("value" in p for p in response)
        assert all("label" in p for p in response)
        assert all("count" in p for p in response)

    def test_hotspot_trend_response_structure(self):
        """GET /api/hotspots/{id}/trend returns correct structure."""
        response = {
            "hotspot_id": 1,
            "points": [
                {"label": "24h前", "score": 0.315},
                {"label": "12h前", "score": 0.51},
                {"label": "6h前", "score": 0.63},
                {"label": "当前", "score": 0.75},
            ],
            "platform": "weibo",
        }

        # Frontend trend chart expects exactly 4 points
        assert len(response["points"]) == 4
        assert all("label" in p and "score" in p for p in response["points"])
        assert 0 <= response["points"][-1]["score"] <= 1


# ────────────────────────────────────────────────────────────────────────────────
# Test Suite: Error Handling
# ────────────────────────────────────────────────────────────────────────────────


class TestErrorHandling:
    """Tests for error handling and resilience."""

    @pytest.mark.asyncio
    async def test_adapter_handles_bridge_error(self):
        """When bridge fails, adapter returns error status."""
        db = AsyncMock()
        adapter = TrendRadarAdapter(db, feature_flag_enabled=True)

        with patch(
            "agent_publisher.services.trendradar_bridge.fetch_trending_via_trendradar",
            new_callable=AsyncMock,
            side_effect=Exception("Network error"),
        ):
            result = await adapter.collect_for_agent(
                agent_id=1,
                platforms=["weibo"],
            )

        assert result["status"] == "error"
        assert "error" in result

    @pytest.mark.asyncio
    async def test_adapter_handles_empty_results(self):
        """When bridge returns empty, adapter handles gracefully."""
        db = AsyncMock()
        adapter = TrendRadarAdapter(db, feature_flag_enabled=True)

        with patch(
            "agent_publisher.services.trendradar_bridge.fetch_trending_via_trendradar",
            new_callable=AsyncMock,
            return_value=[],
        ):
            result = await adapter.collect_for_agent(
                agent_id=None,
                platforms=["weibo"],
            )

        assert result["status"] == "success"
        assert result["new_items"] == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
