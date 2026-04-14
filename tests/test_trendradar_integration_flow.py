"""Integration tests for TrendRadar collection flow in source_registry_service."""
from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timezone

from agent_publisher.services.source_registry_service import SourceRegistryService
from agent_publisher.services.trendradar_adapter import TrendRadarNewsItem


class TestSourceRegistryTrendRadarIntegration:
    """Tests for TrendRadar integration in SourceRegistryService."""

    @pytest.mark.asyncio
    async def test_collect_trending_with_trendradar_disabled(self):
        """When feature flag disabled, uses TrendingCollectorService."""
        db_session = AsyncMock()

        registry = SourceRegistryService(db_session)

        agent = MagicMock()
        agent.id = 1
        agent.name = "Test Agent"

        binding = MagicMock()
        binding.source_config = MagicMock()
        binding.source_config.config = {"platform_id": "weibo"}
        binding.filter_keywords = None

        bindings = [binding]

        # Mock TrendingCollectorService
        with patch('agent_publisher.services.source_registry_service.TrendingCollectorService') as mock_collector:
            mock_instance = AsyncMock()
            mock_instance.collect = AsyncMock(return_value=[1, 2, 3])
            mock_collector.return_value = mock_instance

            # Mock settings with trendradar_enabled = False
            with patch('agent_publisher.services.source_registry_service.settings') as mock_settings:
                mock_settings.trendradar_enabled = False

                result = await registry._collect_trending(agent, bindings)

                # Should call TrendingCollectorService
                mock_collector.assert_called_once_with(db_session)
                mock_instance.collect.assert_called_once()
                assert result == [1, 2, 3]

    @pytest.mark.asyncio
    async def test_collect_trending_with_trendradar_enabled_success(self):
        """When TrendRadar enabled and available, uses TrendRadar."""
        db_session = AsyncMock()

        registry = SourceRegistryService(db_session)

        agent = MagicMock()
        agent.id = 1
        agent.name = "Test Agent"

        binding = MagicMock()
        binding.source_config = MagicMock()
        binding.source_config.config = {"platform_id": "weibo"}
        binding.filter_keywords = None

        bindings = [binding]

        # Mock TrendRadar integration
        with patch('agent_publisher.services.source_registry_service.get_trendradar_integration') as mock_get_integration:
            mock_integration = AsyncMock()
            mock_integration.collect_trending_with_fallback = AsyncMock(return_value=[10, 11, 12])
            mock_get_integration.return_value = mock_integration

            # Mock settings with trendradar_enabled = True
            with patch('agent_publisher.services.source_registry_service.settings') as mock_settings:
                mock_settings.trendradar_enabled = True

                result = await registry._collect_trending(agent, bindings)

                # Should call TrendRadar integration
                mock_get_integration.assert_called_once_with(db_session)
                mock_integration.collect_trending_with_fallback.assert_called_once()
                assert result == [10, 11, 12]

    @pytest.mark.asyncio
    async def test_collect_trending_with_trendradar_error_falls_back(self):
        """When TrendRadar fails, falls back to TrendingCollectorService."""
        db_session = AsyncMock()

        registry = SourceRegistryService(db_session)

        agent = MagicMock()
        agent.id = 1
        agent.name = "Test Agent"

        binding = MagicMock()
        binding.source_config = MagicMock()
        binding.source_config.config = {"platform_id": "weibo"}
        binding.filter_keywords = None

        bindings = [binding]

        # Mock TrendRadar integration to fail
        with patch('agent_publisher.services.source_registry_service.get_trendradar_integration') as mock_get_integration:
            mock_integration = AsyncMock()
            mock_integration.collect_trending_with_fallback = AsyncMock(
                side_effect=Exception("TrendRadar service error")
            )
            mock_get_integration.return_value = mock_integration

            # Mock TrendingCollectorService as fallback
            with patch('agent_publisher.services.source_registry_service.TrendingCollectorService') as mock_collector:
                mock_instance = AsyncMock()
                mock_instance.collect = AsyncMock(return_value=[20, 21, 22])
                mock_collector.return_value = mock_instance

                # Mock settings with trendradar_enabled = True
                with patch('agent_publisher.services.source_registry_service.settings') as mock_settings:
                    mock_settings.trendradar_enabled = True

                    result = await registry._collect_trending(agent, bindings)

                    # Should try TrendRadar
                    mock_get_integration.assert_called_once()

                    # Should fall back to TrendingCollectorService
                    mock_collector.assert_called_once_with(db_session)
                    mock_instance.collect.assert_called_once()

                    # Should return fallback result
                    assert result == [20, 21, 22]

    @pytest.mark.asyncio
    async def test_collect_trending_no_platform_configs(self):
        """With no platform configs, returns empty list."""
        db_session = AsyncMock()

        registry = SourceRegistryService(db_session)

        agent = MagicMock()
        agent.id = 1
        agent.name = "Test Agent"

        binding = MagicMock()
        binding.source_config = MagicMock()
        binding.source_config.config = {}  # No platform_id
        binding.filter_keywords = None

        bindings = [binding]

        result = await registry._collect_trending(agent, bindings)

        # Should return empty list
        assert result == []

    @pytest.mark.asyncio
    async def test_collect_trending_preserves_filter_keywords(self):
        """Filter keywords are passed through to collector."""
        db_session = AsyncMock()

        registry = SourceRegistryService(db_session)

        agent = MagicMock()
        agent.id = 1
        agent.name = "Test Agent"

        binding = MagicMock()
        binding.source_config = MagicMock()
        binding.source_config.config = {"platform_id": "weibo"}
        binding.filter_keywords = ["python", "programming"]

        bindings = [binding]

        # Mock TrendingCollectorService
        with patch('agent_publisher.services.source_registry_service.TrendingCollectorService') as mock_collector:
            mock_instance = AsyncMock()
            mock_instance.collect = AsyncMock(return_value=[1, 2, 3])
            mock_collector.return_value = mock_instance

            # Mock settings with trendradar_enabled = False
            with patch('agent_publisher.services.source_registry_service.settings') as mock_settings:
                mock_settings.trendradar_enabled = False

                result = await registry._collect_trending(agent, bindings)

                # Check that filter_keywords were passed
                call_kwargs = mock_instance.collect.call_args[1]
                assert "filter_keywords" in call_kwargs
                assert call_kwargs["filter_keywords"] == ["python", "programming"]

    @pytest.mark.asyncio
    async def test_collect_for_agent_includes_trending(self):
        """collect_for_agent includes trending in results."""
        db_session = AsyncMock()

        registry = SourceRegistryService(db_session)

        # Mock the methods
        registry.list_agent_bindings = AsyncMock(return_value=[])
        registry._collect_rss = AsyncMock(return_value=[])
        registry._collect_trending = AsyncMock(return_value=[1, 2, 3])
        registry._collect_search = AsyncMock(return_value=[])

        agent = MagicMock()
        agent.id = 1
        agent.name = "Test Agent"

        # Create mock bindings
        binding = MagicMock()
        binding.is_enabled = True
        binding.source_config = MagicMock()
        binding.source_config.source_type = "trending"
        binding.source_config.is_enabled = True

        registry.list_agent_bindings = AsyncMock(return_value=[binding])

        result = await registry.collect_for_agent(agent)

        # Should have trending key
        assert "trending" in result
        assert result["trending"] == [1, 2, 3]


