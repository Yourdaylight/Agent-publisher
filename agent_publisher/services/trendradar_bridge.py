"""Bridge: TrendRadar data → Agent-Publisher TrendRadarNewsItem format.

Uses TrendRadar as a Python library (sync) wrapped in asyncio.to_thread().
Two modes:
  A. Storage read: read from TrendRadar's local SQLite if trendradar_data_dir is set
  B. Live fetch: call DataFetcher.crawl_websites() for fresh data (fallback or default)
"""
from __future__ import annotations

import asyncio
import logging
import math
from typing import Any

from trendradar.crawler.fetcher import DataFetcher
from trendradar.storage.manager import StorageManager
from trendradar.storage.base import convert_crawl_results_to_news_data

from agent_publisher.services.trendradar_adapter import TrendRadarNewsItem

logger = logging.getLogger(__name__)


# ── Single-item conversion ──────────────────────────────────────────


def newsitem_to_trendradar_newsitem(
    item: Any,
    source_id: str,
) -> TrendRadarNewsItem:
    """Convert a TrendRadar NewsItem (or duck-typed equivalent) to TrendRadarNewsItem.

    Hot-value heuristic:
      - If the item has appeared on multiple crawls (count > 1), use count * 10 (capped at 100)
      - Otherwise, derive from rank: higher rank → higher hot_value
    """
    count = getattr(item, "count", 1) or 1
    rank = getattr(item, "rank", 99) or 99

    if count > 1:
        hot_value = min(count * 10.0, 100.0)
    else:
        # Rank-based: rank=1 → 100, rank=50 → ~8, rank=100 → ~0.7
        hot_value = max(0.0, min(100.0, 100.0 * math.exp(-0.05 * (rank - 1))))

    return TrendRadarNewsItem(
        title=getattr(item, "title", ""),
        url=getattr(item, "url", ""),
        source_platform=source_id,
        hot_value=hot_value,
        rank=rank,
        summary=None,
        image_url=None,
        timestamp=None,
        metadata={
            "mobile_url": getattr(item, "mobile_url", ""),
            "ranks": getattr(item, "ranks", [rank]),
            "first_time": getattr(item, "first_time", ""),
            "last_time": getattr(item, "last_time", ""),
            "count": count,
        },
    )


# ── Batch conversion ────────────────────────────────────────────────


def newsdata_to_trendradar_newsitems(
    newsdata: Any | None,
    platforms: list[str] | None = None,
) -> list[TrendRadarNewsItem]:
    """Convert a TrendRadar NewsData object to a flat list of TrendRadarNewsItem.

    Also computes cross-platform count: if the same title appears across
    multiple source_ids, each item gets cross_platform_count and all_platforms
    in its metadata (needed by frontend Trending.vue).

    Args:
        newsdata: A TrendRadar NewsData (or duck-typed equivalent with .items dict).
        platforms: Optional platform filter. None = all platforms.

    Returns:
        Flat list of TrendRadarNewsItem.
    """
    if newsdata is None:
        return []

    items_dict = getattr(newsdata, "items", {})
    if not items_dict:
        return []

    id_to_name = getattr(newsdata, "id_to_name", {})

    # Phase 1: convert all items
    result: list[TrendRadarNewsItem] = []
    for source_id, news_list in items_dict.items():
        if platforms and source_id not in platforms:
            continue
        platform_name = id_to_name.get(source_id, source_id)
        for item in news_list:
            tr_item = newsitem_to_trendradar_newsitem(item, source_id)
            # Add platform_name from id_to_name mapping
            tr_item.metadata["platform_name"] = platform_name
            result.append(tr_item)

    # Phase 2: compute cross-platform counts by title
    title_platforms: dict[str, set[str]] = {}
    for item in result:
        key = item.title.strip().lower()
        title_platforms.setdefault(key, set()).add(item.source_platform)

    for item in result:
        key = item.title.strip().lower()
        cross_platforms = title_platforms.get(key, {item.source_platform})
        item.metadata["cross_platform_count"] = len(cross_platforms)
        item.metadata["all_platforms"] = sorted(cross_platforms)

    return result


