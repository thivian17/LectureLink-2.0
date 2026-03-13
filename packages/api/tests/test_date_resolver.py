"""Tests for the LLM date validation system.

The LLM agent (with full semester + holiday context) resolves dates.
This module validates those dates against semester boundaries and holidays.

Semester fixture:
  start: 2026-01-12 (Monday), end: 2026-05-01
  meeting_days: ['tuesday', 'thursday']
  holidays: [Spring Break 2026-03-09 → 2026-03-13]
"""

from __future__ import annotations

from datetime import date

import pytest
from lecturelink_api.models.syllabus_models import AssessmentExtraction, ExtractedField
from lecturelink_api.tools.date_resolver import (
    ResolvedDate,
    SemesterContext,
    resolve_all_dates,
    resolve_date,
)

# ---------------------------------------------------------------------------
# Fixtures & helpers
# ---------------------------------------------------------------------------


@pytest.fixture
def semester() -> SemesterContext:
    return SemesterContext(
        start=date(2026, 1, 12),
        end=date(2026, 5, 1),
        meeting_days=["tuesday", "thursday"],
        holidays=[
            {
                "name": "Spring Break",
                "start": "2026-03-09",
                "end": "2026-03-13",
            }
        ],
    )


def _make_assessment(
    raw: str = "February 26, 2026",
    resolved: str | None = "2026-02-26",
    confidence: float = 0.9,
):
    """Build a minimal AssessmentExtraction for testing."""
    return AssessmentExtraction(
        title=ExtractedField(value="Test Assessment", confidence=0.9),
        type=ExtractedField(value="homework", confidence=0.9),
        due_date_raw=ExtractedField(value=raw, confidence=0.9),
        due_date_resolved=ExtractedField(
            value=resolved, confidence=confidence, source_text=None
        ),
        weight_percent=ExtractedField(value=10.0, confidence=0.9),
    )


# ---------------------------------------------------------------------------
# SemesterContext dataclass
# ---------------------------------------------------------------------------


class TestSemesterContext:
    def test_creation(self, semester):
        assert semester.start == date(2026, 1, 12)
        assert semester.end == date(2026, 5, 1)
        assert semester.meeting_days == ["tuesday", "thursday"]
        assert len(semester.holidays) == 1
        assert semester.holidays[0]["name"] == "Spring Break"

    def test_default_holidays(self):
        ctx = SemesterContext(
            start=date(2026, 1, 12),
            end=date(2026, 5, 1),
            meeting_days=["monday", "wednesday"],
        )
        assert ctx.holidays == []


# ---------------------------------------------------------------------------
# ResolvedDate dataclass
# ---------------------------------------------------------------------------


class TestResolvedDate:
    def test_resolved_with_value(self):
        rd = ResolvedDate(
            value=date(2026, 1, 15),
            confidence=0.9,
            method="llm_validated",
            original_text="Jan 15",
        )
        assert rd.value == date(2026, 1, 15)
        assert rd.confidence == 0.9
        assert rd.method == "llm_validated"
        assert rd.original_text == "Jan 15"

    def test_resolved_none(self):
        rd = ResolvedDate(
            value=None,
            confidence=0.0,
            method="ambiguous",
            original_text="TBA",
        )
        assert rd.value is None
        assert rd.confidence == 0.0


# ---------------------------------------------------------------------------
# LLM date validation
# ---------------------------------------------------------------------------


