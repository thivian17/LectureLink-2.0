"""Tests for the onboarding service and router."""

from __future__ import annotations

from datetime import date, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from lecturelink_api.services.onboarding import (
    generate_lecture_checklist,
    generate_personalized_message,
    get_semester_progress,
    seed_mastery_from_scores,
    suggest_onboarding_path,
)

# ──────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────


def _mock_execute(data):
    resp = MagicMock()
    resp.data = data
    resp.count = 0
    return resp


def _mock_chain(final_data):
    """Return a mock that supports chained Supabase query builder calls."""
    chain = MagicMock()
    chain.execute.return_value = _mock_execute(final_data)
    for method in (
        "select", "insert", "update", "delete", "upsert",
        "eq", "in_", "order", "limit", "single", "maybe_single",
        "not_",
    ):
        getattr(chain, method).return_value = chain
    # Handle not_.is_() chaining
    chain.not_.is_.return_value = chain
    return chain


# ──────────────────────────────────────────────────────────────────────
# suggest_onboarding_path
# ──────────────────────────────────────────────────────────────────────


class TestSuggestOnboardingPath:
    """Tests for suggest_onboarding_path()."""

    def test_none_dates_returns_mid_semester(self):
        assert suggest_onboarding_path(None, None) == "mid_semester"

    def test_none_start_returns_mid_semester(self):
        assert suggest_onboarding_path(None, date.today()) == "mid_semester"

    def test_none_end_returns_mid_semester(self):
        assert suggest_onboarding_path(date.today(), None) == "mid_semester"

    def test_today_before_start_returns_just_starting(self):
        future = date.today() + timedelta(days=30)
        end = future + timedelta(days=120)
        assert suggest_onboarding_path(future, end) == "just_starting"

    def test_today_equals_start_returns_just_starting(self):
        today = date.today()
        end = today + timedelta(days=120)
        assert suggest_onboarding_path(today, end) == "just_starting"

    def test_today_past_end_returns_course_complete(self):
        start = date.today() - timedelta(days=150)
        end = date.today() - timedelta(days=10)
        assert suggest_onboarding_path(start, end) == "course_complete"

    def test_mid_semester_detection(self):
        # 50% through the semester
        start = date.today() - timedelta(days=60)
        end = date.today() + timedelta(days=60)
        assert suggest_onboarding_path(start, end) == "mid_semester"

    def test_early_semester_under_15pct(self):
        # 10% through = just_starting
        start = date.today() - timedelta(days=10)
        end = start + timedelta(days=100)
        assert suggest_onboarding_path(start, end) == "just_starting"

    def test_late_semester_over_95pct(self):
        # 97% through = course_complete
        start = date.today() - timedelta(days=97)
        end = start + timedelta(days=100)
        assert suggest_onboarding_path(start, end) == "course_complete"

    def test_zero_total_days_returns_just_starting(self):
        today = date.today()
        assert suggest_onboarding_path(today, today) == "just_starting"

    def test_string_dates_accepted(self):
        start = (date.today() - timedelta(days=50)).isoformat()
        end = (date.today() + timedelta(days=50)).isoformat()
        assert suggest_onboarding_path(start, end) == "mid_semester"


# ──────────────────────────────────────────────────────────────────────
# get_semester_progress
# ──────────────────────────────────────────────────────────────────────


