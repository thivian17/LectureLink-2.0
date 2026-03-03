"""Tests for the assessment readiness service."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
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
    for method in ("select", "eq", "is_", "in_", "order", "limit", "gte", "lte",
                    "single", "insert", "upsert", "update"):
        getattr(chain, method).return_value = chain
    return chain


# ===========================================================================
# Pure function tests
# ===========================================================================


class TestClassifyUrgency:
    def test_danger_band(self):
        from lecturelink_api.services.readiness import _classify_urgency
        assert _classify_urgency(0) == "danger"
        assert _classify_urgency(15) == "danger"
        assert _classify_urgency(29) == "danger"

    def test_building_band(self):
        from lecturelink_api.services.readiness import _classify_urgency
        assert _classify_urgency(30) == "building"
        assert _classify_urgency(45) == "building"
        assert _classify_urgency(59) == "building"

    def test_strong_band(self):
        from lecturelink_api.services.readiness import _classify_urgency
        assert _classify_urgency(60) == "strong"
        assert _classify_urgency(70) == "strong"
        assert _classify_urgency(79) == "strong"

    def test_ready_band(self):
        from lecturelink_api.services.readiness import _classify_urgency
        assert _classify_urgency(80) == "ready"
        assert _classify_urgency(100) == "ready"


class TestGradeLetter:
    def test_a_grades(self):
        from lecturelink_api.services.readiness import _grade_letter
        assert _grade_letter(95) == "A"
        assert _grade_letter(91) == "A-"

    def test_b_grades(self):
        from lecturelink_api.services.readiness import _grade_letter
        assert _grade_letter(88) == "B+"
        assert _grade_letter(85) == "B"
        assert _grade_letter(80) == "B-"

    def test_c_grades(self):
        from lecturelink_api.services.readiness import _grade_letter
        assert _grade_letter(78) == "C+"
        assert _grade_letter(75) == "C"
        assert _grade_letter(70) == "C-"

    def test_d_and_f(self):
        from lecturelink_api.services.readiness import _grade_letter
        assert _grade_letter(67) == "D+"
        assert _grade_letter(65) == "D"
        assert _grade_letter(50) == "F"


class TestDaysUntil:
    def test_future_date(self):
        from lecturelink_api.services.readiness import _days_until
        future = (datetime.now(timezone.utc) + timedelta(days=5)).isoformat()
        result = _days_until(future)
        assert result in (4, 5)  # allow for time-of-day rounding

    def test_past_date_returns_negative(self):
        from lecturelink_api.services.readiness import _days_until
        past = (datetime.now(timezone.utc) - timedelta(days=5)).isoformat()
        result = _days_until(past)
        assert result in (-5, -6)  # allow for time-of-day rounding

    def test_none_returns_none(self):
        from lecturelink_api.services.readiness import _days_until
        assert _days_until(None) is None


# ===========================================================================
# Async service tests
# ===========================================================================


def _setup_readiness_sb(
    assessment=None,
    links=None,
    mastery_rows=None,
    courses=None,
    assessments_list=None,
):
    """Create a mock supabase for readiness tests."""
    sb = MagicMock()

    table_data = {
        "assessments": assessment or [],
        "concept_assessment_links": links or [],
        "courses": courses or [{"id": "c1", "name": "Test Course"}],
    }

    def table_side_effect(name):
        return _mock_chain(table_data.get(name, []))

    sb.table.side_effect = table_side_effect

    # RPC for concept mastery
    rpc_mock = MagicMock()
    rpc_mock.execute.return_value = _mock_execute(mastery_rows or [])
    sb.rpc.return_value = rpc_mock

    return sb


class TestGetAssessmentReadiness:
    @pytest.mark.asyncio
    async def test_no_assessment_found(self):
        from lecturelink_api.services.readiness import get_assessment_readiness

        sb = _setup_readiness_sb(assessment=[])
        result = await get_assessment_readiness(sb, "user-1", "a-missing")
        assert result.get("error") == "not_found"

    @pytest.mark.asyncio
    async def test_no_linked_concepts(self):
        from lecturelink_api.services.readiness import get_assessment_readiness

        sb = _setup_readiness_sb(
            assessment=[{
                "id": "a1", "title": "Midterm", "due_date": None,
                "weight_percent": 30.0, "type": "exam", "course_id": "c1",
            }],
            links=[],
        )
        result = await get_assessment_readiness(sb, "user-1", "a1")
        assert result["readiness_score"] == 0.0
        assert result["urgency"] == "danger"

    @pytest.mark.asyncio
    async def test_weighted_average_calculation(self):
        from lecturelink_api.services.readiness import get_assessment_readiness

        sb = _setup_readiness_sb(
            assessment=[{
                "id": "a1", "title": "Midterm", "due_date": None,
                "weight_percent": 30.0, "type": "exam", "course_id": "c1",
            }],
            links=[
                {"concept_id": "c1", "relevance_score": 1.0},
                {"concept_id": "c2", "relevance_score": 0.5},
            ],
            mastery_rows=[
                {
                    "concept_id": "c1", "concept_title": "Topic A",
                    "total_attempts": 10, "accuracy": 0.8, "recent_accuracy": 0.9,
                },
                {
                    "concept_id": "c2", "concept_title": "Topic B",
                    "total_attempts": 5, "accuracy": 0.4, "recent_accuracy": 0.5,
                },
            ],
        )
        result = await get_assessment_readiness(sb, "user-1", "a1")

        # c1 mastery: 0.8*0.6 + 0.9*0.4 = 0.84, weight=1.0
        # c2 mastery: 0.4*0.6 + 0.5*0.4 = 0.44, weight=0.5
        # weighted avg: (0.84*1.0 + 0.44*0.5) / (1.0+0.5) = 1.06/1.5 = 0.7067
        # * 100 = 70.7%
        assert 70 <= result["readiness_score"] <= 71
        assert result["urgency"] == "strong"
        assert len(result["concept_scores"]) == 2


class TestGetAllAssessmentReadiness:
    @pytest.mark.asyncio
    async def test_returns_sorted_list(self):
        from lecturelink_api.services.readiness import get_all_assessment_readiness

        future = (datetime.now(timezone.utc) + timedelta(days=10)).isoformat()
        assessment_data = [
            {"id": "a1", "course_id": "c1", "title": "Midterm",
             "due_date": future, "weight_percent": 30.0, "type": "exam"},
            {"id": "a2", "course_id": "c1", "title": "Final",
             "due_date": future, "weight_percent": 50.0, "type": "exam"},
        ]
        sb = MagicMock()
        sb.table.side_effect = lambda name: _mock_chain(
            assessment_data if name == "assessments" else []
        )
        rpc_mock = MagicMock()
        rpc_mock.execute.return_value = _mock_execute([])
        sb.rpc.return_value = rpc_mock

        result = await get_all_assessment_readiness(sb, "user-1")
        assert isinstance(result, list)
        assert len(result) == 2


class TestGetCourseReadinessSummary:
    @pytest.mark.asyncio
    async def test_empty_course(self):
        from lecturelink_api.services.readiness import get_course_readiness_summary

        sb = _setup_readiness_sb(
            courses=[{"id": "c1", "name": "Physics 101"}],
            mastery_rows=[],
        )
        result = await get_course_readiness_summary(sb, "user-1", "c1")

        assert result["course_name"] == "Physics 101"
        assert result["overall_readiness"] == 0.0
        assert result["concepts_mastered"] == 0
        assert result["concepts_total"] == 0


class TestGetGradeProjection:
    @pytest.mark.asyncio
    async def test_completed_assessments_only(self):
        from lecturelink_api.services.readiness import get_grade_projection

        sb = _setup_readiness_sb(
            assessment=[
                {
                    "id": "a1", "title": "Midterm", "type": "exam",
                    "weight_percent": 30.0, "student_score": 85.0,
                    "completed": True, "due_date": None, "course_id": "c1",
                },
                {
                    "id": "a2", "title": "Final", "type": "exam",
                    "weight_percent": 70.0, "student_score": 90.0,
                    "completed": True, "due_date": None, "course_id": "c1",
                },
            ],
        )
        # Override table to return both assessments
        sb.table.side_effect = lambda name: _mock_chain(
            [
                {
                    "id": "a1", "title": "Midterm", "type": "exam",
                    "weight_percent": 30.0, "student_score": 85.0,
                    "completed": True, "due_date": None, "course_id": "c1",
                },
                {
                    "id": "a2", "title": "Final", "type": "exam",
                    "weight_percent": 70.0, "student_score": 90.0,
                    "completed": True, "due_date": None, "course_id": "c1",
                },
            ]
            if name == "assessments"
            else []
        )
        rpc_mock = MagicMock()
        rpc_mock.execute.return_value = _mock_execute([])
        sb.rpc.return_value = rpc_mock

        result = await get_grade_projection(sb, "user-1", "c1")

        # Weighted: (85*30 + 90*70) / 100 = 88.5
        assert 83 <= result["projected_grade_low"] <= 84
        assert 93 <= result["projected_grade_high"] <= 94
        assert result["grade_letter"] == "B+"
        assert len(result["completed_assessments"]) == 2

    @pytest.mark.asyncio
    async def test_no_assessments(self):
        from lecturelink_api.services.readiness import get_grade_projection

        sb = _setup_readiness_sb(assessment=[])
        sb.table.side_effect = lambda name: _mock_chain([])
        rpc_mock = MagicMock()
        rpc_mock.execute.return_value = _mock_execute([])
        sb.rpc.return_value = rpc_mock

        result = await get_grade_projection(sb, "user-1", "c1")

        assert result["projected_grade_low"] == 0.0
        assert result["grade_letter"] == "F"
