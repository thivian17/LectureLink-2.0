"""Tests for the performance analytics service."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest


def _mock_execute(data):
    resp = MagicMock()
    resp.data = data
    resp.count = 0
    return resp


def _mock_chain(final_data):
    chain = MagicMock()
    chain.execute.return_value = _mock_execute(final_data)
    for method in ("select", "eq", "in_", "order", "limit", "single"):
        getattr(chain, method).return_value = chain
    return chain


def _make_mastery_row(
    concept_id="c1",
    title="Entropy",
    total_attempts=10,
    correct_attempts=6,
    accuracy=0.6,
    recent_accuracy=0.8,
    trend="improving",
    **kw,
):
    return {
        "concept_id": concept_id,
        "concept_title": title,
        "concept_description": kw.get("description"),
        "concept_category": kw.get("category", "concept"),
        "difficulty_estimate": kw.get("difficulty_estimate", 0.5),
        "lecture_id": kw.get("lecture_id"),
        "total_attempts": total_attempts,
        "correct_attempts": correct_attempts,
        "accuracy": accuracy,
        "avg_time_seconds": kw.get("avg_time_seconds", 30.0),
        "recent_accuracy": recent_accuracy,
        "trend": trend,
    }


def _make_quiz_row(quiz_id="q1", title="Quiz 1", best_score=80.0, **kw):
    return {
        "quiz_id": quiz_id,
        "quiz_title": title,
        "difficulty": kw.get("difficulty", "medium"),
        "best_score": best_score,
        "attempt_count": kw.get("attempt_count", 1),
        "question_count": kw.get("question_count", 10),
        "created_at": kw.get("created_at", "2025-01-01T00:00:00+00:00"),
    }


def _setup_supabase(mastery_rows, quiz_rows, links=None, assessment_titles=None):
    """Return a mock supabase client with RPC and table responses."""
    sb = MagicMock()

    rpc_results = [
        _mock_execute(mastery_rows),
        _mock_execute(quiz_rows),
    ]
    call_count = {"rpc": 0}

    def rpc_side_effect(*a, **k):
        result = MagicMock()
        result.execute.return_value = rpc_results[call_count["rpc"]]
        call_count["rpc"] += 1
        return result

    sb.rpc.side_effect = rpc_side_effect

    # Table mock for concept_assessment_links and assessments
    def table_side_effect(name):
        if name == "concept_assessment_links":
            return _mock_chain(links or [])
        if name == "assessments":
            return _mock_chain(assessment_titles or [])
        return _mock_chain([])

    sb.table.side_effect = table_side_effect
    return sb


class TestGetPerformanceEmpty:
    @pytest.mark.asyncio
    async def test_empty_data_returns_zeros(self):
        from lecturelink_api.services.performance import get_performance

        sb = _setup_supabase([], [])
        result = await get_performance(sb, "course-1", "user-1")

        assert result["overall"]["total_questions_attempted"] == 0
        assert result["overall"]["overall_accuracy"] == 0.0
        assert result["overall"]["quizzes_taken"] == 0
        assert result["overall"]["average_quiz_score"] is None
        assert result["concepts"] == []
        assert result["quiz_history"] == []
        assert result["weak_concepts"] == []
        assert result["strong_concepts"] == []


class TestGetPerformanceMastery:
    @pytest.mark.asyncio
    async def test_computes_mastery_blend(self):
        """mastery = accuracy * 0.6 + recent_accuracy * 0.4"""
        from lecturelink_api.services.performance import get_performance

        sb = _setup_supabase(
            [_make_mastery_row(accuracy=0.6, recent_accuracy=0.8)],
            [],
        )
        result = await get_performance(sb, "c", "u")
        concept = result["concepts"][0]
        expected = 0.6 * 0.6 + 0.8 * 0.4  # 0.68
        assert abs(concept["mastery"] - expected) < 0.01

    @pytest.mark.asyncio
    async def test_zero_mastery_for_new_concepts(self):
        """Concepts with 0 attempts should have mastery=0."""
        from lecturelink_api.services.performance import get_performance

        sb = _setup_supabase(
            [_make_mastery_row(total_attempts=0, correct_attempts=0, accuracy=0.0,
                               recent_accuracy=0.0, trend="new")],
            [],
        )
        result = await get_performance(sb, "c", "u")
        assert result["concepts"][0]["mastery"] == 0.0

    @pytest.mark.asyncio
    async def test_weak_concepts_below_half(self):
        """Concepts with mastery < 0.5 and attempts > 0 are weak."""
        from lecturelink_api.services.performance import get_performance

        sb = _setup_supabase(
            [
                _make_mastery_row(
                    concept_id="strong", accuracy=0.9, recent_accuracy=0.9,
                    total_attempts=10, correct_attempts=9,
                ),
                _make_mastery_row(
                    concept_id="weak", accuracy=0.2, recent_accuracy=0.3,
                    total_attempts=10, correct_attempts=2,
                ),
            ],
            [],
        )
        result = await get_performance(sb, "c", "u")
        assert "weak" in result["weak_concepts"]
        assert "strong" not in result["weak_concepts"]

    @pytest.mark.asyncio
    async def test_strong_concepts_above_80(self):
        """Concepts with mastery >= 0.8 are strong."""
        from lecturelink_api.services.performance import get_performance

        sb = _setup_supabase(
            [_make_mastery_row(
                concept_id="expert", accuracy=0.9, recent_accuracy=0.9,
                total_attempts=10, correct_attempts=9,
            )],
            [],
        )
        result = await get_performance(sb, "c", "u")
        assert "expert" in result["strong_concepts"]


class TestGetPerformanceOverall:
    @pytest.mark.asyncio
    async def test_overall_accuracy(self):
        from lecturelink_api.services.performance import get_performance

        sb = _setup_supabase(
            [
                _make_mastery_row(total_attempts=10, correct_attempts=8),
                _make_mastery_row(concept_id="c2", total_attempts=10, correct_attempts=6),
            ],
            [],
        )
        result = await get_performance(sb, "c", "u")
        # 14 correct / 20 total = 0.7
        assert abs(result["overall"]["overall_accuracy"] - 0.7) < 0.01

    @pytest.mark.asyncio
    async def test_average_quiz_score(self):
        from lecturelink_api.services.performance import get_performance

        sb = _setup_supabase(
            [],
            [
                _make_quiz_row(best_score=80.0),
                _make_quiz_row(quiz_id="q2", best_score=60.0),
            ],
        )
        result = await get_performance(sb, "c", "u")
        assert result["overall"]["quizzes_taken"] == 2
        assert result["overall"]["average_quiz_score"] == 70.0

    @pytest.mark.asyncio
    async def test_quiz_history_formatting(self):
        from lecturelink_api.services.performance import get_performance

        sb = _setup_supabase(
            [],
            [_make_quiz_row(quiz_id="q1", title="Test Quiz")],
        )
        result = await get_performance(sb, "c", "u")
        assert len(result["quiz_history"]) == 1
        assert result["quiz_history"][0]["quiz_id"] == "q1"
        assert result["quiz_history"][0]["title"] == "Test Quiz"


class TestGetPerformanceCategories:
    @pytest.mark.asyncio
    async def test_strongest_weakest_categories(self):
        from lecturelink_api.services.performance import get_performance

        sb = _setup_supabase(
            [
                _make_mastery_row(
                    concept_id="c1", category="physics",
                    accuracy=0.9, recent_accuracy=0.9,
                    total_attempts=10, correct_attempts=9,
                ),
                _make_mastery_row(
                    concept_id="c2", category="math",
                    accuracy=0.3, recent_accuracy=0.2,
                    total_attempts=10, correct_attempts=3,
                ),
            ],
            [],
        )
        result = await get_performance(sb, "c", "u")
        assert result["overall"]["strongest_category"] == "physics"
        assert result["overall"]["weakest_category"] == "math"
