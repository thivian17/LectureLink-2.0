"""Tests for the dashboard actions service."""

from __future__ import annotations

from datetime import date, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from lecturelink_api.services.dashboard_actions import (
    get_academic_timeline,
    get_best_next_actions,
    get_weekly_stats,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

TODAY = date.today()


def _mock_execute(data=None):
    resp = MagicMock()
    resp.data = data or []
    return resp


def _mock_chain(final_data=None):
    chain = MagicMock()
    chain.execute.return_value = _mock_execute(final_data)
    for method in (
        "select", "insert", "update", "delete",
        "eq", "in_", "gte", "lte", "order", "limit",
    ):
        getattr(chain, method).return_value = chain
    return chain


def _make_supabase(
    *,
    courses=None,
    assessments=None,
    lectures=None,
    concepts=None,
    learning_events=None,
    concept_links=None,
    streak=None,
    xp_events=None,
    learn_sessions=None,
    tutor_sessions=None,
):
    """Build a mock supabase client with configurable table responses."""
    sb = MagicMock()

    table_responses = {
        "courses": courses,
        "assessments": assessments,
        "lectures": lectures,
        "concepts": concepts,
        "learning_events": learning_events,
        "concept_assessment_links": concept_links,
        "user_streaks": streak,
        "xp_events": xp_events,
        "learn_sessions": learn_sessions,
        "tutor_sessions": tutor_sessions,
    }

    def table_side_effect(name):
        data = table_responses.get(name)
        return _mock_chain(data)

    sb.table.side_effect = table_side_effect
    return sb


# ---------------------------------------------------------------------------
# Timeline Tests
# ---------------------------------------------------------------------------


class TestGetAcademicTimeline:
    """Tests for get_academic_timeline."""

    @pytest.mark.asyncio
    async def test_assessments_in_range_appear_sorted(self):
        """Two assessments within 14 days both appear sorted by date."""
        courses = [{"id": "c1", "name": "Math", "code": "MATH101"}]
        assessments = [
            {
                "id": "a1", "course_id": "c1", "title": "Quiz 1",
                "type": "quiz", "due_date": (TODAY + timedelta(days=5)).isoformat(),
                "weight_percent": 10,
            },
            {
                "id": "a2", "course_id": "c1", "title": "Midterm",
                "type": "midterm", "due_date": (TODAY + timedelta(days=10)).isoformat(),
                "weight_percent": 30,
            },
        ]
        sb = _make_supabase(
            courses=courses,
            assessments=assessments,
            concept_links=[],
            learning_events=[],
            lectures=[],
            concepts=[],
        )
        result = await get_academic_timeline(sb, "user1")

        assert len(result.items) == 2
        assert result.items[0].title == "Quiz 1"
        assert result.items[1].title == "Midterm"
        assert result.today == TODAY.isoformat()

    @pytest.mark.asyncio
    async def test_assessment_outside_range_excluded(self):
        """Assessment 20 days out should not appear in 14-day timeline."""
        courses = [{"id": "c1", "name": "Math", "code": "MATH101"}]
        # The assessment is 20 days out — supabase query filters by lte(future_iso)
        # so it won't be in results. We simulate this by not including it.
        sb = _make_supabase(
            courses=courses,
            assessments=[],
            lectures=[],
            concepts=[],
        )
        result = await get_academic_timeline(sb, "user1")
        assert len(result.items) == 0

    @pytest.mark.asyncio
    @patch("lecturelink_api.services.dashboard_actions.get_assessment_concepts", new_callable=AsyncMock)
    async def test_exam_type_has_readiness(self, mock_get_concepts):
        """Exam-type assessments should have a readiness score."""
        mock_get_concepts.return_value = [
            {"concept_id": "con1"},
            {"concept_id": "con2"},
        ]
        courses = [{"id": "c1", "name": "Math", "code": "MATH101"}]
        assessments = [
            {
                "id": "a1", "course_id": "c1", "title": "Final Exam",
                "type": "exam", "due_date": (TODAY + timedelta(days=7)).isoformat(),
                "weight_percent": 40,
            },
        ]
        learning_events = [{"concept_id": "con1"}]
        sb = _make_supabase(
            courses=courses,
            assessments=assessments,
            learning_events=learning_events,
            lectures=[],
            concepts=[],
        )
        result = await get_academic_timeline(sb, "user1")

        assert len(result.items) == 1
        item = result.items[0]
        assert item.readiness == 0.5  # 1 covered / 2 total
        assert item.urgency is not None

    @pytest.mark.asyncio
    async def test_non_exam_has_no_readiness(self):
        """Non-exam assessments (assignment, project) have readiness=None."""
        courses = [{"id": "c1", "name": "Math", "code": "MATH101"}]
        assessments = [
            {
                "id": "a1", "course_id": "c1", "title": "Homework 3",
                "type": "assignment", "due_date": (TODAY + timedelta(days=3)).isoformat(),
                "weight_percent": 5,
            },
        ]
        sb = _make_supabase(
            courses=courses,
            assessments=assessments,
            lectures=[],
            concepts=[],
        )
        result = await get_academic_timeline(sb, "user1")

        assert len(result.items) == 1
        assert result.items[0].readiness is None
        assert result.items[0].urgency is None

    @pytest.mark.asyncio
    async def test_lecture_needing_review_appears(self):
        """Lecture with no student interactions appears as needs_review."""
        courses = [{"id": "c1", "name": "Math", "code": "MATH101"}]
        lectures = [
            {
                "id": "l1", "course_id": "c1", "title": "Lecture 5",
                "lecture_date": TODAY.isoformat(), "lecture_number": 5,
            },
        ]
        concepts = [
            {"id": "con1", "lecture_id": "l1"},
            {"id": "con2", "lecture_id": "l1"},
        ]
        sb = _make_supabase(
            courses=courses,
            assessments=[],
            lectures=lectures,
            concepts=concepts,
            learning_events=[],
        )
        result = await get_academic_timeline(sb, "user1")

        quiz_items = [i for i in result.items if i.item_type == "practice_quiz"]
        assert len(quiz_items) == 1
        assert quiz_items[0].needs_review is True
        assert quiz_items[0].title == "Quiz: Lecture 5"

    @pytest.mark.asyncio
    async def test_lecture_with_interactions_excluded(self):
        """Lecture where student studied all concepts should not appear."""
        courses = [{"id": "c1", "name": "Math", "code": "MATH101"}]
        lectures = [
            {
                "id": "l1", "course_id": "c1", "title": "Lecture 5",
                "lecture_date": TODAY.isoformat(), "lecture_number": 5,
            },
        ]
        concepts = [{"id": "con1", "lecture_id": "l1"}]
        learning_events = [{"concept_id": "con1"}]
        sb = _make_supabase(
            courses=courses,
            assessments=[],
            lectures=lectures,
            concepts=concepts,
            learning_events=learning_events,
        )
        result = await get_academic_timeline(sb, "user1")

        quiz_items = [i for i in result.items if i.item_type == "practice_quiz"]
        assert len(quiz_items) == 0

    @pytest.mark.asyncio
    async def test_empty_courses_returns_empty(self):
        """User with no courses gets empty timeline with today's date."""
        sb = _make_supabase(courses=[])
        result = await get_academic_timeline(sb, "user1")

        assert result.items == []
        assert result.today == TODAY.isoformat()


# ---------------------------------------------------------------------------
# Best Next Actions Tests
# ---------------------------------------------------------------------------


class TestGetBestNextActions:
    """Tests for get_best_next_actions."""

    @pytest.mark.asyncio
    @patch("lecturelink_api.services.dashboard_actions.get_assessment_concepts", new_callable=AsyncMock)
    async def test_low_readiness_near_deadline_critical(self, mock_get_concepts):
        """Assessment in 3 days with low readiness → study_session with critical urgency."""
        mock_get_concepts.return_value = [
            {"concept_id": "con1"},
            {"concept_id": "con2"},
            {"concept_id": "con3"},
        ]
        courses = [{"id": "c1", "name": "Math", "code": "MATH101"}]
        assessments = [
            {
                "id": "a1", "course_id": "c1", "title": "Quiz 1",
                "type": "quiz", "due_date": (TODAY + timedelta(days=2)).isoformat(),
                "weight_percent": 20,
            },
        ]
        # No learning events → readiness = 0
        sb = _make_supabase(
            courses=courses,
            assessments=assessments,
            learning_events=[],
            lectures=[],
            concepts=[],
        )
        result = await get_best_next_actions(sb, "user1")

        assert len(result.actions) >= 1
        action = result.actions[0]
        assert action.action_type == "study_session"
        assert action.urgency == "critical"
        assert "Quiz 1" in action.title

    @pytest.mark.asyncio
    async def test_unreviewed_lecture_generates_quiz_action(self):
        """Unreviewed lecture → practice_test action prompting quiz."""
        courses = [{"id": "c1", "name": "Math", "code": "MATH101"}]
        lectures = [
            {
                "id": "l1", "course_id": "c1", "title": "Lecture 8",
                "lecture_date": TODAY.isoformat(), "lecture_number": 8,
            },
        ]
        concepts = [
            {"id": "con1", "lecture_id": "l1"},
            {"id": "con2", "lecture_id": "l1"},
        ]
        sb = _make_supabase(
            courses=courses,
            assessments=[],  # No exams
            lectures=lectures,
            concepts=concepts,
            learning_events=[],
            concept_links=[],
        )
        result = await get_best_next_actions(sb, "user1")

        quiz_actions = [a for a in result.actions if a.action_type == "practice_test"]
        assert len(quiz_actions) >= 1
        assert "Lecture 8" in quiz_actions[0].title

    @pytest.mark.asyncio
    @patch("lecturelink_api.services.dashboard_actions.get_assessment_concepts", new_callable=AsyncMock)
    async def test_high_readiness_skipped(self, mock_get_concepts):
        """Assessments with readiness >= 0.8 should not generate study_session actions."""
        mock_get_concepts.return_value = [
            {"concept_id": "con1"},
            {"concept_id": "con2"},
        ]
        courses = [{"id": "c1", "name": "Math", "code": "MATH101"}]
        assessments = [
            {
                "id": "a1", "course_id": "c1", "title": "Quiz 1",
                "type": "quiz", "due_date": (TODAY + timedelta(days=5)).isoformat(),
                "weight_percent": 10,
            },
        ]
        # Both concepts interacted → readiness = 1.0
        learning_events = [
            {"concept_id": "con1"},
            {"concept_id": "con2"},
        ]
        sb = _make_supabase(
            courses=courses,
            assessments=assessments,
            learning_events=learning_events,
            lectures=[],
            concepts=[],
        )
        result = await get_best_next_actions(sb, "user1")

        study_actions = [a for a in result.actions if a.action_type == "study_session"]
        assert len(study_actions) == 0

    @pytest.mark.asyncio
    @patch("lecturelink_api.services.dashboard_actions.get_assessment_concepts", new_callable=AsyncMock)
    async def test_actions_sorted_by_urgency(self, mock_get_concepts):
        """Actions should be sorted by priority (most urgent first)."""
        async def _side_effect(supabase, assessment_id, course_id, user_id):
            return [{"concept_id": f"con_{assessment_id}"}]
        mock_get_concepts.side_effect = _side_effect
        courses = [{"id": "c1", "name": "Math", "code": "MATH101"}]
        assessments = [
            {
                "id": "a1", "course_id": "c1", "title": "Far Quiz",
                "type": "quiz", "due_date": (TODAY + timedelta(days=13)).isoformat(),
                "weight_percent": 10,
            },
            {
                "id": "a2", "course_id": "c1", "title": "Near Exam",
                "type": "exam", "due_date": (TODAY + timedelta(days=2)).isoformat(),
                "weight_percent": 30,
            },
        ]
        sb = _make_supabase(
            courses=courses,
            assessments=assessments,
            learning_events=[],
            lectures=[],
            concepts=[],
        )
        result = await get_best_next_actions(sb, "user1")

        study_actions = [a for a in result.actions if a.action_type == "study_session"]
        assert len(study_actions) == 2
        # Near exam should come first (higher urgency_factor)
        assert "Near Exam" in study_actions[0].title

    @pytest.mark.asyncio
    @patch("lecturelink_api.services.dashboard_actions.get_assessment_concepts", new_callable=AsyncMock)
    async def test_respects_limit(self, mock_get_concepts):
        """Should return at most `limit` actions."""
        async def _side_effect(supabase, assessment_id, course_id, user_id):
            return [{"concept_id": f"con_{assessment_id}"}]
        mock_get_concepts.side_effect = _side_effect
        courses = [{"id": "c1", "name": "Math", "code": "MATH101"}]
        assessments = [
            {
                "id": f"a{i}", "course_id": "c1", "title": f"Quiz {i}",
                "type": "quiz",
                "due_date": (TODAY + timedelta(days=i + 1)).isoformat(),
                "weight_percent": 10,
            }
            for i in range(6)
        ]
        sb = _make_supabase(
            courses=courses,
            assessments=assessments,
            learning_events=[],
            lectures=[],
            concepts=[],
        )
        result = await get_best_next_actions(sb, "user1", limit=2)
        assert len(result.actions) <= 2


# ---------------------------------------------------------------------------
# Weekly Stats Tests
# ---------------------------------------------------------------------------


class TestGetWeeklyStats:
    """Tests for get_weekly_stats."""

    @pytest.mark.asyncio
    async def test_populated_stats(self):
        """User with streak, XP, sessions → all stats populated."""
        # 20-minute learn session represented by started_at/completed_at
        t0 = "2026-04-07T10:00:00+00:00"
        t1 = "2026-04-07T10:20:00+00:00"

        sb = _make_supabase(
            streak=[{"current_streak": 5}],
            xp_events=[{"amount": 100}, {"amount": 50}],
            learn_sessions=[{"started_at": t0, "completed_at": t1}],  # 20 min
            tutor_sessions=[{"duration_seconds": 600}],   # 10 min
        )

        # Override learning_events for concepts_practiced
        def table_side_effect(name):
            if name == "user_streaks":
                return _mock_chain([{"current_streak": 5}])
            if name == "xp_events":
                return _mock_chain([{"amount": 100}, {"amount": 50}])
            if name == "learn_sessions":
                return _mock_chain([{"started_at": t0, "completed_at": t1}])
            if name == "tutor_sessions":
                return _mock_chain([{"duration_seconds": 600}])
            if name == "learning_events":
                return _mock_chain([
                    {"concept_id": "c1"},
                    {"concept_id": "c2"},
                    {"concept_id": "c1"},  # duplicate
                ])
            return _mock_chain([])

        sb.table.side_effect = table_side_effect

        result = await get_weekly_stats(sb, "user1")

        assert result.streak == 5
        assert result.xp_this_week == 150
        assert result.study_minutes_this_week == 30  # 20 + 10
        assert result.concepts_practiced_this_week == 2  # distinct

    @pytest.mark.asyncio
    async def test_new_user_all_zeros(self):
        """New user with no data → all zeros."""
        sb = _make_supabase()

        result = await get_weekly_stats(sb, "user1")

        assert result.streak == 0
        assert result.xp_this_week == 0
        assert result.study_minutes_this_week == 0
        assert result.concepts_practiced_this_week == 0
