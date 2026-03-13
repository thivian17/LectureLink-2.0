"""Tests for the dashboard briefing service."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from lecturelink_api.services.dashboard_briefing import (
    NO_COURSES_GREETING,
    chat_cross_course,
    gather_briefing_context,
    generate_greeting,
    get_briefing,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _mock_execute(data, count=None):
    resp = MagicMock()
    resp.data = data
    resp.count = count or 0
    return resp


def _mock_chain(final_data, count=None):
    chain = MagicMock()
    chain.execute.return_value = _mock_execute(final_data, count=count)
    for method in (
        "select", "insert", "update", "delete",
        "eq", "in_", "gte", "order", "limit", "single",
    ):
        getattr(chain, method).return_value = chain
    return chain


def _make_supabase(
    *,
    courses=None,
    streak=None,
    level=None,
    assessments=None,
    mastery_rows=None,
    sessions=None,
    lecture_count=0,
    user_meta=None,
):
    """Build a mock supabase client for gather_briefing_context."""
    sb = MagicMock()

    # Auth
    user_obj = MagicMock()
    user_obj.user_metadata = user_meta or {"full_name": "Test Student"}
    user_obj.email = "test@example.com"
    auth_result = MagicMock()
    auth_result.user = user_obj
    sb.auth.get_user.return_value = auth_result

    # RPC
    def rpc_side_effect(name, params=None):
        result = MagicMock()
        if name == "get_concept_mastery":
            result.execute.return_value = _mock_execute(mastery_rows or [])
        else:
            result.execute.return_value = _mock_execute([])
        return result

    sb.rpc.side_effect = rpc_side_effect

    # Tables
    def table_side_effect(name):
        if name == "user_streaks":
            return _mock_chain(streak or {"current_streak": 3, "longest_streak": 10})
        if name == "user_levels":
            return _mock_chain(level or {"total_xp": 500, "current_level": 5})
        if name == "courses":
            return _mock_chain(courses if courses is not None else [])
        if name == "assessments":
            return _mock_chain(assessments or [])
        if name == "learn_sessions":
            return _mock_chain(sessions or [])
        if name == "lectures":
            return _mock_chain([], count=lecture_count)
        return _mock_chain([])

    sb.table.side_effect = table_side_effect
    return sb


# ---------------------------------------------------------------------------
# Test 1: gather_briefing_context with courses
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_gather_context_with_courses():
    """Returns structured data with assessments, mastery, streak."""
    courses = [
        {
            "id": "course-1",
            "name": "Algorithms",
            "code": "CS 301",
            "semester_start": "2026-01-15",
            "semester_end": "2026-05-15",
            "meeting_days": ["Monday", "Wednesday"],
            "holidays": None,
        }
    ]
    assessments = [
        {
            "id": "a-1",
            "title": "Midterm Exam",
            "due_date": "2026-04-01",
            "weight_percent": 30,
            "type": "exam",
        }
    ]
    mastery_rows = [
        {
            "concept_id": "c1",
            "concept_title": "Binary Trees",
            "accuracy": 0.4,
            "recent_accuracy": 0.3,
            "total_attempts": 5,
        },
        {
            "concept_id": "c2",
            "concept_title": "Graph Traversal",
            "accuracy": 0.8,
            "recent_accuracy": 0.9,
            "total_attempts": 10,
        },
    ]

    sb = _make_supabase(
        courses=courses,
        assessments=assessments,
        mastery_rows=mastery_rows,
    )

    ctx = await gather_briefing_context(sb, "user-1")

    assert ctx["has_courses"] is True
    assert ctx["student_name"] == "Test Student"
    assert ctx["current_streak"] == 3
    assert ctx["total_xp"] == 500
    assert len(ctx["courses"]) == 1

    course = ctx["courses"][0]
    assert course["course_id"] == "course-1"
    assert course["course_name"] == "Algorithms"
    assert course["next_assessment"]["title"] == "Midterm Exam"
    assert course["next_assessment"]["weight_percent"] == 30
    assert len(course["weak_concepts"]) == 2
    # Weakest concept first
    assert course["weak_concepts"][0]["title"] == "Binary Trees"


# ---------------------------------------------------------------------------
# Test 2: gather_briefing_context no courses
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_gather_context_no_courses():
    """Returns has_courses: False when user has no courses."""
    sb = _make_supabase(courses=[])

    ctx = await gather_briefing_context(sb, "user-1")

    assert ctx["has_courses"] is False
    assert ctx["courses"] == []
    assert ctx["top_priority_course_id"] is None


# ---------------------------------------------------------------------------
# Test 3: generate_greeting no courses — static, no LLM
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_generate_greeting_no_courses():
    """Returns static NO_COURSES_GREETING without calling the LLM."""
    context = {"has_courses": False, "courses": []}

    result = await generate_greeting(context)

    assert result == NO_COURSES_GREETING


# ---------------------------------------------------------------------------
# Test 4: generate_greeting with courses — mock Gemini
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_generate_greeting_with_courses():
    """Calls Gemini and returns structured JSON greeting."""
    context = {
        "has_courses": True,
        "student_name": "Alice",
        "current_streak": 5,
        "courses": [
            {
                "course_id": "c1",
                "course_name": "Physics",
                "next_assessment": {"title": "Quiz 3", "days_until": 3},
                "weak_concepts": [{"title": "Kinematics", "mastery": 0.35}],
            }
        ],
    }

    llm_response = {
        "greeting": "Hey Alice! Quiz 3 is in 3 days.",
        "session_pitch": "Focus on Kinematics today.",
        "checkin_question": "How are you feeling about Physics?",
        "encouragement": "5-day streak!",
    }

    mock_response = MagicMock()
    mock_response.text = json.dumps(llm_response)

    mock_client = MagicMock()
    mock_client.aio.models.generate_content = AsyncMock(return_value=mock_response)

    with patch(
        "lecturelink_api.services.genai_client.get_genai_client",
        return_value=mock_client,
    ):
        result = await generate_greeting(context)

    assert result["greeting"] == "Hey Alice! Quiz 3 is in 3 days."
    assert result["session_pitch"] == "Focus on Kinematics today."
    assert result["checkin_question"] == "How are you feeling about Physics?"
    mock_client.aio.models.generate_content.assert_awaited_once()


# ---------------------------------------------------------------------------
# Test 5: generate_greeting LLM failure — fallback
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_generate_greeting_llm_failure_fallback():
    """Falls back to template greeting when LLM fails."""
    context = {
        "has_courses": True,
        "student_name": "Bob",
        "current_streak": 2,
        "courses": [
            {
                "course_id": "c1",
                "course_name": "Math",
                "next_assessment": {"title": "Final", "days_until": 5},
                "weak_concepts": [],
            }
        ],
    }

    mock_client = MagicMock()
    mock_client.aio.models.generate_content = AsyncMock(
        side_effect=RuntimeError("API down")
    )

    with patch(
        "lecturelink_api.services.genai_client.get_genai_client",
        return_value=mock_client,
    ):
        result = await generate_greeting(context)

    assert "Bob" in result["greeting"]
    assert "Final" in result["greeting"]
    assert "2-day streak" in result["greeting"]
    assert result["checkin_question"] == "How are you feeling about your classes?"


# ---------------------------------------------------------------------------
# Test 6: get_briefing cache hit
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_briefing_cache_hit():
    """Returns cached data without making DB queries."""
    cached_data = {"context": {"has_courses": True}, "greeting": {"greeting": "Hi!"}}

    with patch(
        "lecturelink_api.services.redis_client.cache_get",
        new_callable=AsyncMock,
        return_value=cached_data,
    ):
        sb = MagicMock()
        result = await get_briefing(sb, "user-1")

    assert result == cached_data
    # Supabase should not have been called
    sb.table.assert_not_called()
    sb.auth.get_user.assert_not_called()


# ---------------------------------------------------------------------------
# Test 7: get_briefing cache miss — full pipeline
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_briefing_cache_miss():
    """Calls gather + generate + caches result on miss."""
    sb = _make_supabase(courses=[])

    mock_cache_get = AsyncMock(return_value=None)
    mock_cache_set = AsyncMock()

    with (
        patch(
            "lecturelink_api.services.redis_client.cache_get",
            mock_cache_get,
        ),
        patch(
            "lecturelink_api.services.redis_client.cache_set",
            mock_cache_set,
        ),
    ):
        result = await get_briefing(sb, "user-1")

    assert "context" in result
    assert "greeting" in result
    # No courses → static greeting
    assert result["greeting"] == NO_COURSES_GREETING
    # Should have tried to cache
    mock_cache_set.assert_awaited_once()
    call_args = mock_cache_set.call_args
    assert call_args[0][0] == "dashboard_briefing:user-1"
    assert call_args[1]["ttl"] == 3 * 60 * 60


# ---------------------------------------------------------------------------
# Test 8: chat_cross_course
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_chat_cross_course():
    """Passes context to Gemini and returns response."""
    sb = _make_supabase(courses=[])

    mock_response = MagicMock()
    mock_response.text = "Great question! Based on your data, I suggest..."

    mock_client = MagicMock()
    mock_client.aio.models.generate_content = AsyncMock(return_value=mock_response)

    with patch(
        "lecturelink_api.services.genai_client.get_genai_client",
        return_value=mock_client,
    ):
        result = await chat_cross_course(
            sb, "user-1", "How should I study for my exam?",
            conversation_history=[{"role": "user", "content": "Hello"}],
        )

    assert result["message"] == "Great question! Based on your data, I suggest..."
    assert result["context_used"] is True
    mock_client.aio.models.generate_content.assert_awaited_once()
