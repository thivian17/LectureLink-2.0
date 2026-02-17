"""Tests for the study actions service — schedule computation + priority algorithm."""

from __future__ import annotations

import uuid
from datetime import date, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from lecturelink_api.services.study_actions import (
    LectureGap,
    StudyAction,
    compute_expected_meetings,
    compute_lecture_gap,
    get_study_actions,
)


# ---------------------------------------------------------------------------
# Schedule computation
# ---------------------------------------------------------------------------


class TestComputeExpectedMeetings:
    def test_basic_mwf_schedule(self):
        """MWF from Mon Jan 13 to Fri Jan 24 = 6 meetings."""
        meetings = compute_expected_meetings(
            semester_start=date(2025, 1, 13),
            meeting_days=["Monday", "Wednesday", "Friday"],
            holidays=[],
            as_of=date(2025, 1, 24),
        )
        assert len(meetings) == 6
        assert meetings[0] == date(2025, 1, 13)  # Monday
        assert meetings[-1] == date(2025, 1, 24)  # Friday

    def test_skips_holidays(self):
        """Meetings falling within holiday ranges are excluded."""
        meetings = compute_expected_meetings(
            semester_start=date(2025, 1, 13),
            meeting_days=["Monday", "Wednesday"],
            holidays=[
                {"name": "MLK Day", "start_date": "2025-01-20", "end_date": "2025-01-20"}
            ],
            as_of=date(2025, 1, 22),
        )
        # Expected: Jan 13 (Mon), Jan 15 (Wed), Jan 22 (Wed) = 3
        # Jan 20 (Mon) is MLK Day, skipped
        assert len(meetings) == 3
        assert date(2025, 1, 20) not in meetings

    def test_empty_meeting_days(self):
        """No meeting_days returns empty list."""
        meetings = compute_expected_meetings(
            semester_start=date(2025, 1, 13),
            meeting_days=[],
            as_of=date(2025, 2, 1),
        )
        assert meetings == []

    def test_invalid_day_names_ignored(self):
        """Unknown day names are silently skipped."""
        meetings = compute_expected_meetings(
            semester_start=date(2025, 1, 13),
            meeting_days=["Funday", "Monday"],
            as_of=date(2025, 1, 20),
        )
        # Only Monday is valid: Jan 13, Jan 20
        assert len(meetings) == 2

    def test_as_of_limits_range(self):
        """Only meetings up to as_of are included."""
        meetings = compute_expected_meetings(
            semester_start=date(2025, 1, 13),
            meeting_days=["Monday"],
            as_of=date(2025, 1, 13),  # Only the start day
        )
        assert len(meetings) == 1
        assert meetings[0] == date(2025, 1, 13)

    def test_multi_day_holiday_range(self):
        """A holiday spanning multiple days excludes all dates."""
        meetings = compute_expected_meetings(
            semester_start=date(2025, 3, 10),
            meeting_days=["Monday", "Wednesday", "Friday"],
            holidays=[
                {
                    "name": "Spring Break",
                    "start_date": "2025-03-10",
                    "end_date": "2025-03-14",
                }
            ],
            as_of=date(2025, 3, 21),
        )
        # Week of March 10-14 is all holiday. Next MWF: 17, 19, 21
        assert len(meetings) == 3
        assert meetings[0] == date(2025, 3, 17)


# ---------------------------------------------------------------------------
# Lecture gap
# ---------------------------------------------------------------------------


class TestComputeLectureGap:
    def test_no_gap_when_all_uploaded(self):
        """actual_count == expected_count means missing_count == 0."""
        gap = compute_lecture_gap(
            semester_start=date(2025, 1, 13),
            meeting_days=["Monday", "Wednesday"],
            holidays=[],
            actual_lecture_count=4,
            as_of=date(2025, 1, 22),
        )
        # Expected: Jan 13, 15, 20, 22 = 4
        assert gap.expected_count == 4
        assert gap.missing_count == 0

    def test_gap_detected(self):
        """actual_count < expected_count computes correct missing_count."""
        gap = compute_lecture_gap(
            semester_start=date(2025, 1, 13),
            meeting_days=["Monday", "Wednesday"],
            holidays=[],
            actual_lecture_count=1,
            as_of=date(2025, 1, 22),
        )
        assert gap.expected_count == 4
        assert gap.actual_count == 1
        assert gap.missing_count == 3

    def test_next_expected_date(self):
        """next_expected_date is the first meeting after today."""
        gap = compute_lecture_gap(
            semester_start=date(2025, 1, 13),
            meeting_days=["Monday", "Wednesday"],
            holidays=[],
            actual_lecture_count=0,
            as_of=date(2025, 1, 14),  # Tuesday
        )
        assert gap.next_expected_date == date(2025, 1, 15)  # Wednesday

    def test_extra_lectures_no_negative(self):
        """If student uploaded more than expected, missing_count = 0."""
        gap = compute_lecture_gap(
            semester_start=date(2025, 1, 13),
            meeting_days=["Monday"],
            holidays=[],
            actual_lecture_count=10,
            as_of=date(2025, 1, 20),
        )
        assert gap.missing_count == 0

    def test_last_expected_date(self):
        """last_expected_date is the most recent meeting up to as_of."""
        gap = compute_lecture_gap(
            semester_start=date(2025, 1, 13),
            meeting_days=["Monday", "Wednesday"],
            holidays=[],
            actual_lecture_count=0,
            as_of=date(2025, 1, 16),  # Thursday
        )
        assert gap.last_expected_date == date(2025, 1, 15)  # Wed
        assert gap.days_since_last_expected == 1


