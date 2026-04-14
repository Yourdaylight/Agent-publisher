"""
TrendRadar Integration Adapter - Phase 1 Implementation

This adapter bridges TrendRadar (trending platform aggregation) with Agent Publisher
(content generation). It replaces the single NewsNow API with TrendRadar's 11-platform
aggregation while maintaining backward compatibility.

Architecture:
  TrendRadar          Agent Publisher
  (11 platforms)      (Content Generation)
       │                     │
       ├─ Weibo             │
       ├─ Douyin            │ 
       ├─ Xiaohongshu       ├─ NewsData
       ├─ Baidu             ├─ RSS
       ├─ Zhihu             └─ Manual
       ├─ Toutiao                │
       ├─ Bilibili               ↓
       ├─ V2EX              CandidateMaterial
       ├─ Github Trending        │
       ├─ NewsNow                ↓
       └─ RSS Feeds         LLM Generation
            │
            └─→ Unified Material Pool ←─→ CandidateMaterial

Data Flow:
  1. TrendRadar fetches from 11 platforms
  2. Adapter converts to CandidateMaterial format
  3. Agent Publisher uses enriched materials
  4. Feature flag enables gradual rollout
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional, Dict, List, Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


@dataclass
class TrendRadarNewsItem:
    """Unified news item from TrendRadar aggregation."""
    title: str
    url: str
    source_platform: str  # weibo, douyin, xiaohongshu, etc.
    hot_value: float  # Normalized 0-100 hotness score
    rank: int  # Platform-specific rank
    summary: Optional[str] = None
    image_url: Optional[str] = None
    timestamp: Optional[datetime] = None
    metadata: Optional[Dict[str, Any]] = None

    def to_candidate_material(self, agent_id: int, quality_score: float = 0.5) -> Dict[str, Any]:
        """Convert TrendRadar item to CandidateMaterial format."""
        return {
            "agent_id": agent_id,
            "source_type": "trending",  # Mark as trending source
            "source_identity": f"trendradar:{self.source_platform}",
            "original_url": self.url,
            "title": self.title,
            "summary": self.summary or self.title,
            "raw_content": self._build_raw_content(),
            "quality_score": quality_score,
            "tags": self._extract_tags(),
            "metadata": {
                "platform": self.source_platform,
                "hot_value": self.hot_value,
                "rank": self.rank,
                "source": "trendradar_adapter",
                **(self.metadata or {}),
            },
        }

    def _build_raw_content(self) -> str:
        """Build structured raw content from trending item."""
        content = f"# {self.title}\n\n"
        if self.summary:
            content += f"## 摘要\n{self.summary}\n\n"
        content += f"## 信息\n"
        content += f"- 平台: {self.source_platform}\n"
        content += f"- 热度: {self.hot_value}/100\n"
        content += f"- 排名: #{self.rank}\n"
        if self.image_url:
            content += f"- 图片: {self.image_url}\n"
        if self.timestamp:
            content += f"- 时间: {self.timestamp.isoformat()}\n"
        content += f"- 链接: {self.url}\n"
        return content

    def _extract_tags(self) -> List[str]:
        """Extract tags from title and metadata."""
        tags = [self.source_platform]
        # Add basic hotness tier
        if self.hot_value >= 80:
            tags.append("hot")
        elif self.hot_value >= 50:
            tags.append("warm")
        else:
            tags.append("cool")
        # Add rank tier
        if self.rank <= 10:
            tags.append("top10")
        elif self.rank <= 50:
            tags.append("top50")
        return tags


class TrendRadarAdapter:
    """
    Adapter for integrating TrendRadar with Agent Publisher.
    
    Responsibilities:
    1. Fetch trending data from TrendRadar backend
    2. Convert to CandidateMaterial format
    3. Manage deduplication and quality scoring
    4. Support feature flag for gradual rollout
    """

    def __init__(self, db: AsyncSession, feature_flag_enabled: bool = True):
        """
        Initialize adapter.
        
        Args:
            db: AsyncSession for database operations
            feature_flag_enabled: Enable/disable TrendRadar integration
        """
        self.db = db
        self.feature_flag_enabled = feature_flag_enabled

    async def collect_for_agent(
        self, agent_id: int, platforms: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Collect trending materials for an agent from TrendRadar.
        
        Args:
            agent_id: Target agent ID
            platforms: Filter by specific platforms (default: all 11)
        
        Returns:
            {
                "status": "success|error",
                "platforms_collected": ["weibo", "douyin", ...],
                "new_items": count,
                "duplicates_skipped": count,
                "low_quality_skipped": count,
                "error": error_message if status == "error"
            }
        """
        if not self.feature_flag_enabled:
            logger.info("TrendRadar adapter disabled, skipping collection")
            return {
                "status": "success",
                "platforms_collected": [],
                "new_items": 0,
                "duplicates_skipped": 0,
                "low_quality_skipped": 0,
            }

        try:
            from agent_publisher.config import settings

            # TODO: Phase 1 - Implement actual TrendRadar backend call
            # This is where we'll fetch from TrendRadar's data storage (SQLite/S3)
            # For now, return placeholder structure
            
            logger.info(
                "TrendRadar: Collecting trends for agent %d (platforms=%s)",
                agent_id,
                platforms or "all",
            )

            # Step 1: Fetch from TrendRadar
            items = await self._fetch_from_trendradar(platforms)
            logger.info("TrendRadar: Fetched %d items", len(items))

            # Step 2: Deduplicate against existing materials
            dedup_result = await self._deduplicate_items(agent_id, items)
            unique_items = dedup_result["unique_items"]
            duplicates_skipped = dedup_result["duplicates_skipped"]

            # Step 3: Score and filter
            scored_items = await self._score_and_filter(agent_id, unique_items)

            # Step 4: Convert and store
            created_count = await self._store_materials(agent_id, scored_items)

            return {
                "status": "success",
                "platforms_collected": sorted(set(item.source_platform for item in items)),
                "new_items": created_count,
                "duplicates_skipped": duplicates_skipped,
                "low_quality_skipped": len(unique_items) - created_count,
            }

        except Exception as e:
            logger.error("TrendRadar collection failed: %s", e, exc_info=True)
            return {
                "status": "error",
                "error": str(e),
                "platforms_collected": [],
                "new_items": 0,
            }

    async def _fetch_from_trendradar(
        self, platforms: Optional[List[str]] = None
    ) -> List[TrendRadarNewsItem]:
        """
        Fetch trending items from TrendRadar backend.
        
        TODO: Implement actual fetching from TrendRadar (Phase 1):
        1. Connect to TrendRadar SQLite/S3 storage
        2. Query recent trending items (last 24h)
        3. Filter by specified platforms (or all 11 if not specified)
        4. Parse into TrendRadarNewsItem dataclass
        """
        logger.debug("Fetching from TrendRadar (platforms=%s)", platforms)
        # Placeholder implementation
        return []

    async def _deduplicate_items(
        self, agent_id: int, items: List[TrendRadarNewsItem]
    ) -> Dict[str, Any]:
        """
        Check for duplicates against existing CandidateMaterial.
        
        Strategy:
        - Exact URL match
        - Title similarity (80%+ Levenshtein)
        - Combined deduplication score
        """
        from agent_publisher.models.candidate_material import CandidateMaterial

        existing_urls = set()
        result = await self.db.execute(
            select(CandidateMaterial.original_url).where(
                CandidateMaterial.agent_id == agent_id
            )
        )
        existing_urls = set(row[0] for row in result.all())

        unique_items = []
        duplicates_skipped = 0

        for item in items:
            if item.url in existing_urls:
                duplicates_skipped += 1
                logger.debug("Skipped duplicate URL: %s", item.url)
            else:
                unique_items.append(item)

        return {
            "unique_items": unique_items,
            "duplicates_skipped": duplicates_skipped,
        }

    async def _score_and_filter(
        self, agent_id: int, items: List[TrendRadarNewsItem]
    ) -> List[tuple[TrendRadarNewsItem, float]]:
        """
        Score items based on relevance and quality.
        
        Scoring formula (0-1):
        - Base hotness: hot_value / 100 (40% weight)
        - Recency: exp(-hours_old / 24) (30% weight)
        - Agent fit: keyword_relevance (30% weight)
        
        Filter: Keep items with score > 0.3
        """
        from agent_publisher.models.agent import Agent

        agent = await self.db.get(Agent, agent_id)
        if not agent:
            logger.warning("Agent %d not found for scoring", agent_id)
            return []

        scored = []
        for item in items:
            # Calculate components
            hotness_score = min(item.hot_value / 100.0, 1.0)
            recency_score = 0.8  # TODO: Calculate based on timestamp
            agent_fit_score = await self._calculate_agent_fit(agent, item)

            # Combined score
            final_score = (
                hotness_score * 0.4 + recency_score * 0.3 + agent_fit_score * 0.3
            )

            if final_score > 0.3:
                scored.append((item, final_score))
                logger.debug("Scored %s: %.2f", item.title[:50], final_score)
            else:
                logger.debug("Filtered (low score): %s: %.2f", item.title[:50], final_score)

        return sorted(scored, key=lambda x: x[1], reverse=True)

    async def _calculate_agent_fit(
        self, agent: Any, item: TrendRadarNewsItem
    ) -> float:
        """
        Calculate how well this item fits the agent's topic/keywords.
        
        TODO: Phase 2 - Implement semantic matching
        For Phase 1: Return 0.5 (neutral)
        """
        return 0.5

    async def _store_materials(
        self, agent_id: int, scored_items: List[tuple[TrendRadarNewsItem, float]]
    ) -> int:
        """
        Convert scored items to CandidateMaterial and store.
        """
        from agent_publisher.models.candidate_material import CandidateMaterial

        created = 0
        for item, score in scored_items:
            try:
                material_data = item.to_candidate_material(agent_id, score)
                material = CandidateMaterial(**material_data)
                self.db.add(material)
                created += 1
            except Exception as e:
                logger.error("Failed to create material from item %s: %s", item.title, e)

        if created > 0:
            await self.db.commit()
            logger.info("Created %d materials from TrendRadar", created)

        return created


async def get_trendradar_adapter(db: AsyncSession) -> TrendRadarAdapter:
    """Factory function to create TrendRadar adapter with feature flag."""
    from agent_publisher.config import settings

    enabled = getattr(settings, "trendradar_enabled", True)
    return TrendRadarAdapter(db, feature_flag_enabled=enabled)
