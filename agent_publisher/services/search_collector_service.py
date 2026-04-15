"""Search collector adapter – stub/framework layer.

This module defines the base interface and a stub implementation for the
independent web search collection mode. When an Agent has source_mode =
'independent_search', this adapter is used to collect materials.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod

from sqlalchemy.ext.asyncio import AsyncSession

from agent_publisher.services.candidate_material_service import CandidateMaterialService

logger = logging.getLogger(__name__)


class BaseSearchCollector(ABC):
    """Abstract base class for search-based collectors."""

    @abstractmethod
    async def collect(
        self,
        agent_id: int,
        agent_name: str,
        search_config: dict,
    ) -> list[int]:
        """Execute a search collection cycle.

        Returns list of created CandidateMaterial IDs.
        """
        ...


class StubSearchCollector(BaseSearchCollector):
    """Stub implementation that logs but produces no real results.

    This serves as a placeholder until a real search engine / crawler is
    integrated. It validates the search_config and returns an empty list.
    """

    def __init__(self, session: AsyncSession):
        self.session = session
        self.material_service = CandidateMaterialService(session)

    async def collect(
        self,
        agent_id: int,
        agent_name: str,
        search_config: dict,
    ) -> list[int]:
        if not search_config:
            logger.warning(
                "Agent %s (id=%d) has source_mode=independent_search "
                "but search_config is empty. Collection skipped.",
                agent_name,
                agent_id,
            )
            return []

        keywords = search_config.get("keywords", [])
        domain = search_config.get("domain", "")
        sites = search_config.get("site_constraints", [])

        if not keywords and not domain:
            logger.warning(
                "Agent %s search_config has no keywords or domain. "
                "Cannot perform search collection.",
                agent_name,
            )
            return []

        # TODO: Replace with actual search API integration
        logger.info(
            "StubSearchCollector: would search domain=%r keywords=%r sites=%r for agent %s",
            domain,
            keywords,
            sites,
            agent_name,
        )
        return []


def get_search_collector(session: AsyncSession) -> BaseSearchCollector:
    """Factory function to get the active search collector implementation."""
    return StubSearchCollector(session)
