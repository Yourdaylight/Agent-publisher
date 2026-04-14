"""Integration tests for TrendRadar collection flow in source_registry_service."""
from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock, patch


class TestSourceRegistryTrendRadarIntegration:
    """Tests for TrendRadar integration in SourceRegistryService._collect_trending."""

    def _make_registry(self, db_session=None):
        from agent_publisher.services.source_registry_service import SourceRegistryService
        return SourceRegistryService(db_session or AsyncMock())

    def _make_binding(self, platform_id="weibo", filter_keywords=None):
        binding = MagicMock()
        binding.source_config = MagicMock()
        binding.source_config.config = {"platform_id": platform_id}
        binding.source_config.is_enabled = True
        binding.is_enabled = True
        binding.filter_keywords = filter_keywords
        return binding

    def _make_agent(self, agent_id=1, name="Test Agent"):
        agent = MagicMock()
        agent.id = agent_id
        agent.name = name
        return agent

    @pytest.mark.asyncio
    async def test_collect_trending_uses_adapter(self):
        """_collect_trending uses TrendRadarAdapter directly."""
        db = AsyncMock()
        registry = self._make_registry(db)

        agent = self._make_agent()
        binding = self._make_binding("weibo")

        mock_adapter = AsyncMock()
        mock_adapter.collect_for_agent = AsyncMock(return_value={
            "status": "success",
            "new_items": 3,
            "duplicates_skipped": 1,
            "low_quality_skipped": 0,
            "platforms_collected": ["weibo"],
        })

        # Mock the material IDs query
        mock_result = MagicMock()
        mock_result.all.return_value = [(10,), (11,), (12,)]
        db.execute.return_value = mock_result

        with patch(
            "agent_publisher.services.trendradar_adapter.get_trendradar_adapter",
            new_callable=AsyncMock,
            return_value=mock_adapter,
        ):
            result = await registry._collect_trending(agent, [binding])

        mock_adapter.collect_for_agent.assert_called_once_with(
            agent_id=1,
            agent_name="Test Agent",
            platforms=["weibo"],
            filter_keywords=None,
        )
        assert result == [10, 11, 12]

    @pytest.mark.asyncio
    async def test_collect_trending_passes_filter_keywords(self):
        """Filter keywords from bindings are passed to adapter."""
        db = AsyncMock()
        registry = self._make_registry(db)

        agent = self._make_agent()
        binding = self._make_binding("weibo", filter_keywords=["python", "AI"])

        mock_adapter = AsyncMock()
        mock_adapter.collect_for_agent = AsyncMock(return_value={
            "status": "success",
            "new_items": 1,
            "duplicates_skipped": 0,
            "low_quality_skipped": 0,
            "platforms_collected": ["weibo"],
        })

        mock_result = MagicMock()
        mock_result.all.return_value = [(10,)]
        db.execute.return_value = mock_result

        with patch(
            "agent_publisher.services.trendradar_adapter.get_trendradar_adapter",
            new_callable=AsyncMock,
            return_value=mock_adapter,
        ):
            await registry._collect_trending(agent, [binding])

        call_kwargs = mock_adapter.collect_for_agent.call_args[1]
        assert call_kwargs["filter_keywords"] == ["python", "AI"]

    @pytest.mark.asyncio
    async def test_collect_trending_no_platform_configs(self):
        """With no platform configs, returns empty list."""
        registry = self._make_registry()

        agent = self._make_agent()
        binding = MagicMock()
        binding.source_config = MagicMock()
        binding.source_config.config = {}  # No platform_id
        binding.filter_keywords = None

        result = await registry._collect_trending(agent, [binding])
        assert result == []

    @pytest.mark.asyncio
    async def test_collect_trending_handles_error(self):
        """On adapter error, returns empty list."""
        db = AsyncMock()
        registry = self._make_registry(db)

        agent = self._make_agent()
        binding = self._make_binding("weibo")

        mock_adapter = AsyncMock()
        mock_adapter.collect_for_agent = AsyncMock(return_value={
            "status": "error",
            "error": "Connection failed",
            "new_items": 0,
            "platforms_collected": [],
        })

        with patch(
            "agent_publisher.services.trendradar_adapter.get_trendradar_adapter",
            new_callable=AsyncMock,
            return_value=mock_adapter,
        ):
            result = await registry._collect_trending(agent, [binding])

        assert result == []

    @pytest.mark.asyncio
    async def test_collect_trending_multiple_bindings(self):
        """Collects from multiple platform bindings."""
        db = AsyncMock()
        registry = self._make_registry(db)

        agent = self._make_agent()
        bindings = [
            self._make_binding("weibo"),
            self._make_binding("zhihu"),
            self._make_binding("bilibili"),
        ]

        mock_adapter = AsyncMock()
        mock_adapter.collect_for_agent = AsyncMock(return_value={
            "status": "success",
            "new_items": 5,
            "duplicates_skipped": 0,
            "low_quality_skipped": 0,
            "platforms_collected": ["weibo", "zhihu", "bilibili"],
        })

        mock_result = MagicMock()
        mock_result.all.return_value = [(1,), (2,), (3,), (4,), (5,)]
        db.execute.return_value = mock_result

        with patch(
            "agent_publisher.services.trendradar_adapter.get_trendradar_adapter",
            new_callable=AsyncMock,
            return_value=mock_adapter,
        ):
            result = await registry._collect_trending(agent, bindings)

        call_kwargs = mock_adapter.collect_for_agent.call_args[1]
        assert sorted(call_kwargs["platforms"]) == ["bilibili", "weibo", "zhihu"]
        assert len(result) == 5