class TestGetSemesterProgress:
    """Tests for get_semester_progress()."""

    def test_not_started(self):
        course = {
            "semester_start": (date.today() + timedelta(days=30)).isoformat(),
            "semester_end": (date.today() + timedelta(days=150)).isoformat(),
            "meeting_days": ["monday", "wednesday"],
        }
        result = get_semester_progress(course)
        assert result["status"] == "not_started"
        assert result["progress_pct"] == 0
        assert result["weeks_elapsed"] == 0
        assert result["estimated_lectures_passed"] == 0
        assert result["days_remaining"] == 120

    def test_complete(self):
        course = {
            "semester_start": (date.today() - timedelta(days=120)).isoformat(),
            "semester_end": (date.today() - timedelta(days=1)).isoformat(),
            "meeting_days": ["tuesday", "thursday"],
        }
        result = get_semester_progress(course)
        assert result["status"] == "complete"
        assert result["progress_pct"] == 100
        assert result["days_remaining"] == 0
        assert result["estimated_lectures_passed"] > 0

    def test_in_progress(self):
        course = {
            "semester_start": (date.today() - timedelta(days=30)).isoformat(),
            "semester_end": (date.today() + timedelta(days=90)).isoformat(),
            "meeting_days": ["monday", "wednesday", "friday"],
        }
        result = get_semester_progress(course)
        assert result["status"] == "in_progress"
        assert 0 < result["progress_pct"] < 100
        assert result["weeks_elapsed"] >= 0
        assert result["days_remaining"] == 90

    def test_missing_meeting_days_defaults_to_2(self):
        course = {
            "semester_start": (date.today() - timedelta(days=14)).isoformat(),
            "semester_end": (date.today() + timedelta(days=86)).isoformat(),
            "meeting_days": None,
        }
        result = get_semester_progress(course)
        assert result["status"] == "in_progress"
        # 14 days = 2 weeks, 2 lectures/week default = 4
        assert result["estimated_lectures_passed"] == 4

    def test_none_dates(self):
        result = get_semester_progress({})
        assert result["status"] == "in_progress"
        assert result["progress_pct"] == 50


# ──────────────────────────────────────────────────────────────────────
# generate_lecture_checklist
# ──────────────────────────────────────────────────────────────────────


class TestGenerateLectureChecklist:
    """Tests for generate_lecture_checklist()."""

    def test_basic_two_days_four_weeks(self):
        start = date.today() - timedelta(days=28)
        end = date.today() + timedelta(days=60)
        course = {
            "semester_start": start.isoformat(),
            "semester_end": end.isoformat(),
            "meeting_days": ["monday", "wednesday"],
        }
        checklist = generate_lecture_checklist(course)
        assert len(checklist) > 0
        assert checklist[0]["lecture_number"] == 1
        assert checklist[0]["status"] == "pending"
        # All dates should be <= today
        for item in checklist:
            assert item["expected_date"] <= date.today().isoformat()
            assert item["day_of_week"] in ("monday", "wednesday")

    def test_holidays_skipped(self):
        start = date.today() - timedelta(days=28)
        end = date.today() + timedelta(days=60)

        # Find the next monday from start
        d = start
        while d.weekday() != 0:
            d += timedelta(days=1)
        holiday_monday = d

        course = {
            "semester_start": start.isoformat(),
            "semester_end": end.isoformat(),
            "meeting_days": ["monday", "wednesday"],
        }
        holidays = [{
            "name": "Test Holiday",
            "start_date": holiday_monday.isoformat(),
            "end_date": holiday_monday.isoformat(),
        }]

        checklist_with = generate_lecture_checklist(
            course, holidays=holidays,
        )
        checklist_without = generate_lecture_checklist(course)

        # Should have one fewer lecture with the holiday
        assert len(checklist_with) == len(checklist_without) - 1

    def test_weekly_schedule_topic_hints(self):
        start = date.today() - timedelta(days=14)
        end = date.today() + timedelta(days=60)
        course = {
            "semester_start": start.isoformat(),
            "semester_end": end.isoformat(),
            "meeting_days": ["tuesday"],
        }
        weekly_schedule = [
            {"week_number": 1, "topics": ["Intro to Algorithms"]},
            {"week_number": 2, "topics": ["Sorting"]},
            {"week_number": 3, "topics": ["Graph Theory"]},
        ]
        checklist = generate_lecture_checklist(
            course, syllabus_weekly_schedule=weekly_schedule,
        )
        # Check that at least some items have topic hints
        hints = [item["topic_hint"] for item in checklist if item["topic_hint"]]
        assert len(hints) > 0

    def test_empty_meeting_days(self):
        course = {
            "semester_start": (date.today() - timedelta(days=14)).isoformat(),
            "semester_end": (date.today() + timedelta(days=60)).isoformat(),
            "meeting_days": [],
        }
        assert generate_lecture_checklist(course) == []

    def test_none_dates_returns_empty(self):
        assert generate_lecture_checklist({}) == []

    def test_break_weeks_skipped_from_schedule(self):
        """Weeks labeled as reading week / break in the syllabus schedule
        should not generate lecture slots."""
        start = date(2026, 1, 5)  # a Monday
        course = {
            "semester_start": start.isoformat(),
            "semester_end": "2026-05-01",
            "meeting_days": ["Mon", "Wed"],
        }
        schedule = [
            {"week_number": 1, "topics": ["Intro"]},
            {"week_number": 2, "topics": ["Reading Week"]},
            {"week_number": 3, "topics": ["Chapter 2"]},
        ]
        checklist = generate_lecture_checklist(
            course, syllabus_weekly_schedule=schedule,
        )
        week_numbers = {item["week_number"] for item in checklist}
        assert 2 not in week_numbers, "Reading week should be skipped"
        assert 1 in week_numbers
        assert 3 in week_numbers

    def test_break_keyword_no_false_positive_on_breakdowns(self):
        """'Showing Breakdowns of the Whole' should NOT trigger break detection."""
        start = date(2026, 1, 5)  # a Monday
        course = {
            "semester_start": start.isoformat(),
            "semester_end": "2026-05-01",
            "meeting_days": ["Wed"],
        }
        schedule = [
            {"week_number": 6, "topics": [
                "Data Modelling Fundamentals",
                "Showing Breakdowns of the Whole",
            ]},
        ]
        checklist = generate_lecture_checklist(
            course, syllabus_weekly_schedule=schedule,
        )
        week_numbers = {item["week_number"] for item in checklist}
        assert 6 in week_numbers, "Week 6 should NOT be skipped (Breakdowns != break)"

    def test_end_date_caps_at_today(self):
        start = date.today() - timedelta(days=7)
        # Semester end is way in the future
        end = date.today() + timedelta(days=200)
        course = {
            "semester_start": start.isoformat(),
            "semester_end": end.isoformat(),
            "meeting_days": ["monday", "tuesday", "wednesday",
                             "thursday", "friday"],
        }
        checklist = generate_lecture_checklist(course)
        for item in checklist:
            assert item["expected_date"] <= date.today().isoformat()