# ---------------------------------------------------------------------------
# Action priority algorithm
# ---------------------------------------------------------------------------

COURSE_ID = str(uuid.uuid4())
USER_ID = str(uuid.uuid4())


def _mock_execute(data, count=None):
    resp = MagicMock()
    resp.data = data
    resp.count = count if count is not None else (len(data) if data else 0)
    return resp


def _mock_chain(final_data, count=None):
    chain = MagicMock()
    chain.execute.return_value = _mock_execute(final_data, count)
    for method in (
        "select", "eq", "in_", "order", "limit", "single",
        "gte", "lte", "not_", "neq",
    ):
        getattr(chain, method).return_value = chain
    return chain


def _make_course(**overrides):
    base = {
        "id": COURSE_ID,
        "user_id": USER_ID,
        "name": "Data Structures",
        "code": "CS 201",
        "semester_start": "2025-01-13",
        "semester_end": "2025-05-02",
        "meeting_days": ["Monday", "Wednesday"],
        "meeting_time": "10:00 AM",
        "holidays": [],
        "target_grade": 0.9,
    }
    base.update(overrides)
    return base


class TestGetStudyActionsNoSyllabus:
    @pytest.mark.asyncio
    async def test_no_syllabus_top_priority(self):
        """Course with no syllabus returns upload_syllabus at priority 1.0."""
        sb = MagicMock()
        course = _make_course()

        def table_side_effect(name):
            if name == "courses":
                return _mock_chain([course])
            if name == "syllabi":
                return _mock_chain([])  # No syllabus
            if name == "lectures":
                return _mock_chain([], count=0)
            return _mock_chain([])

        sb.table.side_effect = table_side_effect

        actions = await get_study_actions(sb, USER_ID)
        assert len(actions) >= 1
        assert actions[0].action_type == "upload_syllabus"
        assert actions[0].priority == 1.0
        assert "CS 201" in actions[0].title

    @pytest.mark.asyncio
    async def test_no_syllabus_skips_other_tiers(self):
        """Only upload_syllabus action is generated when no syllabus exists."""
        sb = MagicMock()
        course = _make_course()

        def table_side_effect(name):
            if name == "courses":
                return _mock_chain([course])
            if name == "syllabi":
                return _mock_chain([])
            if name == "lectures":
                return _mock_chain([], count=0)
            return _mock_chain([])

        sb.table.side_effect = table_side_effect

        actions = await get_study_actions(sb, USER_ID)
        assert len(actions) == 1
        assert actions[0].action_type == "upload_syllabus"


class TestGetStudyActionsSyllabusReview:
    @pytest.mark.asyncio
    async def test_needs_review_produces_action(self):
        """Syllabus with needs_review returns review_syllabus at ~0.95."""
        sb = MagicMock()
        course = _make_course(meeting_days=[])  # No meeting days to skip tier 3

        def table_side_effect(name):
            if name == "courses":
                return _mock_chain([course])
            if name == "syllabi":
                return _mock_chain([{
                    "id": "syl-1",
                    "status": "processed",
                    "needs_review": True,
                    "reviewed_at": None,
                }])
            if name == "lectures":
                return _mock_chain([], count=0)
            if name == "assessments":
                return _mock_chain([])
            return _mock_chain([])

        sb.table.side_effect = table_side_effect

        actions = await get_study_actions(sb, USER_ID)
        review_actions = [a for a in actions if a.action_type == "review_syllabus"]
        assert len(review_actions) == 1
        assert review_actions[0].priority == 0.95


