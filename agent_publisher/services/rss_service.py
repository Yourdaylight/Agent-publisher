from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass

import feedparser
import httpx

logger = logging.getLogger(__name__)


@dataclass
class NewsItem:
    title: str
    summary: str
    link: str
    published_date: str
    source_name: str
    url_hash: str


class RSSService:
    @staticmethod
    async def fetch_feed(url: str, source_name: str = "") -> list[NewsItem]:
        """Fetch and parse a single RSS feed."""
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.get(url)
                resp.raise_for_status()
        except httpx.HTTPError as e:
            logger.error("Failed to fetch RSS %s: %s", url, e)
            return []

        feed = feedparser.parse(resp.text)
        items = []
        for entry in feed.entries:
            published = ""
            if hasattr(entry, "published"):
                published = entry.published
            elif hasattr(entry, "updated"):
                published = entry.updated

            url_hash = hashlib.md5(entry.link.encode()).hexdigest()
            items.append(
                NewsItem(
                    title=entry.get("title", ""),
                    summary=entry.get("summary", ""),
                    link=entry.get("link", ""),
                    published_date=published,
                    source_name=source_name or feed.feed.get("title", ""),
                    url_hash=url_hash,
                )
            )
        return items

    @staticmethod
    async def fetch_agent_feeds(rss_sources: list[dict]) -> list[NewsItem]:
        """Fetch all RSS sources for an agent and deduplicate."""
        all_items: list[NewsItem] = []
        seen_hashes: set[str] = set()

        for source in rss_sources:
            url = source.get("url", "")
            name = source.get("name", "")
            if not url:
                continue
            items = await RSSService.fetch_feed(url, name)
            for item in items:
                if item.url_hash not in seen_hashes:
                    seen_hashes.add(item.url_hash)
                    all_items.append(item)

        # Sort by date descending (newest first)
        all_items.sort(key=lambda x: x.published_date, reverse=True)
        return all_items

    @staticmethod
    async def test_feed(url: str) -> dict:
        """Test if an RSS feed URL is accessible and valid."""
        try:
            items = await RSSService.fetch_feed(url)
            return {
                "success": True,
                "item_count": len(items),
                "sample_titles": [item.title for item in items[:3]],
            }
        except Exception as e:
            return {"success": False, "error": str(e)}