# ──────────────────────────────────────────────────────────────────────
# generate_personalized_message
# ──────────────────────────────────────────────────────────────────────


class TestGeneratePersonalizedMessage:
    """Tests for generate_personalized_message()."""

    @pytest.mark.asyncio
    async def test_calls_gemini_and_returns_text(self):
        mock_response = MagicMock()
        mock_response.text = "Welcome to CS101. Your midterm is in 14 days."

        mock_aio = MagicMock()
        mock_aio.models.generate_content = AsyncMock(
            return_value=mock_response,
        )
        mock_client = MagicMock()
        mock_client.aio = mock_aio

        course = {
            "name": "CS101",
            "code": "CS101",
            "semester_start": "2025-01-15",
            "semester_end": "2025-05-15",
            "meeting_days": ["monday", "wednesday"],
        }
        assessments = [
            {
                "title": "Midterm",
                "weight_percent": 30,
                "due_date": "2025-03-15T00:00:00+00:00",
            },
            {
                "title": "Final",
                "weight_percent": 40,
                "due_date": "2025-05-10T00:00:00+00:00",
            },
        ]

        with patch(
            "lecturelink_api.services.onboarding._get_client",
            return_value=mock_client,
        ):
            result = await generate_personalized_message(
                course=course,
                assessments=assessments,
                onboarding_path="mid_semester",
                semester_progress={"progress_pct": 50, "weeks_elapsed": 8,
                                   "estimated_lectures_passed": 16},
                student_name="Alice",
            )

        assert result == "Welcome to CS101. Your midterm is in 14 days."
        mock_aio.models.generate_content.assert_called_once()

        call_kwargs = mock_aio.models.generate_content.call_args
        assert "gemini" in call_kwargs.kwargs.get("model", "")

    @pytest.mark.asyncio
    async def test_handles_none_student_name(self):
        mock_response = MagicMock()
        mock_response.text = "Hello Student."

        mock_aio = MagicMock()
        mock_aio.models.generate_content = AsyncMock(
            return_value=mock_response,
        )
        mock_client = MagicMock()
        mock_client.aio = mock_aio

        course = {
            "name": "BIO200",
            "code": None,
            "semester_start": "2025-01-15",
            "semester_end": "2025-05-15",
            "meeting_days": [],
        }

        with patch(
            "lecturelink_api.services.onboarding._get_client",
            return_value=mock_client,
        ):
            result = await generate_personalized_message(
                course=course,
                assessments=[],
                onboarding_path="just_starting",
            )

        assert result == "Hello Student."