class TestLLMValidation:
    """LLM-resolved dates are validated against semester bounds and holidays."""

    def test_valid_date_accepted(self, semester):
        result = resolve_date("Feb 15", semester, llm_resolved=date(2026, 2, 15))
        assert result.value == date(2026, 2, 15)
        assert result.method == "llm_validated"

    def test_preserves_llm_confidence(self, semester):
        """LLM's own confidence is preserved, not overwritten."""
        result = resolve_date(
            "Feb 15", semester,
            llm_resolved=date(2026, 2, 15),
            llm_confidence=0.85,
        )
        assert result.confidence == 0.85

    def test_default_confidence_when_not_provided(self, semester):
        """Falls back to 0.9 when LLM confidence is 0."""
        result = resolve_date("Feb 15", semester, llm_resolved=date(2026, 2, 15))
        assert result.confidence == 0.9

    def test_semester_start_boundary(self, semester):
        result = resolve_date("first day", semester, llm_resolved=date(2026, 1, 12))
        assert result.value == date(2026, 1, 12)
        assert result.method == "llm_validated"

    def test_semester_end_boundary(self, semester):
        result = resolve_date("last day", semester, llm_resolved=date(2026, 5, 1))
        assert result.value == date(2026, 5, 1)
        assert result.method == "llm_validated"

    def test_before_semester_rejected(self, semester):
        result = resolve_date("some event", semester, llm_resolved=date(2025, 12, 1))
        assert result.value is None
        assert result.method == "ambiguous"

    def test_after_semester_rejected(self, semester):
        result = resolve_date("some event", semester, llm_resolved=date(2026, 6, 1))
        assert result.value is None
        assert result.method == "ambiguous"

    def test_during_holiday_rejected(self, semester):
        """LLM resolves to a date inside Spring Break → rejected."""
        result = resolve_date("midterm", semester, llm_resolved=date(2026, 3, 10))
        assert result.value is None
        assert result.method == "ambiguous"

    def test_holiday_boundary_start_rejected(self, semester):
        """First day of Spring Break rejected."""
        result = resolve_date("exam", semester, llm_resolved=date(2026, 3, 9))
        assert result.value is None
        assert result.method == "ambiguous"

    def test_holiday_boundary_end_rejected(self, semester):
        """Last day of Spring Break rejected."""
        result = resolve_date("exam", semester, llm_resolved=date(2026, 3, 13))
        assert result.value is None
        assert result.method == "ambiguous"

    def test_day_after_holiday_accepted(self, semester):
        """Day after Spring Break is fine."""
        result = resolve_date("quiz", semester, llm_resolved=date(2026, 3, 14))
        assert result.value == date(2026, 3, 14)
        assert result.method == "llm_validated"

    def test_no_llm_resolved_date(self, semester):
        """No LLM date → ambiguous."""
        result = resolve_date("midterm week", semester, llm_resolved=None)
        assert result.value is None
        assert result.method == "ambiguous"

    def test_multiple_holidays(self):
        """Two holiday periods both rejected."""
        sem = SemesterContext(
            start=date(2026, 1, 12),
            end=date(2026, 5, 1),
            meeting_days=["tuesday", "thursday"],
            holidays=[
                {"name": "MLK Day", "start": "2026-01-19", "end": "2026-01-19"},
                {"name": "Spring Break", "start": "2026-03-09", "end": "2026-03-13"},
            ],
        )
        # MLK Day rejected
        result = resolve_date("quiz", sem, llm_resolved=date(2026, 1, 19))
        assert result.value is None

        # Spring Break rejected
        result = resolve_date("exam", sem, llm_resolved=date(2026, 3, 11))
        assert result.value is None

        # Non-holiday accepted
        result = resolve_date("hw", sem, llm_resolved=date(2026, 1, 20))
        assert result.value == date(2026, 1, 20)

    def test_holiday_with_date_objects(self):
        """Holidays may use date objects instead of strings."""
        sem = SemesterContext(
            start=date(2026, 1, 12),
            end=date(2026, 5, 1),
            meeting_days=["tuesday", "thursday"],
            holidays=[
                {
                    "name": "Spring Break",
                    "start": date(2026, 3, 9),
                    "end": date(2026, 3, 13),
                },
            ],
        )
        result = resolve_date("exam", sem, llm_resolved=date(2026, 3, 10))
        assert result.value is None

        result = resolve_date("exam", sem, llm_resolved=date(2026, 3, 14))
        assert result.value == date(2026, 3, 14)

    def test_no_holidays_semester(self):
        """Without holidays, any in-semester date is accepted."""
        sem = SemesterContext(
            start=date(2026, 1, 12),
            end=date(2026, 5, 1),
            meeting_days=["tuesday", "thursday"],
        )
        result = resolve_date("exam", sem, llm_resolved=date(2026, 3, 10))
        assert result.value == date(2026, 3, 10)


# ---------------------------------------------------------------------------
# Ambiguous and unresolvable dates
# ---------------------------------------------------------------------------


class TestAmbiguousDates:
    def test_tba(self, semester):
        result = resolve_date("TBA", semester)
        assert result.value is None
        assert result.confidence == 0.0
        assert result.method == "ambiguous"

    def test_tbd(self, semester):
        result = resolve_date("TBD", semester)
        assert result.value is None
        assert result.method == "ambiguous"

    def test_see_course_website(self, semester):
        result = resolve_date("See course website", semester)
        assert result.value is None
        assert result.method == "ambiguous"

    def test_end_of_semester(self, semester):
        result = resolve_date("End of semester", semester)
        assert result.value is None
        assert result.method == "ambiguous"

    def test_ongoing_phrases(self, semester):
        """Ongoing assessments (participation, etc.) resolve to ambiguous."""
        for phrase in ("Ongoing", "weekly", "Every Class", "throughout semester"):
            result = resolve_date(phrase, semester)
            assert result.value is None, f"'{phrase}' should be ambiguous"
            assert result.method == "ambiguous"

    def test_empty_string(self, semester):
        result = resolve_date("", semester)
        assert result.value is None
        assert result.confidence == 0.0
        assert result.method == "ambiguous"

    def test_whitespace_only(self, semester):
        result = resolve_date("   ", semester)
        assert result.value is None
        assert result.method == "ambiguous"

    def test_to_be_announced(self, semester):
        result = resolve_date("To be announced", semester)
        assert result.value is None
        assert result.method == "ambiguous"

    def test_to_be_determined(self, semester):
        result = resolve_date("To be determined", semester)
        assert result.value is None
        assert result.method == "ambiguous"

    def test_see_canvas(self, semester):
        result = resolve_date("See Canvas", semester)
        assert result.value is None
        assert result.method == "ambiguous"

    def test_original_text_preserved(self, semester):
        result = resolve_date("TBA", semester)
        assert result.original_text == "TBA"


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


