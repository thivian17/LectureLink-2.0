"""Integration tests for the syllabus service assessment pipeline.

Tests the full flow from extraction → date resolution → DB persistence,
plus review acceptance and manual correction flows.
All Supabase calls and agent pipeline calls are mocked.
"""

from __future__ import annotations

import uuid
from unittest.mock import MagicMock, patch

import pytest

from lecturelink_api.models.syllabus_models import (
    AssessmentExtraction,
    ExtractedField,
    GradeComponent,
    SyllabusExtraction,
    WeeklyScheduleEntry,
    extraction_to_db_assessments,
)
from lecturelink_api.services.syllabus_service import (
    _build_semester_context,
    accept_syllabus_review,
    process_syllabus,
    update_assessment_from_review,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _field(value, confidence=0.9, source_text=None):
    return ExtractedField(value=value, confidence=confidence, source_text=source_text)


def _make_assessment(
    title="Midterm 1",
    atype="exam",
    raw_date="October 10",
    resolved_date="2026-03-10",
    weight=15.0,
    topics=None,
    confidence=0.9,
):
    return AssessmentExtraction(
        title=_field(title, confidence),
        type=_field(atype, confidence),
        due_date_raw=_field(raw_date, confidence),
        due_date_resolved=_field(resolved_date, confidence),
        weight_percent=_field(weight, confidence),
        topics=topics or [],
    )


def _make_extraction(assessments=None, grade_breakdown=None):
    """Build a minimal SyllabusExtraction for testing."""
    if assessments is None:
        assessments = [
            _make_assessment("Midterm 1", "exam", "Week 3 Tuesday", "2026-01-27", 15.0),
            _make_assessment("Final Exam", "exam", "May 1", "2026-05-01", 35.0),
            _make_assessment("HW 1", "homework", "TBD", None, 5.0),
        ]
    if grade_breakdown is None:
        grade_breakdown = [
            GradeComponent(
                name=_field("Exams"),
                weight_percent=_field(50.0),
            ),
            GradeComponent(
                name=_field("Homework"),
                weight_percent=_field(25.0),
            ),
            GradeComponent(
                name=_field("Participation"),
                weight_percent=_field(25.0),
            ),
        ]
    return SyllabusExtraction(
        course_name=_field("CS 101"),
        course_code=_field("CS101"),
        instructor_name=_field("Dr. Smith"),
        instructor_email=_field("smith@uni.edu"),
        office_hours=_field("MWF 2-3pm"),
        grade_breakdown=grade_breakdown,
        assessments=assessments,
        weekly_schedule=[
            WeeklyScheduleEntry(week_number=1, topics=["Intro"]),
        ],
        policies={"late_policy": "10% per day"},
        extraction_confidence=0.85,
        missing_sections=[],
    )


SEMESTER_CONTEXT = {
    "semester_start": "2026-01-12",
    "semester_end": "2026-05-01",
    "meeting_days": ["tuesday", "thursday"],
    "holidays": [],
}


def _mock_execute(data):
    resp = MagicMock()
    resp.data = data
    return resp


def _mock_chain(final_data):
    chain = MagicMock()
    chain.execute.return_value = _mock_execute(final_data)
    for method in (
        "select", "insert", "update", "delete",
        "eq", "order", "single", "maybe_single",
    ):
        getattr(chain, method).return_value = chain
    return chain


# ---------------------------------------------------------------------------
# _build_semester_context
# ---------------------------------------------------------------------------


class TestBuildSemesterContext:
    def test_valid_context(self):
        ctx = _build_semester_context(SEMESTER_CONTEXT)
        assert ctx is not None
        assert str(ctx.start) == "2026-01-12"
        assert str(ctx.end) == "2026-05-01"
        assert ctx.meeting_days == ["tuesday", "thursday"]

    def test_normalizes_meeting_days(self):
        ctx = _build_semester_context({
            "semester_start": "2026-01-12",
            "semester_end": "2026-05-01",
            "meeting_days": ["Tue", "Thu"],
        })
        assert ctx is not None
        assert ctx.meeting_days == ["tue", "thu"]

    def test_missing_start_returns_none(self):
        ctx = _build_semester_context({"semester_end": "2026-05-01"})
        assert ctx is None

    def test_missing_end_returns_none(self):
        ctx = _build_semester_context({"semester_start": "2026-01-12"})
        assert ctx is None

    def test_empty_dict_returns_none(self):
        ctx = _build_semester_context({})
        assert ctx is None

    def test_invalid_dates_returns_none(self):
        ctx = _build_semester_context({
            "semester_start": "not-a-date",
            "semester_end": "also-bad",
        })
        assert ctx is None


# ---------------------------------------------------------------------------
# process_syllabus — end-to-end with mocked pipeline
# ---------------------------------------------------------------------------


class TestProcessSyllabus:
    @pytest.mark.asyncio
    async def test_end_to_end_populates_assessments(self):
        """Full pipeline: extraction → date resolution → DB writes."""
        syllabus_id = str(uuid.uuid4())
        course_id = str(uuid.uuid4())
        user_id = str(uuid.uuid4())
        extraction = _make_extraction()

        sb = MagicMock()
        # _fetch_semester_context
        courses_chain = _mock_chain(SEMESTER_CONTEXT)
        # syllabi update + assessments insert
        syllabi_chain = _mock_chain([{"id": syllabus_id}])
        assessments_chain = _mock_chain([])

        call_count = {"n": 0}

        def table_side_effect(name):
            nonlocal call_count
            call_count["n"] += 1
            if name == "courses":
                return courses_chain
            if name == "syllabi":
                return syllabi_chain
            if name == "assessments":
                return assessments_chain
            return _mock_chain([])

        sb.table.side_effect = table_side_effect

        with (
            patch(
                "lecturelink_api.services.syllabus_service._run_agent_pipeline",
                return_value=extraction.model_dump(mode="json"),
            ),
            patch(
                "lecturelink_api.services.syllabus_service.post_process_extraction",
                return_value=extraction,
            ),
        ):
            result = await process_syllabus(
                syllabus_id=syllabus_id,
                file_bytes=b"fake-pdf",
                file_name="syllabus.pdf",
                mime_type="application/pdf",
                course_id=course_id,
                user_id=user_id,
                supabase=sb,
            )

        # Should return a SyllabusExtraction
        assert isinstance(result, SyllabusExtraction)

        # Verify syllabi table was updated with needs_review=True
        syllabi_chain.update.assert_called_once()
        update_payload = syllabi_chain.update.call_args[0][0]
        assert update_payload["needs_review"] is True
        assert update_payload["status"] == "processed"
        assert "raw_extraction" in update_payload
        assert "grade_breakdown" in update_payload
        assert "extraction_confidence" in update_payload

        # Verify assessments were inserted
        assessments_chain.insert.assert_called_once()
        inserted_rows = assessments_chain.insert.call_args[0][0]
        assert len(inserted_rows) == 3

    @pytest.mark.asyncio
    async def test_date_resolution_runs(self):
        """Verify resolve_all_dates is called and affects assessment rows."""
        syllabus_id = str(uuid.uuid4())
        course_id = str(uuid.uuid4())
        extraction = _make_extraction()

        sb = MagicMock()
        courses_chain = _mock_chain(SEMESTER_CONTEXT)
        syllabi_chain = _mock_chain([{"id": syllabus_id}])
        assessments_chain = _mock_chain([])

        def table_side_effect(name):
            if name == "courses":
                return courses_chain
            if name == "syllabi":
                return syllabi_chain
            if name == "assessments":
                return assessments_chain
            return _mock_chain([])

        sb.table.side_effect = table_side_effect

        with (
            patch(
                "lecturelink_api.services.syllabus_service._run_agent_pipeline",
                return_value=extraction.model_dump(mode="json"),
            ),
            patch(
                "lecturelink_api.services.syllabus_service.post_process_extraction",
                return_value=extraction,
            ),
            patch(
                "lecturelink_api.services.syllabus_service.resolve_all_dates",
                wraps=None,
            ) as mock_resolve,
        ):
            mock_resolve.return_value = extraction.assessments
            await process_syllabus(
                syllabus_id=syllabus_id,
                file_bytes=b"fake",
                file_name="test.pdf",
                mime_type="application/pdf",
                course_id=course_id,
                user_id=str(uuid.uuid4()),
                supabase=sb,
            )

        mock_resolve.assert_called_once()

    @pytest.mark.asyncio
    async def test_ambiguous_dates_flagged(self):
        """Assessment with unresolvable date gets is_date_ambiguous=True."""
        extraction = _make_extraction(assessments=[
            _make_assessment("Quiz", "quiz", "TBD", None, 10.0),
        ])

        rows = extraction_to_db_assessments(extraction, "c1", "s1")
        assert len(rows) == 1
        assert rows[0]["is_date_ambiguous"] is True
        assert rows[0]["due_date"] is None

    @pytest.mark.asyncio
    async def test_resolved_dates_not_ambiguous(self):
        """Assessment with resolved date gets is_date_ambiguous=False."""
        extraction = _make_extraction(assessments=[
            _make_assessment("Midterm", "exam", "March 10", "2026-03-10", 20.0),
        ])

        rows = extraction_to_db_assessments(extraction, "c1", "s1")
        assert len(rows) == 1
        assert rows[0]["is_date_ambiguous"] is False
        assert rows[0]["due_date"] == "2026-03-10"

    @pytest.mark.asyncio
    async def test_grade_breakdown_matches_weights(self):
        """grade_breakdown JSONB values should match assessment weight_percent."""
        grade_breakdown = [
            GradeComponent(name=_field("Exams"), weight_percent=_field(50.0)),
            GradeComponent(name=_field("HW"), weight_percent=_field(50.0)),
        ]
        assessments = [
            _make_assessment("Midterm", "exam", "Mar 10", "2026-03-10", 25.0),
            _make_assessment("Final", "exam", "May 1", "2026-05-01", 25.0),
            _make_assessment("HW 1", "homework", "Feb 1", "2026-02-01", 25.0),
            _make_assessment("HW 2", "homework", "Mar 1", "2026-03-01", 25.0),
        ]
        extraction = _make_extraction(assessments=assessments, grade_breakdown=grade_breakdown)

        # Grade breakdown totals
        gb_total = sum(
            float(c.weight_percent.value) for c in extraction.grade_breakdown
        )
        assert gb_total == 100.0

        # Assessment weights should also sum to 100
        rows = extraction_to_db_assessments(extraction, "c1", "s1")
        weight_total = sum(r["weight_percent"] for r in rows)
        assert weight_total == 100.0

    @pytest.mark.asyncio
    async def test_extraction_failure_saves_error(self):
        """If the pipeline raises, syllabi table gets error status."""
        syllabus_id = str(uuid.uuid4())
        course_id = str(uuid.uuid4())

        sb = MagicMock()
        courses_chain = _mock_chain(SEMESTER_CONTEXT)
        syllabi_chain = _mock_chain([{"id": syllabus_id}])

        def table_side_effect(name):
            if name == "courses":
                return courses_chain
            if name == "syllabi":
                return syllabi_chain
            return _mock_chain([])

        sb.table.side_effect = table_side_effect

        with (
            patch(
                "lecturelink_api.services.syllabus_service._run_agent_pipeline",
                side_effect=RuntimeError("Pipeline exploded"),
            ),
            pytest.raises(RuntimeError, match="Pipeline exploded"),
        ):
            await process_syllabus(
                syllabus_id=syllabus_id,
                file_bytes=b"bad",
                file_name="bad.pdf",
                mime_type="application/pdf",
                course_id=course_id,
                user_id=str(uuid.uuid4()),
                supabase=sb,
            )

        # Verify error state was saved
        syllabi_chain.update.assert_called_once()
        error_payload = syllabi_chain.update.call_args[0][0]
        assert error_payload["extraction_confidence"] == 0.0
        assert error_payload["status"] == "error"
        assert error_payload["needs_review"] is True
        assert "error" in error_payload["raw_extraction"]

    @pytest.mark.asyncio
    async def test_no_semester_context_skips_date_resolution(self):
        """If semester dates are missing, date resolution is skipped gracefully."""
        syllabus_id = str(uuid.uuid4())
        course_id = str(uuid.uuid4())
        extraction = _make_extraction()

        sb = MagicMock()
        # Return empty semester context
        courses_chain = _mock_chain({})
        syllabi_chain = _mock_chain([{"id": syllabus_id}])
        assessments_chain = _mock_chain([])

        def table_side_effect(name):
            if name == "courses":
                return courses_chain
            if name == "syllabi":
                return syllabi_chain
            if name == "assessments":
                return assessments_chain
            return _mock_chain([])

        sb.table.side_effect = table_side_effect

        with (
            patch(
                "lecturelink_api.services.syllabus_service._run_agent_pipeline",
                return_value=extraction.model_dump(mode="json"),
            ),
            patch(
                "lecturelink_api.services.syllabus_service.post_process_extraction",
                return_value=extraction,
            ),
            patch(
                "lecturelink_api.services.syllabus_service.resolve_all_dates",
            ) as mock_resolve,
        ):
            result = await process_syllabus(
                syllabus_id=syllabus_id,
                file_bytes=b"fake",
                file_name="test.pdf",
                mime_type="application/pdf",
                course_id=course_id,
                user_id=str(uuid.uuid4()),
                supabase=sb,
            )

        # resolve_all_dates should NOT have been called
        mock_resolve.assert_not_called()
        assert isinstance(result, SyllabusExtraction)


# ---------------------------------------------------------------------------
# update_assessment_from_review
# ---------------------------------------------------------------------------


class TestUpdateAssessmentFromReview:
    @pytest.mark.asyncio
    async def test_manual_date_correction_clears_ambiguous(self):
        """When a date is manually set, is_date_ambiguous should become False."""
        assessment_id = str(uuid.uuid4())
        updated_row = {
            "id": assessment_id,
            "due_date": "2026-04-15",
            "is_date_ambiguous": False,
        }

        sb = MagicMock()
        sb.table.return_value = _mock_chain([updated_row])

        result = await update_assessment_from_review(
            assessment_id=assessment_id,
            updates={"due_date": "2026-04-15"},
            supabase=sb,
        )

        assert result["is_date_ambiguous"] is False
        # Verify the update payload included is_date_ambiguous=False
        sb.table.return_value.update.assert_called_once()
        payload = sb.table.return_value.update.call_args[0][0]
        assert payload["is_date_ambiguous"] is False
        assert payload["due_date"] == "2026-04-15"

    @pytest.mark.asyncio
    async def test_title_update_preserves_ambiguous_flag(self):
        """Updating title alone should NOT touch is_date_ambiguous."""
        assessment_id = str(uuid.uuid4())
        updated_row = {
            "id": assessment_id,
            "title": "Midterm Exam 2",
        }

        sb = MagicMock()
        sb.table.return_value = _mock_chain([updated_row])

        result = await update_assessment_from_review(
            assessment_id=assessment_id,
            updates={"title": "Midterm Exam 2"},
            supabase=sb,
        )

        assert result["title"] == "Midterm Exam 2"
        payload = sb.table.return_value.update.call_args[0][0]
        assert "is_date_ambiguous" not in payload

    @pytest.mark.asyncio
    async def test_null_date_does_not_clear_ambiguous(self):
        """Setting due_date=None should NOT clear is_date_ambiguous."""
        sb = MagicMock()
        sb.table.return_value = _mock_chain([{"id": "a1"}])

        await update_assessment_from_review(
            assessment_id="a1",
            updates={"due_date": None},
            supabase=sb,
        )

        payload = sb.table.return_value.update.call_args[0][0]
        assert "is_date_ambiguous" not in payload

    @pytest.mark.asyncio
    async def test_not_found_raises(self):
        """If the assessment doesn't exist, raise ValueError."""
        sb = MagicMock()
        sb.table.return_value = _mock_chain([])

        with pytest.raises(ValueError, match="not found"):
            await update_assessment_from_review(
                assessment_id="nonexistent",
                updates={"title": "X"},
                supabase=sb,
            )


# ---------------------------------------------------------------------------
# accept_syllabus_review
# ---------------------------------------------------------------------------


class TestAcceptSyllabusReview:
    @pytest.mark.asyncio
    async def test_sets_needs_review_false(self):
        """Accepting review sets needs_review=False and reviewed_at."""
        syllabus_id = str(uuid.uuid4())

        sb = MagicMock()
        syllabi_chain = _mock_chain([{"id": syllabus_id}])
        # For the assessment count query
        assessments_chain = _mock_chain([{"id": "a1"}, {"id": "a2"}, {"id": "a3"}])

        def table_side_effect(name):
            if name == "syllabi":
                return syllabi_chain
            if name == "assessments":
                return assessments_chain
            return _mock_chain([])

        sb.table.side_effect = table_side_effect

        result = await accept_syllabus_review(
            syllabus_id=syllabus_id,
            supabase=sb,
        )

        assert result["syllabus_id"] == syllabus_id
        assert result["assessment_count"] == 3

        # Verify syllabi update payload
        syllabi_chain.update.assert_called_once()
        payload = syllabi_chain.update.call_args[0][0]
        assert payload["needs_review"] is False
        assert payload["reviewed_at"] == "now()"

    @pytest.mark.asyncio
    async def test_returns_zero_count_when_no_assessments(self):
        """If no assessments exist, count should be 0."""
        syllabus_id = str(uuid.uuid4())

        sb = MagicMock()
        syllabi_chain = _mock_chain([{"id": syllabus_id}])
        assessments_chain = _mock_chain([])

        def table_side_effect(name):
            if name == "syllabi":
                return syllabi_chain
            if name == "assessments":
                return assessments_chain
            return _mock_chain([])

        sb.table.side_effect = table_side_effect

        result = await accept_syllabus_review(
            syllabus_id=syllabus_id,
            supabase=sb,
        )

        assert result["assessment_count"] == 0


# ---------------------------------------------------------------------------
# extraction_to_db_assessments — field mapping
# ---------------------------------------------------------------------------


class TestExtractionToDbAssessments:
    def test_all_fields_mapped(self):
        """Each assessment row has all expected DB columns."""
        extraction = _make_extraction(assessments=[
            _make_assessment("Quiz 1", "quiz", "Feb 15", "2026-02-15", 10.0, ["Ch 1"]),
        ])

        rows = extraction_to_db_assessments(extraction, "course-1", "syllabus-1")
        assert len(rows) == 1
        row = rows[0]

        assert row["course_id"] == "course-1"
        assert row["syllabus_id"] == "syllabus-1"
        assert row["title"] == "Quiz 1"
        assert row["type"] == "quiz"
        assert row["due_date"] == "2026-02-15"
        assert row["due_date_raw"] == "Feb 15"
        assert row["is_date_ambiguous"] is False
        assert row["weight_percent"] == 10.0
        assert row["topics"] == ["Ch 1"]
        assert "id" in row  # UUID should be generated

    def test_missing_title_defaults_to_untitled(self):
        extraction = _make_extraction(assessments=[
            _make_assessment(None, "exam", "Mar 1", "2026-03-01", 20.0),
        ])
        rows = extraction_to_db_assessments(extraction, "c1", "s1")
        assert rows[0]["title"] == "Untitled"

    def test_missing_type_defaults_to_other(self):
        extraction = _make_extraction(assessments=[
            _make_assessment("Test", None, "Mar 1", "2026-03-01", 20.0),
        ])
        rows = extraction_to_db_assessments(extraction, "c1", "s1")
        assert rows[0]["type"] == "other"

    def test_string_weight_converted_to_float(self):
        """weight_percent stored as string should be converted."""
        a = _make_assessment("HW", "homework", "Mar 1", "2026-03-01", "15.5")
        extraction = _make_extraction(assessments=[a])
        rows = extraction_to_db_assessments(extraction, "c1", "s1")
        assert rows[0]["weight_percent"] == 15.5

    def test_empty_assessments_returns_empty_list(self):
        extraction = _make_extraction(assessments=[])
        rows = extraction_to_db_assessments(extraction, "c1", "s1")
        assert rows == []