# ── Async fetch entry point ─────────────────────────────────────────


def _live_fetch_sync(platform_ids: list[str]) -> list[TrendRadarNewsItem]:
    """Synchronous live fetch using TrendRadar's DataFetcher."""
    fetcher = DataFetcher()
    results, id_to_name, failed_ids = fetcher.crawl_websites(platform_ids)

    items: list[TrendRadarNewsItem] = []
    for source_id, titles_data in results.items():
        platform_name = id_to_name.get(source_id, source_id)
        for title, data in titles_data.items():
            ranks = data.get("ranks", [])
            rank = ranks[0] if ranks else 99
            url = data.get("url", "")
            mobile_url = data.get("mobileUrl", "")

            # count = number of ranks (how many times it appeared in one crawl)
            count = len(ranks) if ranks else 1
            hot_value = max(0.0, min(100.0, 100.0 * math.exp(-0.05 * (rank - 1))))

            items.append(TrendRadarNewsItem(
                title=title,
                url=url,
                source_platform=source_id,
                hot_value=hot_value,
                rank=rank,
                summary=None,
                image_url=None,
                timestamp=None,
                metadata={
                    "mobile_url": mobile_url,
                    "ranks": ranks,
                    "platform_name": platform_name,
                    "source": "trendradar_live_fetch",
                },
            ))

    if failed_ids:
        logger.warning("TrendRadar live fetch failed for platforms: %s", failed_ids)

    # Compute cross-platform counts
    title_platforms: dict[str, set[str]] = {}
    for item in items:
        key = item.title.strip().lower()
        title_platforms.setdefault(key, set()).add(item.source_platform)

    for item in items:
        key = item.title.strip().lower()
        cross_platforms = title_platforms.get(key, {item.source_platform})
        item.metadata["cross_platform_count"] = len(cross_platforms)
        item.metadata["all_platforms"] = sorted(cross_platforms)

    return items


def _storage_read_sync(
    platform_ids: list[str],
    data_dir: str,
) -> list[TrendRadarNewsItem] | None:
    """Synchronous read from TrendRadar's local SQLite storage.

    Returns None if no data found (caller should fall back to live fetch).
    """
    try:
        sm = StorageManager(
            backend_type="local",
            data_dir=data_dir,
            enable_txt=False,
            enable_html=False,
        )
        newsdata = sm.get_today_all_data()
        if newsdata is None:
            return None

        items = newsdata_to_trendradar_newsitems(newsdata, platforms=platform_ids or None)
        logger.info(
            "TrendRadar storage read: %d items from %s",
            len(items),
            data_dir,
        )
        return items
    except Exception as e:
        logger.warning("TrendRadar storage read failed: %s", e)
        return None


async def fetch_trending_via_trendradar(
    platform_ids: list[str],
    trendradar_data_dir: str = "",
) -> list[TrendRadarNewsItem]:
    """Fetch trending items using TrendRadar.

    Strategy:
      1. If trendradar_data_dir is set, try reading from TrendRadar's local SQLite
      2. If no data found or no data_dir, do a live crawl via DataFetcher
      3. Convert all results to TrendRadarNewsItem

    Args:
        platform_ids: List of platform IDs (e.g. ["weibo", "zhihu", "toutiao"])
        trendradar_data_dir: Path to TrendRadar's output/ directory (optional)

    Returns:
        List of TrendRadarNewsItem
    """
    if not platform_ids:
        return []

    # Try storage read first (if configured)
    if trendradar_data_dir:
        items = await asyncio.to_thread(
            _storage_read_sync, platform_ids, trendradar_data_dir
        )
        if items is not None:
            return items
        logger.info("TrendRadar storage empty, falling back to live fetch")

    # Live fetch
    items = await asyncio.to_thread(_live_fetch_sync, platform_ids)
    logger.info("TrendRadar live fetch: %d items from %d platforms", len(items), len(platform_ids))
    return items