# ──────────────────────────────────────────────────────────────────────
# seed_mastery_from_scores
# ──────────────────────────────────────────────────────────────────────


class TestSeedMasteryFromScores:
    """Tests for seed_mastery_from_scores()."""

    @pytest.mark.asyncio
    async def test_seeds_scores_from_assessments(self):
        sb = MagicMock()

        # assessments query returns 1 assessment with a score
        assess_chain = _mock_chain([
            {"id": "a1", "student_score": 85.0},
        ])
        # concept links query returns 2 concepts
        links_chain = _mock_chain([
            {"concept_id": "c1", "assessment_id": "a1"},
            {"concept_id": "c2", "assessment_id": "a1"},
        ])
        # upsert chain
        upsert_chain = _mock_chain([])

        def table_dispatch(name):
            if name == "assessments":
                return assess_chain
            if name == "concept_assessment_links":
                return links_chain
            if name == "mastery_scores":
                return upsert_chain
            return _mock_chain([])

        sb.table.side_effect = table_dispatch

        count = await seed_mastery_from_scores(sb, "course1", "user1")
        assert count == 2

    @pytest.mark.asyncio
    async def test_returns_zero_when_no_scores(self):
        sb = MagicMock()
        sb.table.return_value = _mock_chain([])

        count = await seed_mastery_from_scores(sb, "course1", "user1")
        assert count == 0

    @pytest.mark.asyncio
    async def test_handles_missing_mastery_table(self):
        sb = MagicMock()

        assess_chain = _mock_chain([
            {"id": "a1", "student_score": 75.0},
        ])
        links_chain = _mock_chain([{"concept_id": "c1", "assessment_id": "a1"}])

        # mastery_scores upsert raises an error (table doesn't exist)
        upsert_chain = MagicMock()
        upsert_chain.upsert.side_effect = Exception("relation does not exist")

        def table_dispatch(name):
            if name == "assessments":
                return assess_chain
            if name == "concept_assessment_links":
                return links_chain
            if name == "mastery_scores":
                return upsert_chain
            return _mock_chain([])

        sb.table.side_effect = table_dispatch

        count = await seed_mastery_from_scores(sb, "course1", "user1")
        assert count == 0

    @pytest.mark.asyncio
    async def test_score_normalization_clamps(self):
        """Scores get clamped to [0.1, 0.95]."""
        sb = MagicMock()

        assess_chain = _mock_chain([
            {"id": "a1", "student_score": 100.0},  # → 1.0 → clamped to 0.95
            {"id": "a2", "student_score": 5.0},    # → 0.05 → clamped to 0.1
        ])
        links_chain = _mock_chain([
            {"concept_id": "c1", "assessment_id": "a1"},
            {"concept_id": "c1", "assessment_id": "a2"},
        ])
        upsert_chain = _mock_chain([])

        def table_dispatch(name):
            if name == "assessments":
                return assess_chain
            if name == "concept_assessment_links":
                return links_chain
            if name == "mastery_scores":
                return upsert_chain
            return _mock_chain([])

        sb.table.side_effect = table_dispatch

        count = await seed_mastery_from_scores(sb, "course1", "user1")
        # 2 assessments × 1 concept each = 2 upserts
        assert count == 2


# ──────────────────────────────────────────────────────────────────────
# Router tests
# ──────────────────────────────────────────────────────────────────────


