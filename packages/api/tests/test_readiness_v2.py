"""Tests for the Readiness V2 signal calculations and composite score."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock

import pytest

from lecturelink_api.models.readiness_v2 import (
    EXAM_TYPES,
    ReadinessBreakdown,
)
from lecturelink_api.services.readiness_v2 import (
    COVERAGE_WEIGHT,
    EFFORT_WEIGHT,
    FRESHNESS_WEIGHT,
    PRACTICE_WEIGHT,
    _compute_coverage,
    _compute_effort,
    _compute_freshness,
    _compute_practice,
    _weighted_readiness,
    classify_urgency,
    compute_assessment_readiness,
    compute_course_readiness,
    get_all_course_readiness,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _mock_execute(data):
    resp = MagicMock()
    resp.data = data
    resp.count = len(data) if isinstance(data, list) else 0
    return resp


def _mock_chain(final_data):
    """Return a chainable mock that resolves to final_data on .execute()."""
    chain = MagicMock()
    chain.execute.return_value = _mock_execute(final_data)
    for method in (
        "select", "insert", "update", "delete",
        "eq", "in_", "order", "limit", "single",
        "gte", "is_",
    ):
        getattr(chain, method).return_value = chain
    return chain


NOW = datetime.now(UTC)


# ===================================================================
# Coverage signal
# ===================================================================

class TestCoverageSignal:
    def test_all_covered(self):
        linked = {"c1", "c2", "c3"}
        interacted = {"c1", "c2", "c3"}
        assert _compute_coverage(linked, interacted) == 1.0

    def test_none_covered(self):
        linked = {"c1", "c2", "c3"}
        interacted: set[str] = set()
        assert _compute_coverage(linked, interacted) == 0.0

    def test_partial_coverage(self):
        linked = {"c1", "c2", "c3", "c4", "c5"}
        interacted = {"c1", "c2", "c3"}
        assert _compute_coverage(linked, interacted) == pytest.approx(0.6)

    def test_no_linked_concepts(self):
        linked: set[str] = set()
        interacted = {"c1"}
        assert _compute_coverage(linked, interacted) == 0.0

    def test_extra_interactions_ignored(self):
        linked = {"c1", "c2"}
        interacted = {"c1", "c2", "c3", "c4"}
        assert _compute_coverage(linked, interacted) == 1.0


# ===================================================================
# Practice signal
# ===================================================================

class TestPracticeSignal:
    def test_all_correct(self):
        linked = {"c1", "c2"}
        correct = {"c1": 5, "c2": 3}
        total = {"c1": 5, "c2": 3}
        assert _compute_practice(linked, correct, total) == 1.0

    def test_mixed_results(self):
        linked = {"c1", "c2"}
        correct = {"c1": 7, "c2": 3}
        total = {"c1": 10, "c2": 10}
        # (0.7 + 0.3) / 2 = 0.5
        assert _compute_practice(linked, correct, total) == pytest.approx(0.5)

    def test_no_attempts(self):
        linked = {"c1", "c2", "c3"}
        assert _compute_practice(linked, {}, {}) == 0.0

    def test_some_concepts_no_attempts(self):
        linked = {"c1", "c2", "c3"}
        correct = {"c1": 8}
        total = {"c1": 10}
        # (0.8 + 0.0 + 0.0) / 3
        assert _compute_practice(linked, correct, total) == pytest.approx(0.8 / 3)

    def test_no_linked_concepts(self):
        assert _compute_practice(set(), {"c1": 5}, {"c1": 5}) == 0.0


# ===================================================================
# Freshness signal
# ===================================================================

class TestFreshnessSignal:
    def test_all_studied_today(self):
        linked = {"c1", "c2"}
        last = {"c1": NOW, "c2": NOW}
        assert _compute_freshness(linked, last, NOW) == 1.0

    def test_all_studied_10_days_ago(self):
        linked = {"c1", "c2"}
        ten_days_ago = NOW - timedelta(days=10)
        last = {"c1": ten_days_ago, "c2": ten_days_ago}
        assert _compute_freshness(linked, last, NOW) == pytest.approx(0.3)

    def test_never_studied(self):
        linked = {"c1", "c2"}
        assert _compute_freshness(linked, {}, NOW) == 0.0

    def test_mixed_recency(self):
        linked = {"c1", "c2"}
        last = {
            "c1": NOW,                          # 1.0
            "c2": NOW - timedelta(days=10),     # 0.3
        }
        assert _compute_freshness(linked, last, NOW) == pytest.approx(0.65)

    def test_no_linked_concepts(self):
        assert _compute_freshness(set(), {"c1": NOW}, NOW) == 0.0

    def test_very_old(self):
        linked = {"c1"}
        last = {"c1": NOW - timedelta(days=30)}
        assert _compute_freshness(linked, last, NOW) == pytest.approx(0.1)

    def test_1_day_ago(self):
        linked = {"c1"}
        last = {"c1": NOW - timedelta(days=1)}
        assert _compute_freshness(linked, last, NOW) == pytest.approx(0.9)

    def test_3_days_ago(self):
        linked = {"c1"}
        last = {"c1": NOW - timedelta(days=3)}
        assert _compute_freshness(linked, last, NOW) == pytest.approx(0.8)

    def test_7_days_ago(self):
        linked = {"c1"}
        last = {"c1": NOW - timedelta(days=7)}
        assert _compute_freshness(linked, last, NOW) == pytest.approx(0.5)

    def test_14_days_ago(self):
        linked = {"c1"}
        last = {"c1": NOW - timedelta(days=14)}
        assert _compute_freshness(linked, last, NOW) == pytest.approx(0.3)


# ===================================================================
# Effort signal
# ===================================================================

class TestEffortSignal:
    def test_exact_match(self):
        # 3 concepts → expected = ceil(3/3) = 1, 1 session → 1.0
        assert _compute_effort(1, 3) == 1.0

    def test_zero_sessions(self):
        assert _compute_effort(0, 6) == 0.0

    def test_capped_at_one(self):
        assert _compute_effort(10, 3) == 1.0

    def test_partial_effort(self):
        # 9 concepts → expected = ceil(9/3) = 3, 1 session → 1/3
        assert _compute_effort(1, 9) == pytest.approx(1 / 3)

    def test_zero_concepts(self):
        # 0 concepts → expected = max(1, 0) = 1
        assert _compute_effort(1, 0) == 1.0


# ===================================================================
# Composite readiness
# ===================================================================

class TestWeightedReadiness:
    def test_all_ones(self):
        b = ReadinessBreakdown(coverage=1.0, practice=1.0, freshness=1.0, effort=1.0)
        assert _weighted_readiness(b) == pytest.approx(1.0)

    def test_all_zeros(self):
        b = ReadinessBreakdown(coverage=0.0, practice=0.0, freshness=0.0, effort=0.0)
        assert _weighted_readiness(b) == 0.0

    def test_known_values(self):
        b = ReadinessBreakdown(coverage=0.6, practice=0.5, freshness=0.8, effort=0.4)
        expected = (
            COVERAGE_WEIGHT * 0.6
            + PRACTICE_WEIGHT * 0.5
            + FRESHNESS_WEIGHT * 0.8
            + EFFORT_WEIGHT * 0.4
        )
        assert _weighted_readiness(b) == pytest.approx(expected)

    def test_weights_sum_to_one(self):
        assert COVERAGE_WEIGHT + PRACTICE_WEIGHT + FRESHNESS_WEIGHT + EFFORT_WEIGHT == pytest.approx(1.0)


# ===================================================================
# Urgency classification
# ===================================================================

class TestUrgencyClassification:
    def test_critical(self):
        assert classify_urgency(2, 0.5) == "critical"

    def test_critical_boundary(self):
        assert classify_urgency(3, 0.69) == "critical"

    def test_high(self):
        assert classify_urgency(5, 0.6) == "high"

    def test_medium(self):
        assert classify_urgency(10, 0.5) == "medium"

    def test_low_far_out(self):
        assert classify_urgency(20, 0.9) == "low"

    def test_low_high_readiness(self):
        assert classify_urgency(5, 0.8) == "low"

    def test_none_days(self):
        assert classify_urgency(None, 0.3) == "low"

    def test_boundary_7_days_high_readiness(self):
        assert classify_urgency(7, 0.7) == "low"

    def test_boundary_14_days_low_readiness(self):
        assert classify_urgency(14, 0.59) == "medium"


# ===================================================================
# Integration: compute_assessment_readiness
# ===================================================================

def _build_supabase(
    assessment=None,
    course=None,
    links=None,
    learning_events=None,
    quiz_attempts=None,
    concepts=None,
    learn_sessions=None,
    tutor_sessions=None,
):
    """Build a mock supabase client with configurable table responses."""
    sb = MagicMock()

    table_data = {
        "assessments": assessment or [],
        "courses": course or [],
        "concept_assessment_links": links or [],
        "learning_events": learning_events or [],
        "quiz_attempts": quiz_attempts or [],
        "concepts": concepts or [],
        "learn_sessions": learn_sessions or [],
        "tutor_sessions": tutor_sessions or [],
    }

    def table_side_effect(name):
        return _mock_chain(table_data.get(name, []))

    sb.table.side_effect = table_side_effect
    return sb


@pytest.mark.asyncio
async def test_assessment_readiness_all_signals_perfect():
    """Student with perfect interactions across all concepts."""
    now_iso = NOW.isoformat()
    sb = _build_supabase(
        assessment=[{
            "id": "a1", "title": "Midterm 1", "due_date": None,
            "type": "midterm", "course_id": "course1",
        }],
        course=[{"name": "Physics 201"}],
        links=[{"concept_id": "c1"}, {"concept_id": "c2"}, {"concept_id": "c3"}],
        learning_events=[
            {"concept_id": "c1", "is_correct": True, "created_at": now_iso},
            {"concept_id": "c2", "is_correct": True, "created_at": now_iso},
            {"concept_id": "c3", "is_correct": True, "created_at": now_iso},
        ],
        quiz_attempts=[],
        concepts=[
            {"id": "c1", "title": "Newton's Laws"},
            {"id": "c2", "title": "Kinematics"},
            {"id": "c3", "title": "Energy"},
        ],
        learn_sessions=[
            {"id": "s1", "concepts_planned": [{"concept_id": "c1"}]},
        ],
        tutor_sessions=[],
    )

    result = await compute_assessment_readiness(sb, "user1", "a1")

    assert result.assessment_id == "a1"
    assert result.title == "Midterm 1"
    assert result.breakdown.coverage == 1.0
    assert result.breakdown.practice == 1.0
    assert result.breakdown.freshness == 1.0
    assert result.concept_count == 3
    assert result.covered_count == 3
    assert result.readiness == pytest.approx(
        COVERAGE_WEIGHT * 1.0 + PRACTICE_WEIGHT * 1.0
        + FRESHNESS_WEIGHT * 1.0 + EFFORT_WEIGHT * result.breakdown.effort,
        abs=0.01,
    )


@pytest.mark.asyncio
async def test_assessment_readiness_zero_interactions():
    """Student with no interactions at all."""
    sb = _build_supabase(
        assessment=[{
            "id": "a1", "title": "Final Exam", "due_date": None,
            "type": "exam", "course_id": "course1",
        }],
        course=[{"name": "Physics 201"}],
        links=[{"concept_id": "c1"}, {"concept_id": "c2"}],
        learning_events=[],
        quiz_attempts=[],
        concepts=[
            {"id": "c1", "title": "Concept 1"},
            {"id": "c2", "title": "Concept 2"},
        ],
        learn_sessions=[],
        tutor_sessions=[],
    )

    result = await compute_assessment_readiness(sb, "user1", "a1")

    assert result.readiness == 0.0
    assert result.breakdown.coverage == 0.0
    assert result.breakdown.practice == 0.0
    assert result.breakdown.freshness == 0.0
    assert result.breakdown.effort == 0.0
    assert result.concept_count == 2
    assert result.covered_count == 0


@pytest.mark.asyncio
async def test_assessment_readiness_no_linked_concepts():
    """Assessment with no concept links → all zeros."""
    sb = _build_supabase(
        assessment=[{
            "id": "a1", "title": "Pop Quiz", "due_date": None,
            "type": "quiz", "course_id": "course1",
        }],
        course=[{"name": "Chem 101"}],
        links=[],
        concepts=[],
    )

    result = await compute_assessment_readiness(sb, "user1", "a1")

    assert result.readiness == 0.0
    assert result.concept_count == 0
    assert result.covered_count == 0


@pytest.mark.asyncio
async def test_weak_concepts_sorted_ascending():
    """Weak concepts should be sorted by combined_score ascending."""
    now_iso = NOW.isoformat()
    old_iso = (NOW - timedelta(days=20)).isoformat()

    sb = _build_supabase(
        assessment=[{
            "id": "a1", "title": "Midterm", "due_date": None,
            "type": "midterm", "course_id": "course1",
        }],
        course=[{"name": "Physics"}],
        links=[{"concept_id": "c1"}, {"concept_id": "c2"}, {"concept_id": "c3"}],
        learning_events=[
            # c1: perfect, recent
            {"concept_id": "c1", "is_correct": True, "created_at": now_iso},
            # c2: bad accuracy, old
            {"concept_id": "c2", "is_correct": False, "created_at": old_iso},
            # c3: no events (weakest)
        ],
        quiz_attempts=[],
        concepts=[
            {"id": "c1", "title": "Strong Concept"},
            {"id": "c2", "title": "Medium Concept"},
            {"id": "c3", "title": "Weak Concept"},
        ],
        learn_sessions=[],
        tutor_sessions=[],
    )

    result = await compute_assessment_readiness(sb, "user1", "a1")

    assert len(result.weak_concepts) == 3
    # c3 (no interactions) should be weakest
    assert result.weak_concepts[0].concept_id == "c3"
    # Scores should be ascending
    scores = [w.combined_score for w in result.weak_concepts]
    assert scores == sorted(scores)


@pytest.mark.asyncio
async def test_suggested_actions_generated():
    """Actions should be generated for low signals."""
    sb = _build_supabase(
        assessment=[{
            "id": "a1", "title": "Exam", "due_date": None,
            "type": "exam", "course_id": "course1",
        }],
        course=[{"name": "Math"}],
        links=[{"concept_id": "c1"}, {"concept_id": "c2"}],
        learning_events=[],
        quiz_attempts=[],
        concepts=[
            {"id": "c1", "title": "Calculus"},
            {"id": "c2", "title": "Algebra"},
        ],
        learn_sessions=[],
        tutor_sessions=[],
    )

    result = await compute_assessment_readiness(sb, "user1", "a1")

    # All signals are 0, so all 4 action types should be generated
    action_types = {a.action_type for a in result.suggested_actions}
    assert "lecture_review" in action_types
    assert "practice_test" in action_types
    assert "flash_review" in action_types
    assert "study_session" in action_types


@pytest.mark.asyncio
async def test_assessment_readiness_with_due_date():
    """Verify days_until_due and urgency with a near due date."""
    near_future = (NOW + timedelta(days=2)).isoformat()
    sb = _build_supabase(
        assessment=[{
            "id": "a1", "title": "Quiz", "due_date": near_future,
            "type": "quiz", "course_id": "course1",
        }],
        course=[{"name": "Bio"}],
        links=[{"concept_id": "c1"}],
        learning_events=[],
        quiz_attempts=[],
        concepts=[{"id": "c1", "title": "Cells"}],
        learn_sessions=[],
        tutor_sessions=[],
    )

    result = await compute_assessment_readiness(sb, "user1", "a1")

    assert result.days_until_due is not None
    assert result.days_until_due <= 2
    # Readiness is 0, due in 2 days → critical
    assert result.urgency == "critical"


# ===================================================================
# Integration: compute_course_readiness
# ===================================================================

@pytest.mark.asyncio
async def test_course_readiness_no_assessments():
    """Course with no exam-type assessments."""
    sb = MagicMock()

    call_count = {"n": 0}

    def table_side_effect(name):
        call_count["n"] += 1
        if name == "courses":
            return _mock_chain([{"name": "Art 101", "code": "ART101"}])
        if name == "assessments":
            # Return only non-exam types
            return _mock_chain([
                {"id": "a1", "title": "Essay", "type": "assignment", "due_date": None},
            ])
        return _mock_chain([])

    sb.table.side_effect = table_side_effect

    result = await compute_course_readiness(sb, "user1", "course1")

    assert result.course_name == "Art 101"
    assert result.readiness == 0.0
    assert result.risk == "low"
    assert result.assessment_count == 0


@pytest.mark.asyncio
async def test_course_readiness_with_exams():
    """Course with exam-type assessments computes average readiness."""
    sb = MagicMock()

    def table_side_effect(name):
        if name == "courses":
            return _mock_chain([{"name": "Physics", "code": "PHYS201"}])
        if name == "assessments":
            return _mock_chain([
                {"id": "a1", "title": "Midterm", "type": "midterm", "due_date": None},
                {"id": "a2", "title": "Final", "type": "final", "due_date": None},
            ])
        if name == "concept_assessment_links":
            return _mock_chain([])  # No linked concepts → readiness = 0
        return _mock_chain([])

    sb.table.side_effect = table_side_effect

    result = await compute_course_readiness(sb, "user1", "course1")

    assert result.assessment_count == 2
    assert result.readiness == 0.0
    assert result.risk == "high"  # 0.0 < 0.4 → high


# ===================================================================
# Integration: get_all_course_readiness
# ===================================================================

@pytest.mark.asyncio
async def test_get_all_course_readiness_sorted_by_risk():
    """Courses should be sorted high → medium → low risk."""
    sb = MagicMock()

    call_index = {"n": 0}

    def table_side_effect(name):
        if name == "courses":
            call_index["n"] += 1
            if call_index["n"] == 1:
                # First call: list all courses
                return _mock_chain([
                    {"id": "c1"},
                    {"id": "c2"},
                ])
            # Subsequent calls: course details
            return _mock_chain([{"name": "Course", "code": "C"}])
        if name == "assessments":
            return _mock_chain([])  # No assessments → low risk
        return _mock_chain([])

    sb.table.side_effect = table_side_effect

    results = await get_all_course_readiness(sb, "user1")

    assert len(results) == 2
    # Both have 0 assessments → low risk, order doesn't matter but should not crash
    for r in results:
        assert r.risk == "low"


# ===================================================================
# EXAM_TYPES constant
# ===================================================================

class TestExamTypes:
    def test_expected_types(self):
        assert "exam" in EXAM_TYPES
        assert "midterm" in EXAM_TYPES
        assert "quiz" in EXAM_TYPES
        assert "test" in EXAM_TYPES
        assert "final" in EXAM_TYPES

    def test_assignment_not_exam(self):
        assert "assignment" not in EXAM_TYPES
        assert "project" not in EXAM_TYPES


# ===================================================================
# Edge cases
# ===================================================================

@pytest.mark.asyncio
async def test_quiz_attempts_contribute_to_signals():
    """Quiz attempts should contribute to coverage, practice, and freshness."""
    now_iso = NOW.isoformat()
    sb = _build_supabase(
        assessment=[{
            "id": "a1", "title": "Exam", "due_date": None,
            "type": "exam", "course_id": "course1",
        }],
        course=[{"name": "Math"}],
        links=[{"concept_id": "c1"}],
        learning_events=[],
        quiz_attempts=[
            {"concept_id": "c1", "is_correct": True, "created_at": now_iso},
            {"concept_id": "c1", "is_correct": False, "created_at": now_iso},
        ],
        concepts=[{"id": "c1", "title": "Algebra"}],
        learn_sessions=[],
        tutor_sessions=[],
    )

    result = await compute_assessment_readiness(sb, "user1", "a1")

    assert result.breakdown.coverage == 1.0
    assert result.breakdown.practice == pytest.approx(0.5)
    assert result.breakdown.freshness == 1.0


@pytest.mark.asyncio
async def test_effort_with_tutor_sessions():
    """Tutor sessions should contribute to effort signal."""
    sb = _build_supabase(
        assessment=[{
            "id": "a1", "title": "Exam", "due_date": None,
            "type": "exam", "course_id": "course1",
        }],
        course=[{"name": "Math"}],
        links=[{"concept_id": "c1"}, {"concept_id": "c2"}, {"concept_id": "c3"}],
        learning_events=[],
        quiz_attempts=[],
        concepts=[
            {"id": "c1", "title": "A"},
            {"id": "c2", "title": "B"},
            {"id": "c3", "title": "C"},
        ],
        learn_sessions=[],
        tutor_sessions=[
            {"id": "t1", "concept_id": "c1"},
        ],
    )

    result = await compute_assessment_readiness(sb, "user1", "a1")

    # 3 concepts → expected = ceil(3/3) = 1, 1 tutor session → effort = 1.0
    assert result.breakdown.effort == 1.0