class TestGetStudyActionsLectureGaps:
    @pytest.mark.asyncio
    async def test_missing_lectures_detected(self):
        """Course behind on lectures produces upload_lectures action."""
        sb = MagicMock()
        today = date.today()
        # Set semester start to 2 weeks ago so there should be ~4 meetings
        sem_start = today - timedelta(days=14)
        course = _make_course(
            semester_start=sem_start.isoformat(),
            meeting_days=["Monday", "Wednesday"],
        )

        def table_side_effect(name):
            if name == "courses":
                return _mock_chain([course])
            if name == "syllabi":
                return _mock_chain([{
                    "id": "syl-1",
                    "status": "processed",
                    "needs_review": False,
                    "reviewed_at": "2025-01-15T00:00:00Z",
                }])
            if name == "lectures":
                return _mock_chain([], count=0)  # 0 lectures uploaded
            if name == "assessments":
                return _mock_chain([])
            return _mock_chain([])

        sb.table.side_effect = table_side_effect

        actions = await get_study_actions(sb, USER_ID)
        upload_actions = [a for a in actions if a.action_type == "upload_lectures"]
        assert len(upload_actions) == 1
        assert upload_actions[0].priority >= 0.85
        assert "behind" in upload_actions[0].title.lower()

    @pytest.mark.asyncio
    async def test_no_meeting_days_no_lecture_action(self):
        """Course without meeting_days produces no upload_lectures action."""
        sb = MagicMock()
        course = _make_course(meeting_days=[])

        def table_side_effect(name):
            if name == "courses":
                return _mock_chain([course])
            if name == "syllabi":
                return _mock_chain([{
                    "id": "syl-1",
                    "status": "processed",
                    "needs_review": False,
                    "reviewed_at": "2025-01-15T00:00:00Z",
                }])
            if name == "lectures":
                return _mock_chain([], count=0)
            if name == "assessments":
                return _mock_chain([])
            return _mock_chain([])

        sb.table.side_effect = table_side_effect

        actions = await get_study_actions(sb, USER_ID)
        upload_actions = [a for a in actions if a.action_type == "upload_lectures"]
        assert len(upload_actions) == 0


class TestGetStudyActionsSorting:
    @pytest.mark.asyncio
    async def test_actions_sorted_by_priority(self):
        """Actions are returned sorted highest priority first."""
        sb = MagicMock()
        today = date.today()
        sem_start = today - timedelta(days=14)
        # Course has needs_review (0.95) AND missing lectures (~0.85-0.92)
        course = _make_course(
            semester_start=sem_start.isoformat(),
            meeting_days=["Monday", "Wednesday"],
        )

        def table_side_effect(name):
            if name == "courses":
                return _mock_chain([course])
            if name == "syllabi":
                return _mock_chain([{
                    "id": "syl-1",
                    "status": "processed",
                    "needs_review": True,
                    "reviewed_at": None,
                }])
            if name == "lectures":
                return _mock_chain([], count=0)
            if name == "assessments":
                return _mock_chain([])
            return _mock_chain([])

        sb.table.side_effect = table_side_effect

        actions = await get_study_actions(sb, USER_ID)
        assert len(actions) >= 2
        for i in range(len(actions) - 1):
            assert actions[i].priority >= actions[i + 1].priority

    @pytest.mark.asyncio
    async def test_limit_respected(self):
        """Only top N actions returned when limit is set."""
        sb = MagicMock()
        today = date.today()
        sem_start = today - timedelta(days=14)
        course = _make_course(
            semester_start=sem_start.isoformat(),
            meeting_days=["Monday", "Wednesday"],
        )

        def table_side_effect(name):
            if name == "courses":
                return _mock_chain([course])
            if name == "syllabi":
                return _mock_chain([{
                    "id": "syl-1",
                    "status": "processed",
                    "needs_review": True,
                    "reviewed_at": None,
                }])
            if name == "lectures":
                return _mock_chain([], count=0)
            if name == "assessments":
                return _mock_chain([])
            return _mock_chain([])

        sb.table.side_effect = table_side_effect

        actions = await get_study_actions(sb, USER_ID, limit=1)
        assert len(actions) == 1


class TestGetStudyActionsCTAUrls:
    @pytest.mark.asyncio
    async def test_cta_urls_valid(self):
        """Each action has a CTA URL pointing to a valid dashboard route."""
        sb = MagicMock()
        course = _make_course(meeting_days=[])

        def table_side_effect(name):
            if name == "courses":
                return _mock_chain([course])
            if name == "syllabi":
                return _mock_chain([])  # No syllabus
            if name == "lectures":
                return _mock_chain([], count=0)
            return _mock_chain([])

        sb.table.side_effect = table_side_effect

        actions = await get_study_actions(sb, USER_ID)
        for action in actions:
            assert action.cta_url.startswith("/dashboard/courses/")
