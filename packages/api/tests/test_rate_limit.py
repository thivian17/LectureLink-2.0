"""Test rate limiting utility."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException
from lecturelink_api.middleware.rate_limit import (
    RATE_LIMITS,
    check_rate_limit,
    get_rate_limit_status,
)


def _mock_supabase(count: int = 0):
    """Create a mock Supabase client that reports *count* existing events."""
    client = MagicMock()
    chain = client.table.return_value.select.return_value
    chain = chain.eq.return_value.eq.return_value.gte.return_value
    chain.execute.return_value = MagicMock(count=count)
    client.table.return_value.insert.return_value.execute.return_value = MagicMock(
        data=[{"id": "new"}]
    )
    return client


class TestCheckRateLimit:
    def test_allows_within_limit(self):
        sb = _mock_supabase(count=0)
        result = check_rate_limit(sb, "user-1", "quiz_generate")
        assert result is True

    def test_raises_429_when_exceeded(self):
        limit = RATE_LIMITS["quiz_generate"]["max_count"]
        sb = _mock_supabase(count=limit)
        with pytest.raises(HTTPException) as exc_info:
            check_rate_limit(sb, "user-1", "quiz_generate")
        assert exc_info.value.status_code == 429
        assert "Retry-After" in exc_info.value.headers

    def test_unknown_action_allowed(self):
        sb = _mock_supabase()
        result = check_rate_limit(sb, "user-1", "unknown_action")
        assert result is True

    def test_records_event_on_success(self):
        sb = _mock_supabase(count=0)
        check_rate_limit(sb, "user-1", "lecture_upload")
        sb.table.return_value.insert.return_value.execute.assert_called_once()


class TestGetRateLimitStatus:
    def test_returns_correct_counts(self):
        sb = _mock_supabase(count=5)
        status = get_rate_limit_status(sb, "user-1", "qa_question")
        assert status["used"] == 5
        assert status["limit"] == 50
        assert status["remaining"] == 45

    def test_zero_remaining_when_maxed(self):
        sb = _mock_supabase(count=50)
        status = get_rate_limit_status(sb, "user-1", "qa_question")
        assert status["remaining"] == 0


class TestRateLimitValues:
    def test_quiz_generate(self):
        assert RATE_LIMITS["quiz_generate"]["max_count"] == 10
        assert RATE_LIMITS["quiz_generate"]["window_hours"] == 24

    def test_qa_question(self):
        assert RATE_LIMITS["qa_question"]["max_count"] == 50
        assert RATE_LIMITS["qa_question"]["window_hours"] == 1

    def test_lecture_upload(self):
        assert RATE_LIMITS["lecture_upload"]["max_count"] == 30
        assert RATE_LIMITS["lecture_upload"]["window_hours"] == 24
