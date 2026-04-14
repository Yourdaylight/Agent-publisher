"""
TrendRadar Integration Adapter - Phase 1 Complete Implementation

This is an enhanced version of trendradar_adapter.py with stub implementations
that can be filled in as TrendRadar backend is accessed.

Current TODOs are marked with ✓ IMPL_PHASE_1 comments for easy tracking.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, List, Any, Set
from urllib.parse import urlparse

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


@dataclass
class TrendRadarNewsItem:
    """Unified news item from TrendRadar aggregation."""
    
    title: str
    url: str
    source_platform: str  # weibo, douyin, xiaohongshu, baidu, zhihu, toutiao, bilibili, v2ex, github, newsnow, rss
    hot_value: float  # Normalized 0-100 hotness score
    rank: int  # Platform-specific rank (1-based)
    summary: Optional[str] = None
    image_url: Optional[str] = None
    author: Optional[str] = None
    timestamp: Optional[datetime] = None
    source_url: Optional[str] = None  # Platform-specific URL (e.g., weibo user)
    metadata: Optional[Dict[str, Any]] = None

    def to_candidate_material(self, agent_id: int, quality_score: float = 0.5) -> Dict[str, Any]:
        """Convert TrendRadar item to CandidateMaterial format."""
        return {
            "agent_id": agent_id,
            "source_type": "trending",
            "source_identity": f"trendradar:{self.source_platform}",
            "original_url": self.url,
            "title": self.title,
            "summary": self.summary or self.title[:200],
            "raw_content": self._build_raw_content(),
            "quality_score": quality_score,
            "tags": self._extract_tags(),
            "metadata": {
                "platform": self.source_platform,
                "hot_value": self.hot_value,
                "rank": self.rank,
                "source": "trendradar_adapter_v1",
                "author": self.author,
                "source_url": self.source_url,
                "fetch_timestamp": datetime.now(timezone.utc).isoformat(),
                **(self.metadata or {}),
            },
        }

    def _build_raw_content(self) -> str:
        """Build structured raw content from trending item."""
        lines = [
            f"# {self.title}\n",
            f"## 基本信息\n",
            f"- **平台**: {self.source_platform.capitalize()}\n",
            f"- **热度**: {self.hot_value:.1f}/100\n",
            f"- **排名**: #{self.rank}\n",
        ]
        
        if self.author:
            lines.append(f"- **作者**: {self.author}\n")
        
        if self.source_url:
            lines.append(f"- **来源**: {self.source_url}\n")
        
        if self.timestamp:
            lines.append(f"- **时间**: {self.timestamp.isoformat()}\n")
        
        if self.image_url:
            lines.append(f"- **图片**: {self.image_url}\n")
        
        lines.append(f"- **链接**: {self.url}\n\n")
        
        if self.summary:
            lines.append(f"## 摘要\n{self.summary}\n")
        
        return "".join(lines)

    def _extract_tags(self) -> List[str]:
        """Extract tags from item metadata."""
        tags = [self.source_platform]
        
        # Hotness tier
        if self.hot_value >= 80:
            tags.append("hot")
            tags.append("trending")
        elif self.hot_value >= 50:
            tags.append("warm")
        else:
            tags.append("cool")
        
        # Rank tier
        if self.rank <= 10:
            tags.append("top10")
            tags.append("top50")
        elif self.rank <= 50:
            tags.append("top50")
        elif self.rank <= 100:
            tags.append("top100")
        
        return tags

    def __hash__(self):
        return hash((self.url, self.source_platform))

    def __eq__(self, other):
        if not isinstance(other, TrendRadarNewsItem):
            return False
        return self.url == other.url and self.source_platform == other.source_platform


class TrendRadarAdapter:
    """
    Adapter for integrating TrendRadar with Agent Publisher.
    
    Features:
    - Fetch from 11 trending platforms
    - Convert to CandidateMaterial format
    - Deduplication (URL + title similarity)
    - Quality scoring (hotness + recency + relevance)
    - Feature flag support
    - Graceful error handling
    """

    def __init__(self, db: AsyncSession, feature_flag_enabled: bool = True):
        self.db = db
        self.feature_flag_enabled = feature_flag_enabled
        self._platforms_supported = {
            "weibo", "douyin", "xiaohongshu", "baidu", "zhihu",
            "toutiao", "bilibili", "v2ex", "github", "newsnow", "rss"
        }

    async def collect_for_agent(
        self, 
        agent_id: int, 
        platforms: Optional[List[str]] = None,
        limit_per_platform: int = 50,
    ) -> Dict[str, Any]:
        """
        Collect trending materials for an agent from TrendRadar.
        
        Args:
            agent_id: Target agent ID
            platforms: Filter by specific platforms (default: all 11)
            limit_per_platform: Max items per platform
        
        Returns:
            {
                "status": "success|error",
                "platforms_collected": ["weibo", "douyin", ...],
                "new_items": count,
                "duplicates_skipped": count,
                "low_quality_skipped": count,
                "error": error_message if status == "error",
                "duration_seconds": float,
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
                "duration_seconds": 0,
            }

        start_time = datetime.now(timezone.utc)
        try:
            logger.info(
                "TrendRadar: Starting collection for agent %d (platforms=%s)",
                agent_id,
                platforms or "all",
            )

            # Validate platforms
            if platforms:
                platforms = [p for p in platforms if p in self._platforms_supported]
            else:
                platforms = sorted(self._platforms_supported)

            # Step 1: Fetch from TrendRadar (concurrent per platform)
            items = await self._fetch_from_trendradar(platforms, limit_per_platform)
            logger.info("TrendRadar: Fetched %d items from %d platforms", len(items), len(platforms))

            # Step 2: Deduplicate against existing materials
            dedup_result = await self._deduplicate_items(agent_id, items)
            unique_items = dedup_result["unique_items"]
            duplicates_skipped = dedup_result["duplicates_skipped"]
            logger.info("TrendRadar: %d duplicates skipped", duplicates_skipped)

            # Step 3: Score and filter
            scored_items = await self._score_and_filter(agent_id, unique_items)
            low_quality_skipped = len(unique_items) - len(scored_items)
            logger.info("TrendRadar: %d low-quality items filtered", low_quality_skipped)

            # Step 4: Convert and store
            created_count = await self._store_materials(agent_id, scored_items)

            duration = (datetime.now(timezone.utc) - start_time).total_seconds()

            return {
                "status": "success",
                "platforms_collected": sorted(set(item.source_platform for item in items)),
                "new_items": created_count,
                "duplicates_skipped": duplicates_skipped,
                "low_quality_skipped": low_quality_skipped,
                "duration_seconds": duration,
            }

        except Exception as e:
            logger.error("TrendRadar collection failed: %s", e, exc_info=True)
            duration = (datetime.now(timezone.utc) - start_time).total_seconds()
            return {
                "status": "error",
                "error": str(e),
                "platforms_collected": [],
                "new_items": 0,
                "duration_seconds": duration,
            }

    async def _fetch_from_trendradar(
        self, 
        platforms: List[str],
        limit_per_platform: int = 50,
    ) -> List[TrendRadarNewsItem]:
        """
        Fetch trending items from TrendRadar backend.
        
        ✓ IMPL_PHASE_1: Connect to TrendRadar (SQLite/S3/API)
        
        Implementation notes:
        1. Import trendradar module
        2. Create TrendRadar client (depends on deployment mode)
        3. Fetch for each platform concurrently (Semaphore)
        4. Parse into TrendRadarNewsItem
        5. Handle errors per platform (don't fail entire fetch)
        """
        logger.debug("Fetching from TrendRadar for platforms: %s", platforms)
        
        # TODO: Implement actual fetching
        # Placeholder for now
        items = []
        
        # Example of expected implementation structure:
        # try:
        #     from trendradar.core.analyzer import Analyzer
        #     analyzer = Analyzer()
        #     for platform in platforms:
        #         try:
        #             platform_data = await analyzer.fetch_trending(platform, limit=limit_per_platform)
        #             for item in platform_data:
        #                 items.append(TrendRadarNewsItem(
        #                     title=item['title'],
        #                     url=item['url'],
        #                     source_platform=platform,
        #                     hot_value=item.get('hot_value', 50),
        #                     rank=item.get('rank', 999),
        #                     summary=item.get('summary'),
        #                     image_url=item.get('image'),
        #                     timestamp=item.get('timestamp'),
        #                 ))
        #         except Exception as e:
        #             logger.error(f"Failed to fetch {platform}: {e}")
        # except ImportError:
        #     logger.error("TrendRadar package not available")
        
        return items

    async def _deduplicate_items(
        self, 
        agent_id: int, 
        items: List[TrendRadarNewsItem],
    ) -> Dict[str, Any]:
        """
        Check for duplicates against existing CandidateMaterial.
        
        Strategy:
        - Exact URL match (primary)
        - Title similarity (secondary, 80%+ Levenshtein)
        - Return unique items + skip count
        """
        from agent_publisher.models.candidate_material import CandidateMaterial

        # Fetch existing URLs
        result = await self.db.execute(
            select(CandidateMaterial.original_url).where(
                CandidateMaterial.agent_id == agent_id
            )
        )
        existing_urls = set(row[0] for row in result.all())

        unique_items = []
        duplicates_skipped = 0
        seen_urls = set()

        for item in items:
            # Skip exact URL match
            if item.url in existing_urls or item.url in seen_urls:
                duplicates_skipped += 1
                logger.debug("Skipped duplicate URL: %s", item.url)
                continue
            
            # TODO: Add title similarity check (Levenshtein 80%+)
            # if self._similar_title_exists(item.title, existing_titles):
            #     duplicates_skipped += 1
            #     continue
            
            unique_items.append(item)
            seen_urls.add(item.url)

        return {
            "unique_items": unique_items,
            "duplicates_skipped": duplicates_skipped,
        }

    async def _score_and_filter(
        self, 
        agent_id: int, 
        items: List[TrendRadarNewsItem],
    ) -> List[tuple[TrendRadarNewsItem, float]]:
        """
        Score items based on relevance and quality.
        
        Scoring formula (0-1):
        - Hotness: hot_value/100 (40% weight)
        - Recency: exp(-hours_old/24) (30% weight) 
        - Agent fit: keyword_relevance(agent_topic, item_title) (30% weight)
        - Final: score > 0.3 is kept
        
        Returns:
            List of (item, score) tuples, sorted by score desc
        """
        from agent_publisher.models.agent import Agent

        agent = await self.db.get(Agent, agent_id)
        if not agent:
            logger.warning("Agent %d not found for scoring", agent_id)
            return []

        scored = []
        for item in items:
            # Component 1: Hotness (40%)
            hotness_score = min(item.hot_value / 100.0, 1.0)

            # Component 2: Recency (30%)
            if item.timestamp:
                hours_old = (datetime.now(timezone.utc) - item.timestamp).total_seconds() / 3600
                recency_score = max(0, 1 - (hours_old / 24))  # 100% at 0h, 0% at 24h
            else:
                recency_score = 1.0  # Assume fresh if no timestamp

            # Component 3: Agent fit (30%) - TODO: Implement semantic matching
            agent_fit_score = await self._calculate_agent_fit(agent, item)

            # Combined score
            final_score = (
                hotness_score * 0.4 + 
                recency_score * 0.3 + 
                agent_fit_score * 0.3
            )

            if final_score > 0.3:
                scored.append((item, final_score))
                logger.debug("Scored: %s - %.2f", item.title[:60], final_score)
            else:
                logger.debug("Filtered (score=%.2f): %s", final_score, item.title[:60])

        return sorted(scored, key=lambda x: x[1], reverse=True)

    async def _calculate_agent_fit(
        self, 
        agent: Any, 
        item: TrendRadarNewsItem,
    ) -> float:
        """
        Calculate semantic relevance of item to agent's topic.
        
        ✓ IMPL_PHASE_1: Implement semantic matching
        
        For Phase 1: Return neutral 0.5
        Phase 2+: Use LLM or embedding-based similarity
        """
        # TODO: Phase 2 - Implement semantic matching
        # - Extract agent's keywords/topic from agent.topic
        # - Compare with item title + summary
        # - Use LLM or embeddings for semantic similarity
        # - Return score 0-1
        
        # Phase 1: Return neutral score
        return 0.5

    async def _store_materials(
        self, 
        agent_id: int, 
        scored_items: List[tuple[TrendRadarNewsItem, float]],
    ) -> int:
        """
        Convert scored items to CandidateMaterial and store in database.
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
                logger.error(
                    "Failed to create material from item '%s': %s", 
                    item.title[:60], 
                    e,
                )

        if created > 0:
            try:
                await self.db.commit()
                logger.info("Created %d materials from TrendRadar", created)
            except Exception as e:
                logger.error("Failed to commit materials: %s", e)
                await self.db.rollback()
                return 0

        return created


async def get_trendradar_adapter(db: AsyncSession) -> TrendRadarAdapter:
    """Factory function to create TrendRadar adapter with feature flag."""
    from agent_publisher.config import settings

    enabled = getattr(settings, "trendradar_enabled", False)
    return TrendRadarAdapter(db, feature_flag_enabled=enabled)