class TestEdgeCases:
    def test_case_insensitive_tba(self, semester):
        for text in ["tba", "TBA", "Tba", "tBa"]:
            result = resolve_date(text, semester)
            assert result.value is None
            assert result.method == "ambiguous"

    def test_ambiguous_preserves_original_text(self, semester):
        result = resolve_date("See course website", semester)
        assert result.original_text == "See course website"

    def test_resolved_preserves_original_text(self, semester):
        result = resolve_date(
            "Jan 15, 2026", semester, llm_resolved=date(2026, 1, 15)
        )
        assert result.original_text == "Jan 15, 2026"

    def test_low_confidence_preserved(self, semester):
        """Low LLM confidence is preserved for downstream ambiguity check."""
        result = resolve_date(
            "maybe March?", semester,
            llm_resolved=date(2026, 3, 1),
            llm_confidence=0.3,
        )
        assert result.value == date(2026, 3, 1)
        assert result.confidence == 0.3
        assert result.method == "llm_validated"

    def test_freetext_without_llm_date_is_ambiguous(self, semester):
        """Raw text that is not a known phrase, but no LLM date → ambiguous."""
        result = resolve_date("sometime in March", semester)
        assert result.value is None
        assert result.method == "ambiguous"


# ---------------------------------------------------------------------------
# resolve_all_dates batch processing
# ---------------------------------------------------------------------------


class TestResolveAllDates:
    def test_empty_list(self, semester):
        result = resolve_all_dates([], semester)
        assert result == []

    def test_single_assessment_validated(self, semester):
        assessments = [_make_assessment(raw="Feb 26", resolved="2026-02-26")]
        result = resolve_all_dates(assessments, semester)
        assert len(result) == 1
        assert result[0].due_date_resolved.value == "2026-02-26"

    def test_preserves_other_fields(self, semester):
        assessments = [_make_assessment(raw="Jan 20", resolved="2026-01-20")]
        result = resolve_all_dates(assessments, semester)
        assert result[0].title.value == "Test Assessment"
        assert result[0].type.value == "homework"
        assert result[0].weight_percent.value == 10.0

    def test_multiple_assessments(self, semester):
        assessments = [
            _make_assessment(raw="Jan 13", resolved="2026-01-13"),
            _make_assessment(raw="Jan 29", resolved="2026-01-29"),
            _make_assessment(raw="TBA", resolved=None),
        ]
        result = resolve_all_dates(assessments, semester)
        assert result[0].due_date_resolved.value == "2026-01-13"
        assert result[1].due_date_resolved.value == "2026-01-29"
        assert result[2].due_date_resolved.value is None

    def test_llm_resolved_used_when_valid(self, semester):
        assessments = [_make_assessment(raw="midterm week", resolved="2026-02-15")]
        result = resolve_all_dates(assessments, semester)
        assert result[0].due_date_resolved.value == "2026-02-15"

    def test_preserves_llm_confidence(self, semester):
        assessments = [_make_assessment(
            raw="midterm", resolved="2026-02-15", confidence=0.75
        )]
        result = resolve_all_dates(assessments, semester)
        assert result[0].due_date_resolved.confidence == 0.75

    def test_ambiguous_sets_none(self, semester):
        assessments = [_make_assessment(raw="TBA", resolved=None)]
        result = resolve_all_dates(assessments, semester)
        assert result[0].due_date_resolved.value is None
        assert result[0].due_date_resolved.confidence == 0.0

    def test_null_raw_value(self, semester):
        a = AssessmentExtraction(
            title=ExtractedField(value="Test", confidence=0.9),
            type=ExtractedField(value="homework", confidence=0.9),
            due_date_raw=ExtractedField(value=None, confidence=0.0),
            due_date_resolved=ExtractedField(value=None, confidence=0.0),
            weight_percent=ExtractedField(value=10.0, confidence=0.9),
        )
        result = resolve_all_dates([a], semester)
        assert result[0].due_date_resolved.value is None

    def test_invalid_llm_date_ignored(self, semester):
        """If the existing resolved value isn't a valid ISO date, treat as missing."""
        assessments = [_make_assessment(raw="some date", resolved="not-a-date")]
        result = resolve_all_dates(assessments, semester)
        assert result[0].due_date_resolved.value is None
        assert result[0].due_date_resolved.confidence == 0.0

    def test_holiday_date_rejected(self, semester):
        """LLM date during Spring Break gets rejected."""
        assessments = [_make_assessment(raw="exam", resolved="2026-03-10")]
        result = resolve_all_dates(assessments, semester)
        assert result[0].due_date_resolved.value is None

    def test_does_not_mutate_input(self, semester):
        """Input list and its assessments must remain unchanged."""
        original = _make_assessment(raw="Jan 13", resolved="2026-01-13")
        assessments = [original]
        resolve_all_dates(assessments, semester)
        assert assessments[0].due_date_resolved.value == "2026-01-13"