class TestLoggingAndMonitoring:
    """Tests for logging and monitoring during collection."""

    @pytest.mark.asyncio
    async def test_logs_collection_path_when_trendradar_enabled(self):
        """Logs indicate which collection path is used."""
        db_session = AsyncMock()

        registry = SourceRegistryService(db_session)

        agent = MagicMock()
        agent.id = 1
        agent.name = "Test Agent"

        binding = MagicMock()
        binding.source_config = MagicMock()
        binding.source_config.config = {"platform_id": "weibo"}
        binding.filter_keywords = None

        bindings = [binding]

        # Mock logger to capture calls
        with patch('agent_publisher.services.source_registry_service.logger') as mock_logger:
            with patch('agent_publisher.services.source_registry_service.get_trendradar_integration') as mock_get_integration:
                mock_integration = AsyncMock()
                mock_integration.collect_trending_with_fallback = AsyncMock(return_value=[1, 2])
                mock_get_integration.return_value = mock_integration

                with patch('agent_publisher.services.source_registry_service.settings') as mock_settings:
                    mock_settings.trendradar_enabled = True

                    await registry._collect_trending(agent, bindings)

                    # Should log info messages
                    assert mock_logger.info.called
                    log_calls = [str(call) for call in mock_logger.info.call_args_list]
                    # Check for TrendRadar-specific logging
                    assert any("TrendRadar" in str(call) for call in log_calls)

    @pytest.mark.asyncio
    async def test_logs_warning_on_trendradar_failure(self):
        """Logs warning when TrendRadar fails and falls back."""
        db_session = AsyncMock()

        registry = SourceRegistryService(db_session)

        agent = MagicMock()
        agent.id = 1
        agent.name = "Test Agent"

        binding = MagicMock()
        binding.source_config = MagicMock()
        binding.source_config.config = {"platform_id": "weibo"}
        binding.filter_keywords = None

        bindings = [binding]

        with patch('agent_publisher.services.source_registry_service.logger') as mock_logger:
            with patch('agent_publisher.services.source_registry_service.get_trendradar_integration') as mock_get_integration:
                mock_integration = AsyncMock()
                mock_integration.collect_trending_with_fallback = AsyncMock(
                    side_effect=Exception("TrendRadar failed")
                )
                mock_get_integration.return_value = mock_integration

                with patch('agent_publisher.services.source_registry_service.TrendingCollectorService') as mock_collector:
                    mock_instance = AsyncMock()
                    mock_instance.collect = AsyncMock(return_value=[1])
                    mock_collector.return_value = mock_instance

                    with patch('agent_publisher.services.source_registry_service.settings') as mock_settings:
                        mock_settings.trendradar_enabled = True

                        await registry._collect_trending(agent, bindings)

                        # Should log warning about failure
                        assert mock_logger.warning.called


# Run all tests
if __name__ == "__main__":
    pytest.main([__file__, "-v"])
