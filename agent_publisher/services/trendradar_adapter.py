"""
TrendRadar Integration Adapter

Bridges TrendRadar (trending platform aggregation) with Agent Publisher
(content generation). Uses TrendRadar as a Python library via trendradar_bridge.

Data Flow:
  TrendRadar DataFetcher/Storage
       │
       ▼ (trendradar_bridge)
  TrendRadarNewsItem
       │
       ▼ (this adapter: dedup → score → filter → store)
  CandidateMaterial
       │
       ▼
  LLM Generation → Article → Publish
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
    source_platform: str  # weibo, douyin, zhihu, baidu, toutiao, bilibili, etc.
    hot_value: float  # Normalized 0-100 hotness score
    rank: int  # Platform-specific rank (1-based)
    summary: Optional[str] = None
    image_url: Optional[str] = None
    timestamp: Optional[datetime] = None
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
                "source": "trendradar_adapter",
                "fetch_timestamp": datetime.now(timezone.utc).isoformat(),
                **(self.metadata or {}),
            },
        }

    def _build_raw_content(self) -> str:
        """Build structured raw content from trending item."""
        lines = [
            f"# {self.title}\n",
            "## 基本信息\n",
            f"- **平台**: {self.source_platform.capitalize()}\n",
            f"- **热度**: {self.hot_value:.1f}/100\n",
            f"- **排名**: #{self.rank}\n",
        ]
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
        if self.hot_value >= 80:
            tags.append("hot")
            tags.append("trending")
        elif self.hot_value >= 50:
            tags.append("warm")
        else:
            tags.append("cool")
        if self.rank <= 10:
            tags.append("top10")
        elif self.rank <= 50:
            tags.append("top50")
        return tags


class TrendRadarAdapter:
    """
    Adapter for integrating TrendRadar with Agent Publisher.

    Pipeline: fetch → deduplicate → score → filter → store
    """

    def __init__(self, db: AsyncSession, feature_flag_enabled: bool = True):
        self.db = db
        self.feature_flag_enabled = feature_flag_enabled

    async def collect_for_agent(
        self,
        agent_id: int | None,
        agent_name: str = "",
        platforms: Optional[List[str]] = None,
        filter_keywords: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Collect trending materials for an agent from TrendRadar.

        Args:
            agent_id: Target agent ID (None for global collection)
            agent_name: Agent name for logging
            platforms: Filter by specific platforms (default: all)
            filter_keywords: Keywords for agent-fit scoring

        Returns:
            {"status": "success|error", "new_items": int, ...}
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

        start_time = datetime.now(timezone.utc)
        try:
            from agent_publisher.config import settings

            # Determine platform list
            if not platforms:
                platforms = [
                    p.strip() for p in settings.trendradar_platforms.split(",") if p.strip()
                ]

            logger.info(
                "TrendRadar: collecting for agent=%s platforms=%s",
                agent_name or agent_id,
                platforms,
            )

            # Step 1: Fetch via bridge
            from agent_publisher.services.trendradar_bridge import (
                fetch_trending_via_trendradar,
            )

            items = await fetch_trending_via_trendradar(
                platform_ids=platforms,
                trendradar_data_dir=settings.trendradar_storage_path,
            )
            logger.info("TrendRadar: fetched %d items", len(items))

            if not items:
                duration = (datetime.now(timezone.utc) - start_time).total_seconds()
                return {
                    "status": "success",
                    "platforms_collected": platforms,
                    "new_items": 0,
                    "duplicates_skipped": 0,
                    "low_quality_skipped": 0,
                    "duration_seconds": duration,
                }

            # Step 2: Deduplicate
            dedup_result = await self._deduplicate_items(agent_id, items)
            unique_items = dedup_result["unique_items"]
            duplicates_skipped = dedup_result["duplicates_skipped"]

            # Step 3: Score and filter
            scored_items = self._score_and_filter(unique_items, filter_keywords)
            low_quality_skipped = len(unique_items) - len(scored_items)

            # Step 4: Store
            created_count = await self._store_materials(agent_id, scored_items)

            duration = (datetime.now(timezone.utc) - start_time).total_seconds()
            return {
                "status": "success",
                "platforms_collected": sorted(set(i.source_platform for i in items)),
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

    async def _deduplicate_items(
        self,
        agent_id: int | None,
        items: List[TrendRadarNewsItem],
    ) -> Dict[str, Any]:
        """Check for duplicates against existing CandidateMaterial (by URL)."""
        from agent_publisher.models.candidate_material import CandidateMaterial

        existing_urls: set[str] = set()
        if agent_id is not None:
            result = await self.db.execute(
                select(CandidateMaterial.original_url).where(CandidateMaterial.agent_id == agent_id)
            )
            existing_urls = set(row[0] for row in result.all())
        else:
            # Global collection: check all recent URLs
            result = await self.db.execute(
                select(CandidateMaterial.original_url).where(
                    CandidateMaterial.source_type == "trending"
                )
            )
            existing_urls = set(row[0] for row in result.all())

        unique_items: list[TrendRadarNewsItem] = []
        seen_urls: set[str] = set()
        duplicates_skipped = 0

        for item in items:
            if item.url in existing_urls or item.url in seen_urls:
                duplicates_skipped += 1
                continue
            unique_items.append(item)
            seen_urls.add(item.url)

        return {
            "unique_items": unique_items,
            "duplicates_skipped": duplicates_skipped,
        }

    def _score_and_filter(
        self,
        items: List[TrendRadarNewsItem],
        filter_keywords: Optional[List[str]] = None,
    ) -> List[tuple[TrendRadarNewsItem, float]]:
        """Score items and filter by quality threshold (0.3).

        Scoring formula:
        - Hotness: hot_value/100 (40% weight)
        - Rank bonus: exp(-rank/50) (30% weight)
        - Agent fit: keyword match (30% weight)
        """
        scored: list[tuple[TrendRadarNewsItem, float]] = []

        for item in items:
            hotness_score = min(item.hot_value / 100.0, 1.0)
            rank_score = max(0.0, min(1.0, 1.0 - (item.rank / 100.0)))
            agent_fit = self._calculate_agent_fit(item, filter_keywords)

            final_score = hotness_score * 0.4 + rank_score * 0.3 + agent_fit * 0.3

            if final_score > 0.3:
                scored.append((item, final_score))

        return sorted(scored, key=lambda x: x[1], reverse=True)

    @staticmethod
    def _calculate_agent_fit(
        item: TrendRadarNewsItem,
        filter_keywords: Optional[List[str]] = None,
    ) -> float:
        """Calculate keyword-based relevance score.

        Returns:
            1.0 if any keyword matches, 0.5 if no keywords configured, 0.0 if none match.
        """
        if not filter_keywords:
            return 0.5  # Neutral when no keywords

        title_lower = item.title.lower()
        for kw in filter_keywords:
            if kw.lower() in title_lower:
                return 1.0
        return 0.0

    async def _store_materials(
        self,
        agent_id: int | None,
        scored_items: List[tuple[TrendRadarNewsItem, float]],
    ) -> int:
        """Convert scored items to CandidateMaterial and store."""
        from agent_publisher.models.candidate_material import CandidateMaterial

        created = 0
        for item, score in scored_items:
            try:
                material_data = item.to_candidate_material(
                    agent_id=agent_id or 0, quality_score=score
                )
                # Map 'metadata' key to 'extra_metadata' column
                material = CandidateMaterial(
                    agent_id=material_data.get("agent_id"),
                    source_type=material_data["source_type"],
                    source_identity=material_data["source_identity"],
                    original_url=material_data["original_url"],
                    title=material_data["title"],
                    summary=material_data["summary"],
                    raw_content=material_data["raw_content"],
                    quality_score=material_data["quality_score"],
                    tags=material_data["tags"],
                    extra_metadata=material_data["metadata"],
                )
                self.db.add(material)
                created += 1
            except Exception as e:
                logger.error(
                    "Failed to create material from '%s': %s",
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

    enabled = getattr(settings, "trendradar_enabled", True)
    return TrendRadarAdapter(db, feature_flag_enabled=enabled)
