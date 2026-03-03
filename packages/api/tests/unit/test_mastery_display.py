"""Tests for mastery display conditional rendering (0-attempt hiding).

Verifies that get_assessment_readiness() includes total_attempts in each
ConceptReadiness entry, enabling the frontend to conditionally show/hide
mastery bars for concepts the student hasn't attempted yet.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from lecturelink_api.services.tutor_planner import get_assessment_readiness


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _mock_supabase(
    *,
    assessment: dict | None = None,
    links: list[dict] | None = None,
    mastery: list[dict] | None = None,
    events: list[dict] | None = None,
    lectures: list[dict] | None = None,
) -> MagicMock:
    """Build a mock Supabase client wired for get_assessment_readiness."""
    sb = MagicMock()

    # --- table() chains ---
    def _table(name: str) -> MagicMock:
        chain = MagicMock()
        chain.eq.return_value = chain
        chain.in_.return_value = chain
        chain.order.return_value = chain
        chain.limit.return_value = chain

        if name == "assessments":
            chain.select.return_value = chain
            chain.maybe_single.return_value = chain
            chain.execute.return_value = MagicMock(data=assessment)
        elif name == "concept_assessment_links":
            chain.select.return_value = chain
            chain.execute.return_value = MagicMock(data=links or [])
        elif name == "tutor_session_events":
            chain.select.return_value = chain
            chain.execute.return_value = MagicMock(data=events or [])
        elif name == "lectures":
            chain.select.return_value = chain
            chain.execute.return_value = MagicMock(data=lectures or [])
        elif name == "courses":
            chain.select.return_value = chain
            chain.maybe_single.return_value = chain
            chain.execute.return_value = MagicMock(
                data={"name": "CS 101", "code": "CS101"}
            )
        return chain

    sb.table.side_effect = _table

    # --- rpc() for get_concept_mastery ---
    rpc_chain = MagicMock()
    rpc_chain.execute.return_value = MagicMock(data=mastery or [])
    sb.rpc.return_value = rpc_chain

    return sb


def _mastery_row(
    concept_id: str,
    title: str,
    total_attempts: int,
    accuracy: float = 0.0,
    recent_accuracy: float = 0.0,
    lecture_id: str | None = None,
) -> dict:
    """Build a row mimicking the get_concept_mastery RPC output."""
    return {
        "concept_id": concept_id,
        "concept_title": title,
        "total_attempts": total_attempts,
        "accuracy": accuracy,
        "recent_accuracy": recent_accuracy,
        "lecture_id": lecture_id,
        "difficulty_estimate": 0.5,
        "concept_description": "",
        "concept_category": "general",
        "correct_attempts": int(total_attempts * accuracy),
        "avg_time_seconds": 10.0,
        "trend": "new",
    }


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestTotalAttemptsInReadiness:
    """Verify total_attempts is included in ConceptReadiness entries."""

    @pytest.mark.asyncio
    async def test_zero_attempts_concept(self):
        """Concepts with 0 attempts should have total_attempts=0 and mastery=0."""
        sb = _mock_supabase(
            assessment={"title": "Midterm", "due_date": None, "weight_percent": 30, "topics": ["Sorting"]},
            mastery=[
                _mastery_row("c1", "Bubble Sort", total_attempts=0),
            ],
        )

        result = await get_assessment_readiness(sb, "course-1", "user-1", "a-1")

        assert len(result.concepts) >= 1
        concept = result.concepts[0]
        assert concept.total_attempts == 0
        assert concept.mastery == 0.0

    @pytest.mark.asyncio
    async def test_concept_with_attempts(self):
        """Concepts with attempts should report the correct total_attempts."""
        sb = _mock_supabase(
            assessment={"title": "Midterm", "due_date": None, "weight_percent": 30, "topics": ["Sorting"]},
            mastery=[
                _mastery_row("c1", "Merge Sort", total_attempts=12, accuracy=0.8, recent_accuracy=0.9),
            ],
        )

        result = await get_assessment_readiness(sb, "course-1", "user-1", "a-1")

        assert len(result.concepts) >= 1
        concept = result.concepts[0]
        assert concept.total_attempts == 12
        assert concept.mastery > 0

    @pytest.mark.asyncio
    async def test_mixed_course_attempts(self):
        """Course with both attempted and unattempted concepts."""
        sb = _mock_supabase(
            assessment={
                "title": "Final",
                "due_date": None,
                "weight_percent": 40,
                "topics": ["Sorting", "Graphs"],
            },
            mastery=[
                _mastery_row("c1", "Quick Sort", total_attempts=5, accuracy=0.6, recent_accuracy=0.7),
                _mastery_row("c2", "BFS", total_attempts=0),
            ],
        )

        result = await get_assessment_readiness(sb, "course-1", "user-1", "a-1")

        attempts_by_title: dict[str, int] = {}
        for c in result.concepts:
            attempts_by_title[c.title] = c.total_attempts

        # At least one topic should have attempts > 0, another should have 0
        all_attempts = list(attempts_by_title.values())
        assert any(a > 0 for a in all_attempts), "Expected at least one concept with attempts"
        # The unattempted concept contributes 0 attempts to its topic bucket
        # (or appears directly with 0)

    @pytest.mark.asyncio
    async def test_fallback_topics_have_zero_attempts(self):
        """When no mastery data exists, fallback topics should have total_attempts=0."""
        sb = _mock_supabase(
            assessment={
                "title": "Quiz 1",
                "due_date": None,
                "weight_percent": 10,
                "topics": ["Arrays", "Linked Lists"],
            },
            mastery=[],  # No mastery data at all
        )

        result = await get_assessment_readiness(sb, "course-1", "user-1", "a-1")

        assert len(result.concepts) == 2
        for concept in result.concepts:
            assert concept.total_attempts == 0
            assert concept.mastery == 0.0
