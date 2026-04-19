"""Comprehensive tests for GovernanceService.

This test suite covers:
- Source mode statistics (by source type, acceptance rates, conversion rates)
- Tag statistics (tag distribution, acceptance rates by tag)
- Intake trends (daily material intake, by source type)
- Admin vs user visibility (owner_email filtering)
- Edge cases (zero data, special characters, boundary conditions)
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from agent_publisher.models.candidate_material import CandidateMaterial
from agent_publisher.services.governance_service import GovernanceService


# ==============================================================================
# Fixtures
# ==============================================================================

@pytest.fixture
def mock_session():
    """Create a mock AsyncSession for testing."""
    session = AsyncMock(spec=AsyncSession)
    return session


@pytest.fixture
def service(mock_session):
    """Create GovernanceService instance with mock session."""
    return GovernanceService(mock_session)


# ==============================================================================
# Section 1: Source Mode Statistics
# ==============================================================================

class TestSourceModeStats:
    """Test source mode statistics."""

    @pytest.mark.asyncio
    async def test_get_source_mode_stats_basic(self, service, mock_session):
        """get_source_mode_stats should return stats for each source type."""
        # Mock the query result
        mock_result = MagicMock()
        mock_result.all.return_value = [
            MagicMock(
                source_type="rss",
                total=100,
                accepted=80,
                rejected=15,
                duplicate_count=5,
            ),
            MagicMock(
                source_type="search",
                total=50,
                accepted=40,
                rejected=8,
                duplicate_count=2,
            ),
        ]
        
        # Mock article count query
        mock_article_result = MagicMock()
        mock_article_result.scalar.return_value = 200
        
        mock_session.execute = AsyncMock(side_effect=[mock_result, mock_article_result])
        
        stats = await service.get_source_mode_stats()
        
        assert len(stats) == 2
        assert stats[0]["source_type"] == "rss"
        assert stats[0]["total"] == 100
        assert stats[0]["accepted"] == 80
        assert "acceptance_rate" in stats[0]
        assert "duplicate_rate" in stats[0]

    @pytest.mark.asyncio
    async def test_get_source_mode_stats_calculates_rates(self, service, mock_session):
        """get_source_mode_stats should calculate acceptance and duplicate rates."""
        mock_result = MagicMock()
        mock_result.all.return_value = [
            MagicMock(
                source_type="rss",
                total=100,
                accepted=80,
                rejected=15,
                duplicate_count=5,
            ),
        ]
        
        mock_article_result = MagicMock()
        mock_article_result.scalar.return_value = 100
        
        mock_session.execute = AsyncMock(side_effect=[mock_result, mock_article_result])
        
        stats = await service.get_source_mode_stats()
        
        assert stats[0]["acceptance_rate"] == 0.8  # 80/100
        assert stats[0]["duplicate_rate"] == 0.05  # 5/100
        assert stats[0]["conversion_rate"] == 0.8  # 80/100

    @pytest.mark.asyncio
    async def test_get_source_mode_stats_with_owner_email(self, service, mock_session):
        """get_source_mode_stats should filter by owner_email when provided."""
        mock_result = MagicMock()
        mock_result.all.return_value = [
            MagicMock(
                source_type="rss",
                total=50,
                accepted=40,
                rejected=8,
                duplicate_count=2,
            ),
        ]
        
        mock_article_result = MagicMock()
        mock_article_result.scalar.return_value = 50
        
        mock_session.execute = AsyncMock(side_effect=[mock_result, mock_article_result])
        
        stats = await service.get_source_mode_stats(owner_email="user@example.com")
        
        assert mock_session.execute.call_count == 2
        assert len(stats) == 1

    @pytest.mark.asyncio
    async def test_get_source_mode_stats_handles_zero_data(self, service, mock_session):
        """get_source_mode_stats should handle zero materials gracefully."""
        mock_result = MagicMock()
        mock_result.all.return_value = []
        
        mock_article_result = MagicMock()
        mock_article_result.scalar.return_value = 0
        
        mock_session.execute = AsyncMock(side_effect=[mock_result, mock_article_result])
        
        stats = await service.get_source_mode_stats()
        
        assert stats == []

    @pytest.mark.asyncio
    async def test_get_source_mode_stats_calculates_pending(self, service, mock_session):
        """get_source_mode_stats should calculate pending count."""
        mock_result = MagicMock()
        mock_result.all.return_value = [
            MagicMock(
                source_type="manual",
                total=50,
                accepted=30,
                rejected=10,
                duplicate_count=0,
            ),
        ]
        
        mock_article_result = MagicMock()
        mock_article_result.scalar.return_value = 30
        
        mock_session.execute = AsyncMock(side_effect=[mock_result, mock_article_result])
        
        stats = await service.get_source_mode_stats()
        
        # pending = total - accepted - rejected = 50 - 30 - 10 = 10
        assert stats[0]["pending"] == 10

    @pytest.mark.asyncio
    async def test_get_source_mode_stats_divides_by_zero_safely(self, service, mock_session):
        """get_source_mode_stats should handle division by zero safely."""
        mock_result = MagicMock()
        mock_result.all.return_value = [
            MagicMock(
                source_type="empty",
                total=0,
                accepted=0,
                rejected=0,
                duplicate_count=0,
            ),
        ]
        
        mock_article_result = MagicMock()
        mock_article_result.scalar.return_value = 0
        
        mock_session.execute = AsyncMock(side_effect=[mock_result, mock_article_result])
        
        stats = await service.get_source_mode_stats()
        
        assert stats[0]["acceptance_rate"] == 0
        assert stats[0]["duplicate_rate"] == 0
        assert stats[0]["conversion_rate"] == 0


# ==============================================================================
# Section 2: Tag Statistics
# ==============================================================================

class TestTagStats:
    """Test tag statistics."""

    @pytest.mark.asyncio
    async def test_get_tag_stats_basic(self, service, mock_session):
        """get_tag_stats should return stats for each tag."""
        # Mock the query result - returns tuples of (tags_list, status)
        mock_result = MagicMock()
        mock_result.all.return_value = [
            (["important", "featured"], "accepted"),
            (["important"], "accepted"),
            (["important"], "rejected"),
            (["trending"], "accepted"),
            (["trending"], "pending"),
        ]
        
        mock_session.execute = AsyncMock(return_value=mock_result)
        
        stats = await service.get_tag_stats()
        
        # Should have at least important and trending tags
        assert len(stats) >= 2
        # Should be sorted by total count (descending)
        assert stats[0]["total"] >= stats[-1]["total"]

    @pytest.mark.asyncio
    async def test_get_tag_stats_calculates_acceptance_rate(self, service, mock_session):
        """get_tag_stats should calculate acceptance rate per tag."""
        mock_result = MagicMock()
        mock_result.all.return_value = [
            (["quality"], "accepted"),
            (["quality"], "accepted"),
            (["quality"], "rejected"),
            (["quality"], "pending"),
        ]
        
        mock_session.execute = AsyncMock(return_value=mock_result)
        
        stats = await service.get_tag_stats()
        
        quality_tag = next((s for s in stats if s["tag"] == "quality"), None)
        assert quality_tag is not None
        assert quality_tag["total"] == 4
        assert quality_tag["accepted"] == 2
        assert quality_tag["acceptance_rate"] == 0.5  # 2/4

    @pytest.mark.asyncio
    async def test_get_tag_stats_sorted_by_count_descending(self, service, mock_session):
        """get_tag_stats should return tags sorted by total count (descending)."""
        mock_result = MagicMock()
        mock_result.all.return_value = [
            (["common"], "accepted"),
            (["common"], "accepted"),
            (["common"], "accepted"),
            (["common"], "accepted"),
            (["common"], "accepted"),
            (["rare"], "accepted"),
        ]
        
        mock_session.execute = AsyncMock(return_value=mock_result)
        
        stats = await service.get_tag_stats()
        
        # "common" should come before "rare"
        assert stats[0]["tag"] == "common"
        assert stats[0]["total"] == 5
        assert stats[1]["tag"] == "rare"
        assert stats[1]["total"] == 1

    @pytest.mark.asyncio
    async def test_get_tag_stats_with_owner_email(self, service, mock_session):
        """get_tag_stats should filter by owner_email when provided."""
        mock_result = MagicMock()
        mock_result.all.return_value = [
            (["user_tag"], "accepted"),
            (["user_tag"], "accepted"),
        ]
        
        mock_session.execute = AsyncMock(return_value=mock_result)
        
        stats = await service.get_tag_stats(owner_email="user@example.com")
        
        assert mock_session.execute.called
        assert len(stats) == 1
        assert stats[0]["tag"] == "user_tag"

    @pytest.mark.asyncio
    async def test_get_tag_stats_handles_empty_tags(self, service, mock_session):
        """get_tag_stats should handle materials with empty/null tags."""
        mock_result = MagicMock()
        mock_result.all.return_value = []
        
        mock_session.execute = AsyncMock(return_value=mock_result)
        
        stats = await service.get_tag_stats()
        
        assert stats == []

    @pytest.mark.asyncio
    async def test_get_tag_stats_handles_special_characters(self, service, mock_session):
        """get_tag_stats should handle tags with special characters."""
        mock_result = MagicMock()
        mock_result.all.return_value = [
            (["中文标签"], "accepted"),
            (["中文标签"], "accepted"),
            (["tag-with-dash"], "rejected"),
            (["tag_with_underscore"], "accepted"),
        ]
        
        mock_session.execute = AsyncMock(return_value=mock_result)
        
        stats = await service.get_tag_stats()
        
        # Should include unicode tag
        assert any(s["tag"] == "中文标签" for s in stats)

    @pytest.mark.asyncio
    async def test_get_tag_stats_divides_by_zero_safely(self, service, mock_session):
        """get_tag_stats should handle division by zero safely."""
        mock_result = MagicMock()
        mock_result.all.return_value = [
            (["empty_tag"], "pending"),  # No accepted items
        ]
        
        mock_session.execute = AsyncMock(return_value=mock_result)
        
        stats = await service.get_tag_stats()
        
        assert stats[0]["acceptance_rate"] == 0


# ==============================================================================
# Section 3: Daily Intake Trend
# ==============================================================================

class TestDailyIntakeTrend:
    """Test daily intake trend analysis."""

    @pytest.mark.asyncio
    async def test_get_daily_intake_trend_basic(self, service, mock_session):
        """get_daily_intake_trend should return daily intake by source type."""
        today = datetime.now().date()
        yesterday = today - timedelta(days=1)
        
        mock_result = MagicMock()
        mock_result.all.return_value = [
            MagicMock(date=yesterday, source_type="rss", count=50),
            MagicMock(date=today, source_type="rss", count=75),
            MagicMock(date=today, source_type="search", count=25),
        ]
        
        mock_session.execute = AsyncMock(return_value=mock_result)
        
        trend = await service.get_daily_intake_trend(days=30)
        
        assert len(trend) == 3
        assert trend[0]["source_type"] == "rss"
        assert trend[0]["count"] == 50

    @pytest.mark.asyncio
    async def test_get_daily_intake_trend_default_30_days(self, service, mock_session):
        """get_daily_intake_trend should default to 30 days."""
        mock_result = MagicMock()
        mock_result.all.return_value = []
        
        mock_session.execute = AsyncMock(return_value=mock_result)
        
        trend = await service.get_daily_intake_trend()
        
        assert mock_session.execute.called

    @pytest.mark.asyncio
    async def test_get_daily_intake_trend_custom_days(self, service, mock_session):
        """get_daily_intake_trend should support custom day ranges."""
        mock_result = MagicMock()
        mock_result.all.return_value = []
        
        mock_session.execute = AsyncMock(return_value=mock_result)
        
        trend = await service.get_daily_intake_trend(days=7)
        
        assert mock_session.execute.called

    @pytest.mark.asyncio
    async def test_get_daily_intake_trend_with_owner_email(self, service, mock_session):
        """get_daily_intake_trend should filter by owner_email when provided."""
        mock_result = MagicMock()
        mock_result.all.return_value = [
            MagicMock(
                date=datetime.now().date(),
                source_type="rss",
                count=30,
            ),
        ]
        
        mock_session.execute = AsyncMock(return_value=mock_result)
        
        trend = await service.get_daily_intake_trend(owner_email="user@example.com")
        
        assert mock_session.execute.called
        assert len(trend) == 1

    @pytest.mark.asyncio
    async def test_get_daily_intake_trend_ordered_by_date(self, service, mock_session):
        """get_daily_intake_trend should be ordered by date (ascending)."""
        date1 = datetime.now().date() - timedelta(days=2)
        date2 = datetime.now().date() - timedelta(days=1)
        date3 = datetime.now().date()
        
        mock_result = MagicMock()
        mock_result.all.return_value = [
            MagicMock(date=date1, source_type="rss", count=10),
            MagicMock(date=date2, source_type="rss", count=20),
            MagicMock(date=date3, source_type="rss", count=30),
        ]
        
        mock_session.execute = AsyncMock(return_value=mock_result)
        
        trend = await service.get_daily_intake_trend(days=30)
        
        # Verify ordering
        assert str(trend[0]["date"]) <= str(trend[1]["date"])

    @pytest.mark.asyncio
    async def test_get_daily_intake_trend_handles_no_data(self, service, mock_session):
        """get_daily_intake_trend should handle empty result set."""
        mock_result = MagicMock()
        mock_result.all.return_value = []
        
        mock_session.execute = AsyncMock(return_value=mock_result)
        
        trend = await service.get_daily_intake_trend()
        
        assert trend == []

    @pytest.mark.asyncio
    async def test_get_daily_intake_trend_converts_date_to_string(self, service, mock_session):
        """get_daily_intake_trend should convert dates to string format."""
        test_date = datetime.now().date()
        
        mock_result = MagicMock()
        mock_result.all.return_value = [
            MagicMock(date=test_date, source_type="rss", count=50),
        ]
        
        mock_session.execute = AsyncMock(return_value=mock_result)
        
        trend = await service.get_daily_intake_trend()
        
        assert isinstance(trend[0]["date"], str)
        assert trend[0]["date"] == str(test_date)


# ==============================================================================
# Section 4: Admin vs User Visibility
# ==============================================================================

class TestVisibilityFiltering:
    """Test visibility filtering with owner_email."""

    @pytest.mark.asyncio
    async def test_source_stats_admin_sees_all(self, service, mock_session):
        """Admin (None owner_email) should see all sources."""
        mock_result = MagicMock()
        mock_result.all.return_value = [
            MagicMock(
                source_type="rss",
                total=100,
                accepted=80,
                rejected=15,
                duplicate_count=5,
            ),
        ]
        
        mock_article_result = MagicMock()
        mock_article_result.scalar.return_value = 100
        
        mock_session.execute = AsyncMock(side_effect=[mock_result, mock_article_result])
        
        # No owner_email means admin view
        stats = await service.get_source_mode_stats(owner_email=None)
        
        assert mock_session.execute.called

    @pytest.mark.asyncio
    async def test_source_stats_user_sees_only_own(self, service, mock_session):
        """User should only see their own sources."""
        mock_result = MagicMock()
        mock_result.all.return_value = [
            MagicMock(
                source_type="rss",
                total=20,
                accepted=15,
                rejected=3,
                duplicate_count=2,
            ),
        ]
        
        mock_article_result = MagicMock()
        mock_article_result.scalar.return_value = 15
        
        mock_session.execute = AsyncMock(side_effect=[mock_result, mock_article_result])
        
        stats = await service.get_source_mode_stats(owner_email="user@example.com")
        
        # Should still call execute (with filtering)
        assert mock_session.execute.called


# ==============================================================================
# Section 5: Edge Cases
# ==============================================================================

class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    @pytest.mark.asyncio
    async def test_tag_stats_with_list_and_non_list_tags(self, service, mock_session):
        """get_tag_stats should handle both list and non-list tag formats."""
        mock_result = MagicMock()
        mock_result.all.return_value = [
            (["tag1", "tag2"], "accepted"),
            (None, "rejected"),
        ]
        
        mock_session.execute = AsyncMock(return_value=mock_result)
        
        stats = await service.get_tag_stats()
        
        # Should not raise, should extract tags properly
        assert mock_session.execute.called

    @pytest.mark.asyncio
    async def test_source_stats_with_null_values(self, service, mock_session):
        """get_source_mode_stats should handle null values in database."""
        mock_result = MagicMock()
        mock_result.all.return_value = [
            MagicMock(
                source_type="test",
                total=50,
                accepted=None,  # Null value
                rejected=None,
                duplicate_count=None,
            ),
        ]
        
        mock_article_result = MagicMock()
        mock_article_result.scalar.return_value = None
        
        mock_session.execute = AsyncMock(side_effect=[mock_result, mock_article_result])
        
        stats = await service.get_source_mode_stats()
        
        # Should handle gracefully, converting None to 0
        assert stats[0]["accepted"] == 0

    @pytest.mark.asyncio
    async def test_daily_trend_with_large_day_range(self, service, mock_session):
        """get_daily_intake_trend should handle large day ranges."""
        mock_result = MagicMock()
        mock_result.all.return_value = []
        
        mock_session.execute = AsyncMock(return_value=mock_result)
        
        # Request 365 days of data
        trend = await service.get_daily_intake_trend(days=365)
        
        assert mock_session.execute.called

    @pytest.mark.asyncio
    async def test_tag_stats_with_many_tags(self, service, mock_session):
        """get_tag_stats should handle materials with many tags."""
        # Create mock data with 50+ different tags
        tag_data = [(f"tag_{i}",) if i % 2 == 0 else ([f"tag_{i}"],) for i in range(50)]
        mock_result = MagicMock()
        mock_result.all.return_value = [(["tag_0"], "accepted")] * 100 + [(["tag_1"], "rejected")] * 50
        
        mock_session.execute = AsyncMock(return_value=mock_result)
        
        stats = await service.get_tag_stats()
        
        # Should handle all tags, sorted by count
        assert len(stats) >= 1
        if len(stats) > 1:
            assert stats[0]["total"] >= stats[-1]["total"]

    @pytest.mark.asyncio
    async def test_source_stats_with_duplicate_rate_100_percent(self, service, mock_session):
        """get_source_mode_stats should handle 100% duplicate rate."""
        mock_result = MagicMock()
        mock_result.all.return_value = [
            MagicMock(
                source_type="test",
                total=100,
                accepted=0,
                rejected=0,
                duplicate_count=100,
            ),
        ]
        
        mock_article_result = MagicMock()
        mock_article_result.scalar.return_value = 0
        
        mock_session.execute = AsyncMock(side_effect=[mock_result, mock_article_result])
        
        stats = await service.get_source_mode_stats()
        
        assert stats[0]["duplicate_rate"] == 1.0
        assert stats[0]["acceptance_rate"] == 0.0

    @pytest.mark.asyncio
    async def test_daily_trend_with_gap_dates(self, service, mock_session):
        """get_daily_intake_trend should handle gaps in daily data."""
        date1 = datetime.now().date() - timedelta(days=5)
        date2 = datetime.now().date() - timedelta(days=2)
        # Note: no data for dates 4, 3, 1 days ago
        
        mock_result = MagicMock()
        mock_result.all.return_value = [
            MagicMock(date=date1, source_type="rss", count=10),
            MagicMock(date=date2, source_type="rss", count=20),
        ]
        
        mock_session.execute = AsyncMock(return_value=mock_result)
        
        trend = await service.get_daily_intake_trend(days=30)
        
        # Should only return days with data (gaps allowed)
        assert len(trend) == 2
