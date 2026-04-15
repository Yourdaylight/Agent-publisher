"""Tests for TrendRadar bridge — converts TrendRadar data models to Agent-Publisher format."""
from __future__ import annotations

import pytest
from datetime import datetime, timezone
from unittest.mock import patch, MagicMock

from agent_publisher.services.trendradar_bridge import (
    newsitem_to_trendradar_newsitem,
    newsdata_to_trendradar_newsitems,
    fetch_trending_via_trendradar,
)
from agent_publisher.services.trendradar_adapter import TrendRadarNewsItem


def _make_newsitem(
    title="Test Title",
    source_id="weibo",
    rank=1,
    url="https://example.com/news",
    mobile_url="",
    crawl_time="10:30",
    count=3,
    ranks=None,
    first_time="09:00",
    last_time="10:30",
):
    """Create a TrendRadar NewsItem-compatible object (duck typing)."""
    from types import SimpleNamespace

    return SimpleNamespace(
        title=title,
        source_id=source_id,
        source_name="",
        rank=rank,
        url=url,
        mobile_url=mobile_url,
        crawl_time=crawl_time,
        count=count,
        ranks=ranks or [rank],
        first_time=first_time,
        last_time=last_time,
        rank_timeline=[],
    )


def _make_newsdata(items_by_platform: dict, date="2026-04-14", crawl_time="10:30"):
    """Create a TrendRadar NewsData-compatible object (duck typing)."""
    from types import SimpleNamespace

    id_to_name = {pid: pid.upper() for pid in items_by_platform}
    return SimpleNamespace(
        date=date,
        crawl_time=crawl_time,
        items=items_by_platform,
        id_to_name=id_to_name,
        failed_ids=[],
    )


# ── Unit tests: single item conversion ──


class TestNewsItemConversion:
    def test_basic_conversion(self):
        """Converts a NewsItem to TrendRadarNewsItem with correct fields."""
        item = _make_newsitem(title="AI突破", source_id="weibo", rank=3, url="https://weibo.com/1")
        result = newsitem_to_trendradar_newsitem(item, source_id="weibo")

        assert isinstance(result, TrendRadarNewsItem)
        assert result.title == "AI突破"
        assert result.source_platform == "weibo"
        assert result.rank == 3
        assert result.url == "https://weibo.com/1"

    def test_hot_value_from_count(self):
        """hot_value is derived from appearance count, capped at 100."""
        item = _make_newsitem(count=5)
        result = newsitem_to_trendradar_newsitem(item, source_id="weibo")
        assert result.hot_value == 50.0  # 5 * 10

    def test_hot_value_capped(self):
        """hot_value is capped at 100."""
        item = _make_newsitem(count=20)
        result = newsitem_to_trendradar_newsitem(item, source_id="weibo")
        assert result.hot_value == 100.0

    def test_hot_value_minimum_rank_based(self):
        """Items with count=1 get a rank-based hot_value."""
        item = _make_newsitem(count=1, rank=1)
        result = newsitem_to_trendradar_newsitem(item, source_id="weibo")
        # rank=1 → high hot_value
        assert result.hot_value > 50

    def test_metadata_includes_extra_fields(self):
        """Metadata stores mobile_url, ranks, first_time, last_time."""
        item = _make_newsitem(
            mobile_url="https://m.weibo.com/1",
            ranks=[1, 3, 5],
            first_time="08:00",
            last_time="12:00",
        )
        result = newsitem_to_trendradar_newsitem(item, source_id="weibo")

        assert result.metadata["mobile_url"] == "https://m.weibo.com/1"
        assert result.metadata["ranks"] == [1, 3, 5]
        assert result.metadata["first_time"] == "08:00"
        assert result.metadata["last_time"] == "12:00"

    def test_empty_title_still_converts(self):
        """Items with empty titles convert without error."""
        item = _make_newsitem(title="")
        result = newsitem_to_trendradar_newsitem(item, source_id="weibo")
        assert result.title == ""


# ── Batch conversion tests ──


