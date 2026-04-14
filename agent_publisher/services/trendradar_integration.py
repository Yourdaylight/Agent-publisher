"""
TrendRadar Integration Hook for Phase 1

This module integrates TrendRadar into the existing collection workflow.
It serves as the orchestration layer that:
1. Calls TrendRadar adapter for trending data
2. Maintains backward compatibility with existing trending_service
3. Provides feature flag for gradual rollout

Usage in source_registry_service:
  # In collect_for_agent method, replace _collect_trending call with:
  trending_ids = await self._collect_trending_with_trendradar(agent, by_type["trending"])
"""

from __future__ import annotations

import logging
from typing import Optional, List

from sqlalchemy.ext.asyncio import AsyncSession

from agent_publisher.models.agent import Agent
from agent_publisher.models.source_config import AgentSourceBinding

logger = logging.getLogger(__name__)


class TrendRadarIntegration:
    """
    Orchestration layer for TrendRadar integration with Agent Publisher.
    
    Architecture:
    1. Feature flag: trendradar_enabled (config.py)
    2. Fallback: If TrendRadar unavailable, use existing trending_service
    3. Parallel: Can run alongside existing system
    4. Non-breaking: 100% backward compatible
    """

    def __init__(self, db: AsyncSession):
        self.db = db
        self._initialized = False
        self._trendradar_available = False

    async def initialize(self):
        """
        Check TrendRadar availability at startup.
        
        This runs once to determine if TrendRadar package is available
        and properly configured.
        """
        if self._initialized:
            return

        try:
            from agent_publisher.services.trendradar_adapter import TrendRadarAdapter
            self._trendradar_available = True
            logger.info("TrendRadar integration initialized successfully")
        except ImportError:
            logger.warning("TrendRadar package not available, using fallback trending_service")
            self._trendradar_available = False
        except Exception as e:
            logger.error("TrendRadar initialization failed: %s", e)
            self._trendradar_available = False

        self._initialized = True

    async def collect_trending_with_fallback(
        self,
        agent: Agent,
        bindings: List[AgentSourceBinding],
    ) -> List[int]:
        """
        Collect trending data with TrendRadar → fallback strategy.
        
        Strategy:
        1. Try TrendRadar first (if enabled and available)
        2. Fall back to existing trending_service
        3. Handle errors gracefully
        
        Args:
            agent: Target agent
            bindings: Source bindings for this agent
        
        Returns:
            List of created CandidateMaterial IDs
        """
        from agent_publisher.config import settings

        # Initialize on first use
        await self.initialize()

        # Check feature flag
        trendradar_enabled = getattr(settings, "trendradar_enabled", False)

        if trendradar_enabled and self._trendradar_available:
            logger.info("Using TrendRadar for trending collection (agent=%d)", agent.id)
            try:
                return await self._collect_with_trendradar(agent, bindings)
            except Exception as e:
                logger.error(
                    "TrendRadar collection failed, falling back to trending_service: %s", e
                )
                return await self._collect_with_trending_service(agent, bindings)
        else:
            logger.info("TrendRadar disabled, using trending_service (agent=%d)", agent.id)
            return await self._collect_with_trending_service(agent, bindings)

    async def _collect_with_trendradar(
        self, agent: Agent, bindings: List[AgentSourceBinding]
    ) -> List[int]:
        """
        Collect trending data using TrendRadar adapter.
        
        Steps:
        1. Create adapter instance
        2. Call collect_for_agent
        3. Return created material IDs
        """
        from agent_publisher.services.trendradar_adapter import TrendRadarAdapter
        from agent_publisher.models.candidate_material import CandidateMaterial
        from sqlalchemy import select

        adapter = TrendRadarAdapter(self.db)

        # Extract platform list from bindings
        platforms = []
        for binding in bindings:
            if binding.source_config and binding.source_config.config:
                platform = binding.source_config.config.get("platform")
                if platform:
                    platforms.append(platform)

        # Collect from TrendRadar
        result = await adapter.collect_for_agent(
            agent.id,
            platforms=platforms if platforms else None,
        )

        if result["status"] != "success":
            logger.error("TrendRadar collection error: %s", result.get("error"))
            return []

        logger.info(
            "TrendRadar collection succeeded: platforms=%s, new_items=%d, duplicates=%d",
            result.get("platforms_collected", []),
            result.get("new_items", 0),
            result.get("duplicates_skipped", 0),
        )

        # Fetch newly created materials
        stmt = select(CandidateMaterial.id).where(
            CandidateMaterial.agent_id == agent.id,
            CandidateMaterial.source_type == "trending",
        )
        result = await self.db.execute(stmt)
        return [row[0] for row in result.all()]

    async def _collect_with_trending_service(
        self, agent: Agent, bindings: List[AgentSourceBinding]
    ) -> List[int]:
        """
        Fall back to existing trending_service for collection.
        
        This maintains 100% backward compatibility with the original system.
        """
        from agent_publisher.services.trending_service import (
            TrendingCollectorService,
            parse_keyword_rules,
        )
        from agent_publisher.models.candidate_material import CandidateMaterial
        from sqlalchemy import select

        service = TrendingCollectorService(self.db)
        collected_ids = []

        for binding in bindings:
            if not binding.source_config:
                continue

            source_key = binding.source_config.source_key
            filter_rules = binding.filter_keywords or ""

            try:
                # Parse filtering rules
                keyword_rules = parse_keyword_rules(filter_rules)

                # Collect from single platform
                result = await service.collect(
                    source_key=source_key,
                    agent_id=agent.id,
                    keyword_rules=keyword_rules,
                )

                logger.info(
                    "Collected %d materials from %s for agent %s",
                    result["count"],
                    source_key,
                    agent.name,
                )

                # Fetch created material IDs
                stmt = select(CandidateMaterial.id).where(
                    CandidateMaterial.agent_id == agent.id,
                    CandidateMaterial.source_type == "trending",
                )
                result = await self.db.execute(stmt)
                collected_ids.extend([row[0] for row in result.all()])

            except Exception as e:
                logger.error(
                    "Failed to collect from %s for agent %s: %s",
                    source_key,
                    agent.name,
                    e,
                )

        return collected_ids


def get_trendradar_integration(db: AsyncSession) -> TrendRadarIntegration:
    """Factory function for TrendRadar integration."""
    return TrendRadarIntegration(db)
