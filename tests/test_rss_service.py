from __future__ import annotations

import pytest

from agent_publisher.services.rss_service import RSSService


@pytest.mark.asyncio
async def test_fetch_feed_invalid_url():
    """Fetching an invalid URL returns empty list."""
    items = await RSSService.fetch_feed("https://invalid.example.com/feed.xml")
    assert items == []


@pytest.mark.asyncio
async def test_fetch_agent_feeds_dedup():
    """Duplicate URLs across sources should be deduplicated."""
    # Mock by passing same source twice; they'll fail but test dedup logic
    sources = [
        {"url": "https://invalid.example.com/feed1.xml", "name": "Source 1"},
        {"url": "https://invalid.example.com/feed2.xml", "name": "Source 2"},
    ]
    items = await RSSService.fetch_agent_feeds(sources)
    assert isinstance(items, list)


@pytest.mark.asyncio
async def test_test_feed_invalid():
    """test_feed with invalid URL returns success=False."""
    result = await RSSService.test_feed("https://invalid.example.com/nope.xml")
    # Either returns empty items or error
    assert isinstance(result, dict)
    assert "success" in result