class TestNewsDataConversion:
    def test_converts_multiple_platforms(self):
        """Converts NewsData with multiple platforms into flat list."""
        items = {
            "weibo": [_make_newsitem(title="微博热搜1"), _make_newsitem(title="微博热搜2")],
            "zhihu": [_make_newsitem(title="知乎热榜1")],
        }
        newsdata = _make_newsdata(items)
        result = newsdata_to_trendradar_newsitems(newsdata)

        assert len(result) == 3
        platforms = {r.source_platform for r in result}
        assert platforms == {"weibo", "zhihu"}

    def test_empty_newsdata_returns_empty(self):
        """Empty NewsData returns empty list."""
        newsdata = _make_newsdata({})
        result = newsdata_to_trendradar_newsitems(newsdata)
        assert result == []

    def test_none_newsdata_returns_empty(self):
        """None NewsData returns empty list."""
        result = newsdata_to_trendradar_newsitems(None)
        assert result == []

    def test_platform_filtering(self):
        """Only returns items from requested platforms."""
        items = {
            "weibo": [_make_newsitem(title="微博")],
            "zhihu": [_make_newsitem(title="知乎")],
            "bilibili": [_make_newsitem(title="B站")],
        }
        newsdata = _make_newsdata(items)
        result = newsdata_to_trendradar_newsitems(newsdata, platforms=["weibo", "bilibili"])

        assert len(result) == 2
        platforms = {r.source_platform for r in result}
        assert platforms == {"weibo", "bilibili"}

    def test_no_filter_returns_all(self):
        """With no platform filter, returns all platforms."""
        items = {
            "weibo": [_make_newsitem(title="1")],
            "zhihu": [_make_newsitem(title="2")],
        }
        newsdata = _make_newsdata(items)
        result = newsdata_to_trendradar_newsitems(newsdata, platforms=None)
        assert len(result) == 2

    def test_cross_platform_count_computed(self):
        """Same title on 3 platforms → cross_platform_count=3 on each."""
        items = {
            "weibo": [_make_newsitem(title="AI突破", url="https://weibo.com/1")],
            "zhihu": [_make_newsitem(title="AI突破", url="https://zhihu.com/1")],
            "baidu": [_make_newsitem(title="AI突破", url="https://baidu.com/1")],
        }
        newsdata = _make_newsdata(items)
        result = newsdata_to_trendradar_newsitems(newsdata)

        assert len(result) == 3
        for item in result:
            assert item.metadata["cross_platform_count"] == 3
            assert len(item.metadata["all_platforms"]) == 3

    def test_cross_platform_count_single(self):
        """Unique title on 1 platform → cross_platform_count=1."""
        items = {
            "weibo": [_make_newsitem(title="独家新闻", url="https://weibo.com/1")],
            "zhihu": [_make_newsitem(title="完全不同", url="https://zhihu.com/1")],
        }
        newsdata = _make_newsdata(items)
        result = newsdata_to_trendradar_newsitems(newsdata)

        for item in result:
            assert item.metadata["cross_platform_count"] == 1

    def test_platform_name_in_metadata(self):
        """Items include platform_name from id_to_name mapping."""
        items = {
            "weibo": [_make_newsitem(title="微博新闻")],
        }
        newsdata = _make_newsdata(items)
        # Override id_to_name with Chinese names
        newsdata.id_to_name = {"weibo": "微博热搜"}
        result = newsdata_to_trendradar_newsitems(newsdata)

        assert len(result) == 1
        assert result[0].metadata["platform_name"] == "微博热搜"


# ── Integration test: fetch_trending_via_trendradar ──


class TestFetchTrendingViaTrendRadar:
    @pytest.mark.asyncio
    async def test_live_fetch_mode(self):
        """When no storage path, uses DataFetcher live crawl."""
        mock_results = {
            "weibo": {
                "AI突破": {"ranks": [1], "url": "https://weibo.com/1", "mobileUrl": ""},
                "热搜第二": {"ranks": [2], "url": "https://weibo.com/2", "mobileUrl": ""},
            }
        }
        mock_id_to_name = {"weibo": "微博热搜"}
        mock_failed = []

        with patch("agent_publisher.services.trendradar_bridge.DataFetcher") as MockFetcher:
            mock_instance = MagicMock()
            mock_instance.crawl_websites.return_value = (
                mock_results,
                mock_id_to_name,
                mock_failed,
            )
            MockFetcher.return_value = mock_instance

            items = await fetch_trending_via_trendradar(["weibo"])

            assert len(items) == 2
            assert items[0].source_platform == "weibo"
            mock_instance.crawl_websites.assert_called_once()

    @pytest.mark.asyncio
    async def test_storage_read_mode(self):
        """When storage path is set and data exists, reads from storage."""
        mock_newsdata = _make_newsdata({
            "zhihu": [_make_newsitem(title="知乎热点", source_id="zhihu")],
        })

        with patch("agent_publisher.services.trendradar_bridge.StorageManager") as MockSM:
            mock_sm = MagicMock()
            mock_sm.get_today_all_data.return_value = mock_newsdata
            MockSM.return_value = mock_sm

            items = await fetch_trending_via_trendradar(
                ["zhihu"], trendradar_data_dir="/tmp/trendradar/output"
            )

            assert len(items) == 1
            assert items[0].title == "知乎热点"
            MockSM.assert_called_once()

    @pytest.mark.asyncio
    async def test_storage_empty_falls_back_to_live(self):
        """When storage has no data, falls back to live fetch."""
        with patch("agent_publisher.services.trendradar_bridge.StorageManager") as MockSM:
            mock_sm = MagicMock()
            mock_sm.get_today_all_data.return_value = None
            MockSM.return_value = mock_sm

            with patch("agent_publisher.services.trendradar_bridge.DataFetcher") as MockFetcher:
                mock_instance = MagicMock()
                mock_instance.crawl_websites.return_value = ({}, {}, [])
                MockFetcher.return_value = mock_instance

                items = await fetch_trending_via_trendradar(
                    ["weibo"], trendradar_data_dir="/tmp/trendradar/output"
                )

                assert items == []
                mock_instance.crawl_websites.assert_called_once()

    @pytest.mark.asyncio
    async def test_empty_platform_list(self):
        """Empty platform list returns empty result."""
        items = await fetch_trending_via_trendradar([])
        assert items == []
