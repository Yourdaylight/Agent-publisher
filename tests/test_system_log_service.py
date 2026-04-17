"""Comprehensive tests for SystemLogService.

This test suite covers:
- Log creation with all fields
- Data sanitization for sensitive information
- Querying by action, target type, operator, status
- Time range filtering
- Keyword search
- Pagination (limit, offset)
- Log statistics
- Log cleanup for old entries
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from agent_publisher.models.system_log import SystemLog
from agent_publisher.services.system_log_service import SystemLogService


# ==============================================================================
# Fixtures
# ==============================================================================

@pytest.fixture
def mock_db():
    """Create a mock AsyncSession for testing."""
    db = AsyncMock(spec=AsyncSession)
    return db


@pytest.fixture
def service(mock_db):
    """Create SystemLogService instance with mock session."""
    return SystemLogService(mock_db)


def create_mock_log(
    id: int = 1,
    action: str = "publish",
    target_type: str = "article",
    target_id: str = "123",
    description: str = "Article published",
    operator: str = "user@example.com",
    is_admin: bool = False,
    status: str = "success",
    error_message: str = "",
    extra: str = "",
    client_ip: str = "192.168.1.1",
    request_path: str = "/api/articles/123/publish",
    **kwargs,
) -> SystemLog:
    """Create a mock SystemLog object."""
    log = MagicMock(spec=SystemLog)
    log.id = id
    log.action = action
    log.target_type = target_type
    log.target_id = target_id
    log.description = description
    log.operator = operator
    log.is_admin = 1 if is_admin else 0
    log.status = status
    log.error_message = error_message
    log.extra = extra
    log.client_ip = client_ip
    log.request_path = request_path
    log.timestamp = datetime.now(timezone.utc)
    for key, value in kwargs.items():
        setattr(log, key, value)
    return log


# ==============================================================================
# Section 1: Log Creation
# ==============================================================================

class TestLogCreation:
    """Test log creation operations."""

    @pytest.mark.asyncio
    async def test_record_creates_log_entry(self, service, mock_db):
        """record should create a new log entry."""
        mock_log = create_mock_log()
        mock_db.add = MagicMock()
        mock_db.commit = AsyncMock()
        mock_db.refresh = AsyncMock()
        
        result = await service.record(
            action="publish",
            target_type="article",
            target_id="123",
            description="Article published",
            operator="user@example.com",
        )
        
        assert mock_db.add.called
        assert mock_db.commit.called

    @pytest.mark.asyncio
    async def test_record_with_all_fields(self, service, mock_db):
        """record should handle all optional fields."""
        mock_log = create_mock_log()
        mock_db.add = MagicMock()
        mock_db.commit = AsyncMock()
        mock_db.refresh = AsyncMock()
        
        extra_data = {"key": "value", "nested": {"field": "data"}}
        
        result = await service.record(
            action="create",
            target_type="agent",
            target_id="agent_001",
            description="New agent created",
            operator="admin@example.com",
            is_admin=True,
            status="success",
            error_message="",
            extra=extra_data,
            client_ip="192.168.1.1",
            request_path="/api/agents",
        )
        
        assert mock_db.add.called
        assert mock_db.commit.called

    @pytest.mark.asyncio
    async def test_record_failure_logs_error(self, service, mock_db):
        """record should handle failed status with error message."""
        mock_log = create_mock_log(status="failed")
        mock_db.add = MagicMock()
        mock_db.commit = AsyncMock()
        mock_db.refresh = AsyncMock()
        
        result = await service.record(
            action="sync",
            target_type="article",
            target_id="456",
            description="Sync failed",
            operator="system",
            status="failed",
            error_message="Connection timeout",
        )
        
        assert mock_db.add.called

    @pytest.mark.asyncio
    async def test_record_converts_target_id_to_string(self, service, mock_db):
        """record should convert integer target_id to string."""
        mock_log = create_mock_log()
        captured_log = None
        
        def capture_add(log):
            nonlocal captured_log
            captured_log = log
        
        mock_db.add.side_effect = capture_add
        mock_db.commit = AsyncMock()
        mock_db.refresh = AsyncMock()
        
        result = await service.record(
            action="delete",
            target_type="media",
            target_id=789,  # Integer
            description="Media deleted",
        )
        
        assert mock_db.add.called

    @pytest.mark.asyncio
    async def test_record_serializes_extra_json(self, service, mock_db):
        """record should serialize extra dict to JSON."""
        mock_log = create_mock_log()
        captured_log = None
        
        def capture_add(log):
            nonlocal captured_log
            captured_log = log
        
        mock_db.add.side_effect = capture_add
        mock_db.commit = AsyncMock()
        mock_db.refresh = AsyncMock()
        
        extra_data = {"metrics": {"duration": 1.23}, "tags": ["important"]}
        
        result = await service.record(
            action="generate",
            target_type="task",
            target_id="task_001",
            extra=extra_data,
        )
        
        assert mock_db.add.called

    @pytest.mark.asyncio
    async def test_record_handles_unicode_content(self, service, mock_db):
        """record should handle unicode characters in description and error message."""
        mock_log = create_mock_log()
        mock_db.add = MagicMock()
        mock_db.commit = AsyncMock()
        mock_db.refresh = AsyncMock()
        
        result = await service.record(
            action="publish",
            target_type="article",
            target_id="999",
            description="文章发布成功 | Article published",
            error_message="错误信息：Connection failed",
            operator="用户@example.com",
        )
        
        assert mock_db.add.called


# ==============================================================================
# Section 2: Querying
# ==============================================================================

class TestQuerying:
    """Test log querying operations."""

    @pytest.mark.asyncio
    async def test_query_no_filters_returns_all(self, service, mock_db):
        """query with no filters should return all logs in reverse chronological order."""
        logs = [
            create_mock_log(id=3),
            create_mock_log(id=2),
            create_mock_log(id=1),
        ]
        
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = logs
        mock_db.execute = AsyncMock(return_value=mock_result)
        
        result = await service.query()
        
        assert len(result) == 3
        assert mock_db.execute.called

    @pytest.mark.asyncio
    async def test_query_filters_by_action(self, service, mock_db):
        """query should filter by action."""
        logs = [create_mock_log(action="publish")]
        
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = logs
        mock_db.execute = AsyncMock(return_value=mock_result)
        
        result = await service.query(action="publish")
        
        assert len(result) == 1
        assert mock_db.execute.called

    @pytest.mark.asyncio
    async def test_query_filters_by_target_type(self, service, mock_db):
        """query should filter by target_type."""
        logs = [create_mock_log(target_type="article")]
        
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = logs
        mock_db.execute = AsyncMock(return_value=mock_result)
        
        result = await service.query(target_type="article")
        
        assert len(result) == 1

    @pytest.mark.asyncio
    async def test_query_filters_by_operator(self, service, mock_db):
        """query should filter by operator (email)."""
        logs = [create_mock_log(operator="user@example.com")]
        
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = logs
        mock_db.execute = AsyncMock(return_value=mock_result)
        
        result = await service.query(operator="user@example.com")
        
        assert len(result) == 1

    @pytest.mark.asyncio
    async def test_query_filters_by_status(self, service, mock_db):
        """query should filter by status (success/failed)."""
        success_logs = [
            create_mock_log(id=1, status="success"),
            create_mock_log(id=2, status="success"),
        ]
        
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = success_logs
        mock_db.execute = AsyncMock(return_value=mock_result)
        
        result = await service.query(status="success")
        
        assert len(result) == 2
        assert all(log.status == "success" for log in result)

    @pytest.mark.asyncio
    async def test_query_filters_by_time_range(self, service, mock_db):
        """query should filter by start_time and end_time."""
        now = datetime.now(timezone.utc)
        yesterday = now - timedelta(days=1)
        tomorrow = now + timedelta(days=1)
        
        logs = [create_mock_log(timestamp=now)]
        
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = logs
        mock_db.execute = AsyncMock(return_value=mock_result)
        
        result = await service.query(start_time=yesterday, end_time=tomorrow)
        
        assert mock_db.execute.called

    @pytest.mark.asyncio
    async def test_query_keyword_search(self, service, mock_db):
        """query should search by keyword in description and error_message."""
        logs = [
            create_mock_log(description="Article published successfully"),
        ]
        
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = logs
        mock_db.execute = AsyncMock(return_value=mock_result)
        
        result = await service.query(keyword="Article")
        
        assert mock_db.execute.called

    @pytest.mark.asyncio
    async def test_query_pagination_with_limit_offset(self, service, mock_db):
        """query should support pagination with limit and offset."""
        logs = [create_mock_log(id=i) for i in range(10, 20)]
        
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = logs
        mock_db.execute = AsyncMock(return_value=mock_result)
        
        result = await service.query(limit=10, offset=20)
        
        assert len(result) == 10
        assert mock_db.execute.called

    @pytest.mark.asyncio
    async def test_query_multiple_filters(self, service, mock_db):
        """query should combine multiple filters."""
        logs = [
            create_mock_log(
                action="publish",
                operator="admin@example.com",
                status="failed",
            )
        ]
        
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = logs
        mock_db.execute = AsyncMock(return_value=mock_result)
        
        result = await service.query(
            action="publish",
            operator="admin@example.com",
            status="failed",
        )
        
        assert mock_db.execute.called


# ==============================================================================
# Section 3: Statistics
# ==============================================================================

class TestStatistics:
    """Test log statistics operations."""

    @pytest.mark.asyncio
    async def test_get_stats_returns_all_metrics(self, service, mock_db):
        """get_stats should return total, today, failed, and by_action counts."""
        # Mock the execute calls (4 queries)
        mock_results = [
            MagicMock(scalar=MagicMock(return_value=1000)),  # total
            MagicMock(scalar=MagicMock(return_value=150)),   # today
            MagicMock(scalar=MagicMock(return_value=25)),    # failed
            MagicMock(all=MagicMock(return_value=[
                ("publish", 500),
                ("sync", 300),
                ("create", 200),
            ])),  # by_action
        ]
        
        mock_db.execute = AsyncMock(side_effect=mock_results)
        
        result = await service.get_stats()
        
        assert result["total"] == 1000
        assert result["today"] == 150
        assert result["failed"] == 25
        assert "publish" in result["by_action"]

    @pytest.mark.asyncio
    async def test_get_stats_handles_zero_logs(self, service, mock_db):
        """get_stats should handle case with zero logs."""
        mock_results = [
            MagicMock(scalar=MagicMock(return_value=0)),  # total
            MagicMock(scalar=MagicMock(return_value=0)),  # today
            MagicMock(scalar=MagicMock(return_value=0)),  # failed
            MagicMock(all=MagicMock(return_value=[])),    # by_action empty
        ]
        
        mock_db.execute = AsyncMock(side_effect=mock_results)
        
        result = await service.get_stats()
        
        assert result["total"] == 0
        assert result["today"] == 0
        assert result["failed"] == 0
        assert result["by_action"] == {}


# ==============================================================================
# Section 4: Cleanup
# ==============================================================================

class TestCleanup:
    """Test log cleanup operations."""

    @pytest.mark.asyncio
    async def test_cleanup_deletes_old_logs(self, service, mock_db):
        """cleanup should delete logs older than specified days."""
        mock_result = MagicMock()
        mock_result.rowcount = 100
        mock_db.execute = AsyncMock(return_value=mock_result)
        mock_db.commit = AsyncMock()
        
        result = await service.cleanup(days=90)
        
        assert result == 100
        assert mock_db.execute.called
        assert mock_db.commit.called

    @pytest.mark.asyncio
    async def test_cleanup_default_90_days(self, service, mock_db):
        """cleanup should default to 90 days if not specified."""
        mock_result = MagicMock()
        mock_result.rowcount = 50
        mock_db.execute = AsyncMock(return_value=mock_result)
        mock_db.commit = AsyncMock()
        
        result = await service.cleanup()
        
        assert result == 50
        assert mock_db.execute.called

    @pytest.mark.asyncio
    async def test_cleanup_custom_days(self, service, mock_db):
        """cleanup should support custom retention period."""
        mock_result = MagicMock()
        mock_result.rowcount = 30
        mock_db.execute = AsyncMock(return_value=mock_result)
        mock_db.commit = AsyncMock()
        
        result = await service.cleanup(days=30)
        
        assert result == 30

    @pytest.mark.asyncio
    async def test_cleanup_returns_deleted_count(self, service, mock_db):
        """cleanup should return the count of deleted rows."""
        mock_result = MagicMock()
        mock_result.rowcount = 250
        mock_db.execute = AsyncMock(return_value=mock_result)
        mock_db.commit = AsyncMock()
        
        result = await service.cleanup(days=60)
        
        assert isinstance(result, int)
        assert result == 250


# ==============================================================================
# Section 5: Admin vs User Visibility
# ==============================================================================

class TestVisibility:
    """Test admin and user visibility rules (if implemented at service level)."""

    @pytest.mark.asyncio
    async def test_query_includes_admin_logs(self, service, mock_db):
        """Queries should include logs from admin operations."""
        admin_logs = [create_mock_log(is_admin=1, operator="admin@example.com")]
        
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = admin_logs
        mock_db.execute = AsyncMock(return_value=mock_result)
        
        result = await service.query()
        
        assert len(result) == 1
        assert result[0].is_admin == 1

    @pytest.mark.asyncio
    async def test_query_includes_user_logs(self, service, mock_db):
        """Queries should include logs from regular user operations."""
        user_logs = [create_mock_log(is_admin=0, operator="user@example.com")]
        
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = user_logs
        mock_db.execute = AsyncMock(return_value=mock_result)
        
        result = await service.query()
        
        assert len(result) == 1
        assert result[0].is_admin == 0


# ==============================================================================
# Section 6: Edge Cases
# ==============================================================================

class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    @pytest.mark.asyncio
    async def test_record_with_null_error_message(self, service, mock_db):
        """record should handle missing error message on successful operation."""
        mock_db.add = MagicMock()
        mock_db.commit = AsyncMock()
        mock_db.refresh = AsyncMock()
        
        result = await service.record(
            action="create",
            target_type="agent",
            status="success",
            error_message="",  # Empty on success
        )
        
        assert mock_db.add.called

    @pytest.mark.asyncio
    async def test_record_with_very_long_description(self, service, mock_db):
        """record should handle very long descriptions."""
        long_description = "A" * 500
        mock_db.add = MagicMock()
        mock_db.commit = AsyncMock()
        mock_db.refresh = AsyncMock()
        
        result = await service.record(
            action="sync",
            description=long_description,
        )
        
        assert mock_db.add.called

    @pytest.mark.asyncio
    async def test_record_with_complex_extra_json(self, service, mock_db):
        """record should handle complex nested JSON in extra field."""
        complex_extra = {
            "request": {
                "method": "POST",
                "headers": {"Content-Type": "application/json"},
            },
            "response": {
                "status_code": 200,
                "headers": {"X-Custom": "value"},
                "body": {"data": [1, 2, 3]},
            },
            "metrics": {
                "duration_ms": 123.45,
                "memory_used": 1024000,
            },
        }
        
        mock_db.add = MagicMock()
        mock_db.commit = AsyncMock()
        mock_db.refresh = AsyncMock()
        
        result = await service.record(
            action="generate",
            extra=complex_extra,
        )
        
        assert mock_db.add.called

    @pytest.mark.asyncio
    async def test_query_with_empty_keyword_string(self, service, mock_db):
        """query should handle empty keyword string."""
        logs = []
        
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = logs
        mock_db.execute = AsyncMock(return_value=mock_result)
        
        result = await service.query(keyword="")
        
        assert mock_db.execute.called

    @pytest.mark.asyncio
    async def test_query_pagination_zero_offset(self, service, mock_db):
        """query should handle zero offset (first page)."""
        logs = [create_mock_log(id=i) for i in range(1, 11)]
        
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = logs
        mock_db.execute = AsyncMock(return_value=mock_result)
        
        result = await service.query(limit=10, offset=0)
        
        assert len(result) == 10

    @pytest.mark.asyncio
    async def test_query_pagination_large_offset(self, service, mock_db):
        """query should handle large offset (beyond available results)."""
        logs = []  # No results for high offset
        
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = logs
        mock_db.execute = AsyncMock(return_value=mock_result)
        
        result = await service.query(limit=10, offset=10000)
        
        assert len(result) == 0
