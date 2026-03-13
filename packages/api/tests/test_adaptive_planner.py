"""Tests for adaptive quiz planning in quiz_planner.py."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


def _mock_execute(data):
    resp = MagicMock()
    resp.data = data
    resp.count = 0
    return resp


def _mock_chain(final_data):
    chain = MagicMock()
    chain.execute.return_value = _mock_execute(final_data)
    for method in ("select", "eq", "in_", "order", "limit"):
        getattr(chain, method).return_value = chain
    return chain


def _make_concept(concept_id, title="Concept", difficulty=0.5, **kw):
    return {
        "id": concept_id,
        "title": title,
        "description": kw.get("description", ""),
        "category": kw.get("category", "concept"),
        "difficulty_estimate": difficulty,
        "lecture_id": kw.get("lecture_id", "lec-1"),
    }


def _make_mastery(concept_id, accuracy=0.5, recent_accuracy=0.5, total_attempts=5, **kw):
    return {
        "concept_id": concept_id,
        "concept_title": kw.get("title", "Concept"),
        "concept_description": None,
        "concept_category": "concept",
        "difficulty_estimate": 0.5,
        "lecture_id": None,
        "total_attempts": total_attempts,
        "correct_attempts": int(accuracy * total_attempts),
        "accuracy": accuracy,
        "avg_time_seconds": 30.0,
        "recent_accuracy": recent_accuracy,
        "trend": kw.get("trend", "stable"),
    }


class TestAdaptivePlanQuiz:
    @pytest.mark.asyncio
    @patch("lecturelink_api.services.quiz_planner.fetch_concept_chunks", new_callable=AsyncMock)
    async def test_adaptive_prioritizes_weak_concepts(self, mock_search):
        """Weak concepts (low mastery) should appear first in the plan."""
        from lecturelink_api.services.quiz_planner import plan_quiz

        mock_search.return_value = [{"chunk_id": "ch1", "content": "test"}]

        concepts = [
            _make_concept("strong", "Strong Topic", difficulty=0.5),
            _make_concept("weak", "Weak Topic", difficulty=0.5),
        ]
        mastery = [
            _make_mastery("strong", accuracy=0.9, recent_accuracy=0.9),
            _make_mastery("weak", accuracy=0.2, recent_accuracy=0.1),
        ]

        sb = MagicMock()
        sb.table.return_value = _mock_chain(concepts)
        sb.rpc.return_value = MagicMock(
            execute=MagicMock(return_value=_mock_execute(mastery))
        )

        result = await plan_quiz(
            sb, "course-1", "user-1", difficulty="adaptive", num_questions=2,
        )

        # Weak concept should come first
        plan_titles = [c["concept"]["title"] for c in result["concepts"]]
        assert plan_titles[0] == "Weak Topic"

    @pytest.mark.asyncio
    @patch("lecturelink_api.services.quiz_planner.fetch_concept_chunks", new_callable=AsyncMock)
    async def test_adaptive_returns_adaptive_difficulties(self, mock_search):
        """Plan should include adaptive_difficulties dict."""
        from lecturelink_api.services.quiz_planner import plan_quiz

        mock_search.return_value = [{"chunk_id": "ch1", "content": "test"}]

        concepts = [_make_concept("c1", "Topic")]
        mastery = [_make_mastery("c1", accuracy=0.8, recent_accuracy=0.9)]

        sb = MagicMock()
        sb.table.return_value = _mock_chain(concepts)
        sb.rpc.return_value = MagicMock(
            execute=MagicMock(return_value=_mock_execute(mastery))
        )

        result = await plan_quiz(
            sb, "course-1", "user-1", difficulty="adaptive", num_questions=1,
        )

        assert "adaptive_difficulties" in result
        assert "c1" in result["adaptive_difficulties"]

    @pytest.mark.asyncio
    @patch("lecturelink_api.services.quiz_planner.fetch_concept_chunks", new_callable=AsyncMock)
    async def test_adaptive_difficulty_increases_for_strong_students(self, mock_search):
        """Strong students should get harder questions on their strong concepts."""
        from lecturelink_api.services.quiz_planner import plan_quiz

        mock_search.return_value = [{"chunk_id": "ch1", "content": "test"}]

        concepts = [_make_concept("c1", "Topic", difficulty=0.5)]
        mastery = [_make_mastery("c1", accuracy=0.9, recent_accuracy=0.9)]

        sb = MagicMock()
        sb.table.return_value = _mock_chain(concepts)
        sb.rpc.return_value = MagicMock(
            execute=MagicMock(return_value=_mock_execute(mastery))
        )

        result = await plan_quiz(
            sb, "course-1", "user-1", difficulty="adaptive", num_questions=1,
        )

        # mastery = 0.9*0.6 + 0.9*0.4 = 0.9 → diff = 0.5 + (0.9-0.5)*0.4 = 0.66
        adaptive_diff = result["adaptive_difficulties"]["c1"]
        assert adaptive_diff > 0.5

    @pytest.mark.asyncio
    @patch("lecturelink_api.services.quiz_planner.fetch_concept_chunks", new_callable=AsyncMock)
    async def test_non_adaptive_unchanged(self, mock_search):
        """Non-adaptive difficulty should use original band filtering."""
        from lecturelink_api.services.quiz_planner import plan_quiz

        mock_search.return_value = [{"chunk_id": "ch1", "content": "test"}]

        concepts = [
            _make_concept("c1", "Easy Concept", difficulty=0.3),
            _make_concept("c2", "Hard Concept", difficulty=0.8),
        ]

        sb = MagicMock()
        sb.table.return_value = _mock_chain(concepts)

        result = await plan_quiz(
            sb, "course-1", "user-1", difficulty="easy", num_questions=2,
        )

        assert "adaptive_difficulties" not in result

    @pytest.mark.asyncio
    @patch("lecturelink_api.services.quiz_planner.fetch_concept_chunks", new_callable=AsyncMock)
    async def test_adaptive_new_concepts_get_medium_priority(self, mock_search):
        """Concepts with no attempts should get medium priority (0.5)."""
        from lecturelink_api.services.quiz_planner import plan_quiz

        mock_search.return_value = [{"chunk_id": "ch1", "content": "test"}]

        concepts = [
            _make_concept("new", "New Topic"),
            _make_concept("weak", "Weak Topic"),
        ]
        mastery = [
            _make_mastery("new", total_attempts=0, accuracy=0.0, recent_accuracy=0.0),
            _make_mastery("weak", accuracy=0.1, recent_accuracy=0.1, total_attempts=10),
        ]

        sb = MagicMock()
        sb.table.return_value = _mock_chain(concepts)
        sb.rpc.return_value = MagicMock(
            execute=MagicMock(return_value=_mock_execute(mastery))
        )

        result = await plan_quiz(
            sb, "course-1", "user-1", difficulty="adaptive", num_questions=2,
        )

        # Weak (mastery ~0.1) should be first, new (medium priority) second
        plan_titles = [c["concept"]["title"] for c in result["concepts"]]
        assert plan_titles[0] == "Weak Topic"
        assert plan_titles[1] == "New Topic"