class TestCollectAllTrending:
    """Tests for global trending refresh via collect_all_trending."""

    @pytest.mark.asyncio
    async def test_collect_all_trending_uses_adapter(self):
        """collect_all_trending uses TrendRadarAdapter."""
        db = AsyncMock()

        from agent_publisher.services.source_registry_service import SourceRegistryService
        registry = SourceRegistryService(db)

        # Mock list_sources to return some trending sources
        mock_source = MagicMock()
        mock_source.config = {"platform_id": "weibo"}
        registry.list_sources = AsyncMock(return_value=[mock_source])

        mock_adapter = AsyncMock()
        mock_adapter.collect_for_agent = AsyncMock(return_value={
            "status": "success",
            "new_items": 10,
            "duplicates_skipped": 3,
            "platforms_collected": ["weibo"],
        })

        with patch(
            "agent_publisher.services.trendradar_adapter.get_trendradar_adapter",
            new_callable=AsyncMock,
            return_value=mock_adapter,
        ):
            result = await registry.collect_all_trending()

        assert result["new_items"] == 10
        assert result["duplicate_items"] == 3
        mock_adapter.collect_for_agent.assert_called_once()
        call_kwargs = mock_adapter.collect_for_agent.call_args[1]
        assert call_kwargs["agent_id"] is None
        assert call_kwargs["agent_name"] == "global_trending"

    @pytest.mark.asyncio
    async def test_collect_all_trending_no_sources(self):
        """No enabled sources returns empty result."""
        db = AsyncMock()

        from agent_publisher.services.source_registry_service import SourceRegistryService
        registry = SourceRegistryService(db)
        registry.list_sources = AsyncMock(return_value=[])

        result = await registry.collect_all_trending()
        assert result["platforms_collected"] == []
        assert result["new_items"] == 0


class TestCollectForAgent:
    """Tests for full collect_for_agent dispatch."""

    @pytest.mark.asyncio
    async def test_collect_for_agent_includes_trending(self):
        """collect_for_agent dispatches trending to _collect_trending."""
        db = AsyncMock()

        from agent_publisher.services.source_registry_service import SourceRegistryService
        registry = SourceRegistryService(db)

        agent = MagicMock()
        agent.id = 1
        agent.name = "Test Agent"

        binding = MagicMock()
        binding.is_enabled = True
        binding.source_config = MagicMock()
        binding.source_config.source_type = "trending"
        binding.source_config.is_enabled = True

        registry.list_agent_bindings = AsyncMock(return_value=[binding])
        registry._collect_trending = AsyncMock(return_value=[1, 2, 3])

        result = await registry.collect_for_agent(agent)

        assert "trending" in result
        assert result["trending"] == [1, 2, 3]
        registry._collect_trending.assert_called_once()