class TestOnboardingRouter:
    """Integration tests for onboarding API endpoints."""

    def _make_sb(self, course_data=None, extra_tables=None):
        """Build a mock Supabase client."""
        sb = MagicMock()

        default_course = {
            "id": "course-1",
            "user_id": "user-1",
            "name": "CS101",
            "code": "CS101",
            "semester_start": "2025-01-15",
            "semester_end": "2025-05-15",
            "meeting_days": ["monday", "wednesday"],
            "holidays": [],
            "onboarding_path": None,
            "onboarding_step": None,
            "onboarding_completed_at": None,
            "onboarding_welcome": None,
            "mode": "active",
        }
        if course_data:
            default_course.update(course_data)

        tables = {
            "courses": [default_course],
            "user_onboarding": [],
            "assessments": [],
            "syllabi": [],
            "profiles": [{"full_name": "Test User"}],
            **(extra_tables or {}),
        }

        def table_dispatch(name):
            data = tables.get(name, [])
            return _mock_chain(data)

        sb.table.side_effect = table_dispatch
        return sb, default_course

    @pytest.mark.asyncio
    async def test_start_onboarding(self):
        from lecturelink_api.routers.onboarding import start_onboarding

        sb, _ = self._make_sb()

        with patch(
            "lecturelink_api.routers.onboarding.get_authenticated_supabase", return_value=sb,
        ):
            result = await start_onboarding(
                course_id="course-1",
                user={"id": "user-1", "token": "tok", "email": "a@b.com"},
                settings=MagicMock(),
            )

        assert result["status"] == "started"
        assert result["step"] == "syllabus_upload"

    @pytest.mark.asyncio
    async def test_start_onboarding_rejects_completed(self):
        from lecturelink_api.routers.onboarding import start_onboarding

        sb, _ = self._make_sb({"onboarding_completed_at": "2025-03-01T00:00:00"})

        with (
            patch("lecturelink_api.routers.onboarding.get_authenticated_supabase", return_value=sb),
            pytest.raises(Exception) as exc_info,
        ):
            await start_onboarding(
                course_id="course-1",
                user={"id": "user-1", "token": "tok", "email": "a@b.com"},
                settings=MagicMock(),
            )

        assert exc_info.value.status_code == 409

    @pytest.mark.asyncio
    async def test_get_onboarding_status(self):
        from lecturelink_api.routers.onboarding import get_onboarding_status

        sb, _ = self._make_sb({
            "onboarding_path": "mid_semester",
            "onboarding_step": "syllabus_upload",
        })

        with patch(
            "lecturelink_api.routers.onboarding.get_authenticated_supabase", return_value=sb,
        ):
            result = await get_onboarding_status(
                course_id="course-1",
                user={"id": "user-1", "token": "tok", "email": "a@b.com"},
                settings=MagicMock(),
            )

        assert result["path"] == "mid_semester"
        assert result["step"] == "syllabus_upload"

    @pytest.mark.asyncio
    async def test_set_path_course_complete_sets_review_mode(self):
        from lecturelink_api.models.api_models import SetPathRequest
        from lecturelink_api.routers.onboarding import set_path

        sb, _ = self._make_sb()

        with patch(
            "lecturelink_api.routers.onboarding.get_authenticated_supabase", return_value=sb,
        ):
            result = await set_path(
                course_id="course-1",
                body=SetPathRequest(path="course_complete"),
                user={"id": "user-1", "token": "tok", "email": "a@b.com"},
                settings=MagicMock(),
            )

        assert result["path"] == "course_complete"
        assert result["mode"] == "review"

    @pytest.mark.asyncio
    async def test_update_step_rejects_invalid(self):
        from lecturelink_api.models.api_models import StepUpdateRequest
        from lecturelink_api.routers.onboarding import update_step

        sb, _ = self._make_sb()

        with (
            patch("lecturelink_api.routers.onboarding.get_authenticated_supabase", return_value=sb),
            pytest.raises(Exception) as exc_info,
        ):
            await update_step(
                course_id="course-1",
                body=StepUpdateRequest(step="invalid_step"),
                user={"id": "user-1", "token": "tok", "email": "a@b.com"},
                settings=MagicMock(),
            )

        assert exc_info.value.status_code == 400

    @pytest.mark.asyncio
    async def test_update_step_valid(self):
        from lecturelink_api.models.api_models import StepUpdateRequest
        from lecturelink_api.routers.onboarding import update_step

        sb, _ = self._make_sb({
            "onboarding_path": "mid_semester",
            "onboarding_step": "past_results",
        })

        with patch(
            "lecturelink_api.routers.onboarding.get_authenticated_supabase", return_value=sb,
        ):
            result = await update_step(
                course_id="course-1",
                body=StepUpdateRequest(step="past_results"),
                user={"id": "user-1", "token": "tok", "email": "a@b.com"},
                settings=MagicMock(),
            )

        assert result["step"] == "past_results"

    @pytest.mark.asyncio
    async def test_suggest_path_endpoint(self):
        from lecturelink_api.routers.onboarding import get_suggested_path

        sb, _ = self._make_sb()

        with patch(
            "lecturelink_api.routers.onboarding.get_authenticated_supabase", return_value=sb,
        ):
            result = await get_suggested_path(
                course_id="course-1",
                user={"id": "user-1", "token": "tok", "email": "a@b.com"},
                settings=MagicMock(),
            )

        assert "suggested_path" in result
        assert "progress_pct" in result

    @pytest.mark.asyncio
    async def test_complete_onboarding(self):
        from lecturelink_api.routers.onboarding import complete_onboarding

        sb, _ = self._make_sb({"onboarding_path": "just_starting"})

        with patch(
            "lecturelink_api.routers.onboarding.get_authenticated_supabase", return_value=sb,
        ):
            result = await complete_onboarding(
                course_id="course-1",
                user={"id": "user-1", "token": "tok", "email": "a@b.com"},
                settings=MagicMock(),
            )

        assert "completed_at" in result
        assert result["mastery_scores_seeded"] == 0

    @pytest.mark.asyncio
    async def test_complete_onboarding_mid_semester_seeds(self):
        from lecturelink_api.routers.onboarding import complete_onboarding

        sb, _ = self._make_sb({"onboarding_path": "mid_semester"})

        with (
            patch("lecturelink_api.routers.onboarding.get_authenticated_supabase", return_value=sb),
            patch(
                "lecturelink_api.routers.onboarding.seed_mastery_from_scores",
                new_callable=AsyncMock,
                return_value=5,
            ),
        ):
            result = await complete_onboarding(
                course_id="course-1",
                user={"id": "user-1", "token": "tok", "email": "a@b.com"},
                settings=MagicMock(),
            )

        assert result["mastery_scores_seeded"] == 5

    @pytest.mark.asyncio
    async def test_personalized_message_returns_cached(self):
        from lecturelink_api.routers.onboarding import get_personalized_message

        cached = {
            "message": "Cached msg",
            "generated_at": "2025-03-01T00:00:00",
            "path": "mid_semester",
        }
        sb, _ = self._make_sb({
            "onboarding_path": "mid_semester",
            "onboarding_welcome": cached,
        })

        with patch(
            "lecturelink_api.routers.onboarding.get_authenticated_supabase", return_value=sb,
        ):
            result = await get_personalized_message(
                course_id="course-1",
                body=None,
                user={"id": "user-1", "token": "tok", "email": "a@b.com"},
                settings=MagicMock(),
            )

        assert result == cached

    @pytest.mark.asyncio
    async def test_lecture_checklist_endpoint(self):
        from lecturelink_api.routers.onboarding import get_lecture_checklist

        today = date.today()
        sb, _ = self._make_sb({
            "semester_start": (today - timedelta(days=14)).isoformat(),
            "semester_end": (today + timedelta(days=60)).isoformat(),
            "meeting_days": ["tuesday", "thursday"],
        })

        with patch(
            "lecturelink_api.routers.onboarding.get_authenticated_supabase", return_value=sb,
        ):
            result = await get_lecture_checklist(
                course_id="course-1",
                user={"id": "user-1", "token": "tok", "email": "a@b.com"},
                settings=MagicMock(),
            )

        assert isinstance(result, list)
        assert len(result) > 0
        assert result[0]["lecture_number"] == 1

    @pytest.mark.asyncio
    async def test_semester_progress_endpoint(self):
        from lecturelink_api.routers.onboarding import (
            get_semester_progress_endpoint,
        )

        today = date.today()
        sb, _ = self._make_sb({
            "semester_start": (today - timedelta(days=30)).isoformat(),
            "semester_end": (today + timedelta(days=90)).isoformat(),
        })

        with patch(
            "lecturelink_api.routers.onboarding.get_authenticated_supabase", return_value=sb,
        ):
            result = await get_semester_progress_endpoint(
                course_id="course-1",
                user={"id": "user-1", "token": "tok", "email": "a@b.com"},
                settings=MagicMock(),
            )

        assert result["status"] == "in_progress"
        assert "past_assessments" in result
        assert "upcoming_assessments" in result

    @pytest.mark.asyncio
    async def test_update_lecture_checklist_item(self):
        from lecturelink_api.routers.onboarding import update_lecture_checklist_item
        from lecturelink_api.models.api_models import LectureChecklistUpdate

        today = date.today()
        sb, _ = self._make_sb({
            "semester_start": (today - timedelta(days=14)).isoformat(),
            "semester_end": (today + timedelta(days=60)).isoformat(),
            "meeting_days": ["tuesday", "thursday"],
        })

        with patch(
            "lecturelink_api.routers.onboarding.get_authenticated_supabase", return_value=sb,
        ):
            result = await update_lecture_checklist_item(
                course_id="course-1",
                lecture_number=1,
                body=LectureChecklistUpdate(
                    lecture_number=1,
                    title="Intro to Algorithms",
                    description="Big-O notation basics",
                ),
                user={"id": "user-1", "token": "tok", "email": "a@b.com"},
                settings=MagicMock(),
            )

        assert result.lecture_number == 1
        assert result.topic_hint == "Intro to Algorithms"
        # Verify correction was stored
        sb.table.assert_any_call("lecture_schedule_corrections")

    @pytest.mark.asyncio
    async def test_update_lecture_checklist_item_not_found(self):
        from fastapi import HTTPException
        from lecturelink_api.routers.onboarding import update_lecture_checklist_item
        from lecturelink_api.models.api_models import LectureChecklistUpdate

        today = date.today()
        sb, _ = self._make_sb({
            "semester_start": (today - timedelta(days=14)).isoformat(),
            "semester_end": (today + timedelta(days=60)).isoformat(),
            "meeting_days": ["tuesday", "thursday"],
        })

        with patch(
            "lecturelink_api.routers.onboarding.get_authenticated_supabase", return_value=sb,
        ):
            with pytest.raises(HTTPException) as exc_info:
                await update_lecture_checklist_item(
                    course_id="course-1",
                    lecture_number=999,
                    body=LectureChecklistUpdate(lecture_number=999),
                    user={"id": "user-1", "token": "tok", "email": "a@b.com"},
                    settings=MagicMock(),
                )
            assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_add_lecture_checklist_item(self):
        from lecturelink_api.routers.onboarding import add_lecture_checklist_item
        from lecturelink_api.models.api_models import LectureChecklistAdd

        today = date.today()
        sb, _ = self._make_sb({
            "semester_start": (today - timedelta(days=14)).isoformat(),
            "semester_end": (today + timedelta(days=60)).isoformat(),
            "meeting_days": ["tuesday", "thursday"],
            "holidays": [],
        }, extra_tables={
            "lecture_schedule_corrections": [],
        })

        with patch(
            "lecturelink_api.routers.onboarding.get_authenticated_supabase", return_value=sb,
        ):
            result = await add_lecture_checklist_item(
                course_id="course-1",
                body=LectureChecklistAdd(
                    title="Guest Lecture",
                    lecture_date=today,
                    description="AI Ethics panel",
                ),
                user={"id": "user-1", "token": "tok", "email": "a@b.com"},
                settings=MagicMock(),
            )

        assert result.lecture_number > 0
        assert result.is_user_added is True
        assert result.topic_hint == "Guest Lecture"
        sb.table.assert_any_call("lecture_schedule_corrections")

    @pytest.mark.asyncio
    async def test_lecture_checklist_includes_user_added(self):
        """GET checklist merges auto-generated + user-added lectures."""
        from lecturelink_api.routers.onboarding import get_lecture_checklist

        today = date.today()
        sb, _ = self._make_sb({
            "semester_start": (today - timedelta(days=14)).isoformat(),
            "semester_end": (today + timedelta(days=60)).isoformat(),
            "meeting_days": ["tuesday", "thursday"],
            "holidays": [],
        }, extra_tables={
            "lecture_schedule_corrections": [
                {
                    "original_lecture_number": 99,
                    "corrected_date": today.isoformat(),
                    "corrected_title": "Added Lecture",
                    "corrected_description": None,
                    "is_addition": True,
                },
            ],
        })

        with patch(
            "lecturelink_api.routers.onboarding.get_authenticated_supabase", return_value=sb,
        ):
            result = await get_lecture_checklist(
                course_id="course-1",
                user={"id": "user-1", "token": "tok", "email": "a@b.com"},
                settings=MagicMock(),
            )

        assert isinstance(result, list)
        assert any(item.get("is_user_added") for item in result)
