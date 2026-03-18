"""Tests for mastery display conditional rendering (0-attempt hiding).

Verifies that get_assessment_readiness() includes total_attempts in each
ConceptReadiness entry, enabling the frontend to conditionally show/hide
mastery bars for concepts the student hasn't attempted yet.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from lecturelink_api.models.readiness_v2 import (
    AssessmentReadinessV2,
    ReadinessBreakdown,
    WeakConcept,
)
from lecturelink_api.services.tutor_planner import get_assessment_readiness

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _weak(
    concept_id: str,
    title: str,
    combined_score: float = 0.0,
    coverage: bool = False,
    practice_score: float = 0.0,
    freshness_score: float = 0.0,
) -> WeakConcept:
    return WeakConcept(
        concept_id=concept_id,
        title=title,
        coverage=coverage,
        practice_score=practice_score,
        freshness_score=freshness_score,
        combined_score=combined_score,
    )


def _v2_result(
    *,
    title: str = "Midterm",
    weak_concepts: list[WeakConcept] | None = None,
    readiness: float = 0.0,
    concept_count: int = 0,
    covered_count: int = 0,
) -> AssessmentReadinessV2:
    return AssessmentReadinessV2(
        assessment_id="a-1",
        title=title,
        course_id="course-1",
        assessment_type="exam",
        readiness=readiness,
        breakdown=ReadinessBreakdown(coverage=0, practice=0, freshness=0, effort=0),
        weak_concepts=weak_concepts or [],
        suggested_actions=[],
        urgency="medium",
        concept_count=concept_count,
        covered_count=covered_count,
    )


def _assessment_ctx(topics: list[str] | None = None) -> dict:
    return {
        "assessment_title": "Midterm",
        "due_date_str": None,
        "days_until": None,
        "topics": topics,
    }


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestTotalAttemptsInReadiness:
    """Verify total_attempts is included in ConceptReadiness entries."""

    @pytest.mark.asyncio
    @patch("lecturelink_api.services.tutor_planner.get_assessment_context", new_callable=AsyncMock)
    @patch("lecturelink_api.services.tutor_planner.compute_assessment_readiness", new_callable=AsyncMock)
    async def test_zero_attempts_concept(self, mock_v2, mock_ctx):
        """Concepts with 0 attempts should have total_attempts=0 and mastery=0."""
        mock_ctx.return_value = _assessment_ctx(topics=["Sorting"])
        mock_v2.return_value = _v2_result(
            weak_concepts=[_weak("c1", "Bubble Sort", combined_score=0.0)],
            concept_count=1,
        )

        sb = MagicMock()
        result = await get_assessment_readiness(sb, "course-1", "user-1", "a-1")

        assert len(result.concepts) >= 1
        concept = result.concepts[0]
        assert concept.total_attempts == 0
        assert concept.mastery == 0.0

    @pytest.mark.asyncio
    @patch("lecturelink_api.services.tutor_planner.get_assessment_context", new_callable=AsyncMock)
    @patch("lecturelink_api.services.tutor_planner.compute_assessment_readiness", new_callable=AsyncMock)
    async def test_concept_with_mastery(self, mock_v2, mock_ctx):
        """Concepts with mastery should report the correct combined_score."""
        mock_ctx.return_value = _assessment_ctx(topics=["Sorting"])
        mock_v2.return_value = _v2_result(
            weak_concepts=[_weak("c1", "Merge Sort", combined_score=0.75, coverage=True)],
            readiness=0.75,
            concept_count=1,
        )

        sb = MagicMock()
        result = await get_assessment_readiness(sb, "course-1", "user-1", "a-1")

        assert len(result.concepts) >= 1
        concept = result.concepts[0]
        assert concept.mastery > 0

    @pytest.mark.asyncio
    @patch("lecturelink_api.services.tutor_planner.get_assessment_context", new_callable=AsyncMock)
    @patch("lecturelink_api.services.tutor_planner.compute_assessment_readiness", new_callable=AsyncMock)
    async def test_mixed_course_weak_concepts(self, mock_v2, mock_ctx):
        """Course with both covered and uncovered weak concepts."""
        mock_ctx.return_value = _assessment_ctx(topics=["Sorting", "Graphs"])
        mock_v2.return_value = _v2_result(
            title="Final",
            weak_concepts=[
                _weak("c1", "Quick Sort", combined_score=0.6, coverage=True),
                _weak("c2", "BFS", combined_score=0.0, coverage=False),
            ],
            readiness=0.3,
            concept_count=2,
        )

        sb = MagicMock()
        result = await get_assessment_readiness(sb, "course-1", "user-1", "a-1")

        # Should have concepts from consolidation
        assert len(result.concepts) >= 1

    @pytest.mark.asyncio
    @patch("lecturelink_api.services.tutor_planner.get_assessment_context", new_callable=AsyncMock)
    @patch("lecturelink_api.services.tutor_planner.compute_assessment_readiness", new_callable=AsyncMock)
    async def test_fallback_topics_have_zero_attempts(self, mock_v2, mock_ctx):
        """When no weak concepts, fallback topics should have total_attempts=0."""
        mock_ctx.return_value = _assessment_ctx(topics=["Arrays", "Linked Lists"])
        mock_v2.return_value = _v2_result(
            title="Quiz 1",
            weak_concepts=[],
            concept_count=0,
        )

        sb = MagicMock()
        result = await get_assessment_readiness(sb, "course-1", "user-1", "a-1")

        assert len(result.concepts) == 2
        for concept in result.concepts:
            assert concept.total_attempts == 0
            assert concept.mastery == 0.0
