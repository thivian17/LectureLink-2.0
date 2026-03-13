"""Tests for the three-layer date resolution system.

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
    DAY_MAP,
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


def _make_assessment(raw: str = "Week 7 Thursday", resolved: str | None = "2026-02-26"):
    """Build a minimal AssessmentExtraction for testing."""
    return AssessmentExtraction(
        title=ExtractedField(value="Test Assessment", confidence=0.9),
        type=ExtractedField(value="homework", confidence=0.9),
        due_date_raw=ExtractedField(value=raw, confidence=0.9),
        due_date_resolved=ExtractedField(
            value=resolved, confidence=0.5, source_text=None
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
# DAY_MAP constant
# ---------------------------------------------------------------------------


class TestDayMap:
    def test_all_days_present(self):
        expected = {
            "monday", "tuesday", "wednesday", "thursday",
            "friday", "saturday", "sunday",
        }
        assert set(DAY_MAP.keys()) == expected

    def test_monday_is_zero(self):
        assert DAY_MAP["monday"] == 0

    def test_sunday_is_six(self):
        assert DAY_MAP["sunday"] == 6


# ---------------------------------------------------------------------------
# Layer 1 — LLM-resolved validation
# ---------------------------------------------------------------------------


class TestLayer1LLMValidation:
    def test_llm_date_within_semester(self, semester):
        result = resolve_date("Jan 15", semester, llm_resolved=date(2026, 1, 15))
        assert result.value == date(2026, 1, 15)
        assert result.confidence == 0.9
        assert result.method == "llm_validated"

    def test_llm_date_at_semester_start(self, semester):
        result = resolve_date("first day", semester, llm_resolved=date(2026, 1, 12))
        assert result.value == date(2026, 1, 12)
        assert result.method == "llm_validated"

    def test_llm_date_at_semester_end(self, semester):
        result = resolve_date("last day", semester, llm_resolved=date(2026, 5, 1))
        assert result.value == date(2026, 5, 1)
        assert result.method == "llm_validated"

    def test_llm_date_before_semester_rejected(self, semester):
        result = resolve_date("Dec 1", semester, llm_resolved=date(2025, 12, 1))
        assert result.method != "llm_validated"

    def test_llm_date_after_semester_rejected(self, semester):
        result = resolve_date("June 1", semester, llm_resolved=date(2026, 6, 1))
        assert result.method != "llm_validated"

    def test_llm_none_skips_to_other_layers(self, semester):
        result = resolve_date("Week 1 Tuesday", semester, llm_resolved=None)
        assert result.method == "week_relative"

    def test_llm_takes_priority_over_week_pattern(self, semester):
        result = resolve_date(
            "Week 3 Tuesday", semester, llm_resolved=date(2026, 2, 1)
        )
        assert result.value == date(2026, 2, 1)
        assert result.method == "llm_validated"

    def test_llm_rejected_falls_to_week_pattern(self, semester):
        # LLM gives out-of-range date, but text has a week pattern
        result = resolve_date(
            "Week 3 Tuesday", semester, llm_resolved=date(2025, 6, 1)
        )
        assert result.value == date(2026, 1, 27)
        assert result.method == "week_relative"


# ---------------------------------------------------------------------------
# Layer 2 — Relative week pattern matching
# ---------------------------------------------------------------------------


class TestLayer2WeekRelative:
    def test_week_1_tuesday(self, semester):
        result = resolve_date("Week 1 Tuesday", semester)
        assert result.value == date(2026, 1, 13)
        assert result.confidence == 0.85
        assert result.method == "week_relative"

    def test_week_1_thursday(self, semester):
        result = resolve_date("Week 1 Thursday", semester)
        assert result.value == date(2026, 1, 15)

    def test_week_3_no_day(self, semester):
        """Week 3 without day name → Monday of week 3."""
        result = resolve_date("Week 3", semester)
        assert result.value == date(2026, 1, 26)
        assert result.method == "week_relative"

    def test_week_3_tuesday(self, semester):
        result = resolve_date("Week 3 Tuesday", semester)
        assert result.value == date(2026, 1, 27)

    def test_wk_5_thurs_abbreviation(self, semester):
        result = resolve_date("Wk 5 Thurs", semester)
        assert result.value == date(2026, 2, 12)

    def test_week_lowercase(self, semester):
        result = resolve_date("week 2 monday", semester)
        assert result.value == date(2026, 1, 19)

    def test_week_uppercase(self, semester):
        result = resolve_date("WEEK 2 FRIDAY", semester)
        assert result.value == date(2026, 1, 23)

    def test_wk_no_space_before_number(self, semester):
        result = resolve_date("wk2 tuesday", semester)
        assert result.value == date(2026, 1, 20)

    def test_week_4_wednesday(self, semester):
        result = resolve_date("Week 4 Wednesday", semester)
        assert result.value == date(2026, 2, 4)

    def test_week_10_monday(self, semester):
        """Week 10 is the 10th teaching week; Spring Break (CW9) is skipped."""
        result = resolve_date("Week 10 Monday", semester)
        assert result.value == date(2026, 3, 23)

    def test_week_with_tue_abbrev(self, semester):
        result = resolve_date("Wk 6 Tue", semester)
        assert result.value == date(2026, 2, 17)

    def test_week_with_mon_abbrev(self, semester):
        result = resolve_date("Week 1 Mon", semester)
        assert result.value == date(2026, 1, 12)

    def test_week_with_fri_abbrev(self, semester):
        result = resolve_date("Week 2 Fri", semester)
        assert result.value == date(2026, 1, 23)

    def test_week_with_wed_abbrev(self, semester):
        result = resolve_date("Week 3 Wed", semester)
        assert result.value == date(2026, 1, 28)

    def test_end_of_week_10(self, semester):
        """'Due end of week 10' → Friday of teaching week 10 (Spring Break skipped)."""
        result = resolve_date("Due end of week 10", semester)
        assert result.value == date(2026, 3, 27)
        assert result.method == "week_relative"

    def test_end_of_week_without_due_prefix(self, semester):
        result = resolve_date("end of week 5", semester)
        assert result.value == date(2026, 2, 13)

    def test_week_14_saturday(self, semester):
        """Teaching week 14 (Spring Break skipped) = CW15, Saturday = Apr 25."""
        result = resolve_date("Week 14 Saturday", semester)
        assert result.value == date(2026, 4, 25)

    def test_week_1_is_first_week(self, semester):
        """Week 1 without day → Monday of semester start."""
        result = resolve_date("Week 1", semester)
        assert result.value == date(2026, 1, 12)

    def test_week_beyond_semester(self, semester):
        """Week 20 Monday = May 25, well past semester end."""
        result = resolve_date("Week 20 Monday", semester)
        # Layer 2 rejects it because the date is outside semester bounds
        assert result.method != "week_relative"

    def test_week_with_surrounding_text(self, semester):
        """Regex should find the week pattern even with extra words."""
        result = resolve_date("Assignment due Week 5 Thursday", semester)
        assert result.value == date(2026, 2, 12)
        assert result.method == "week_relative"


# ---------------------------------------------------------------------------
# Layer 2 — Holiday handling
# ---------------------------------------------------------------------------


class TestHolidayHandling:
    def test_week_9_tuesday_spring_break(self, semester):
        """Week 9 Tue = Mar 10 → Spring Break → shifts to Mar 17."""
        result = resolve_date("Week 9 Tuesday", semester)
        assert result.value == date(2026, 3, 17)
        assert result.method == "week_relative"

    def test_week_9_monday_spring_break(self, semester):
        """Week 9 Mon = Mar 9 → Spring Break → shifts to Mar 16."""
        result = resolve_date("Week 9 Monday", semester)
        assert result.value == date(2026, 3, 16)

    def test_week_9_thursday_spring_break(self, semester):
        """Week 9 Thu = Mar 12 → Spring Break → shifts to Mar 19."""
        result = resolve_date("Week 9 Thursday", semester)
        assert result.value == date(2026, 3, 19)

    def test_week_9_friday_spring_break(self, semester):
        """Week 9 Fri = Mar 13 → Spring Break → shifts to Mar 20."""
        result = resolve_date("Week 9 Friday", semester)
        assert result.value == date(2026, 3, 20)

    def test_week_8_not_affected(self, semester):
        """Week 8 Thu = Mar 5, before Spring Break — untouched."""
        result = resolve_date("Week 8 Thursday", semester)
        assert result.value == date(2026, 3, 5)

    def test_week_10_after_break(self, semester):
        """Week 10 is the 10th teaching week; Spring Break (CW9) skipped → CW11 Tue."""
        result = resolve_date("Week 10 Tuesday", semester)
        assert result.value == date(2026, 3, 24)

    def test_end_of_week_9_spring_break(self, semester):
        """End of week 9 = Fri Mar 13 → Spring Break → shifts to Mar 20."""
        result = resolve_date("end of week 9", semester)
        assert result.value == date(2026, 3, 20)

    def test_weeks_after_break_all_offset(self, semester):
        """All teaching weeks after Spring Break should be offset by +1 calendar week.

        This verifies the fix for the off-by-one bug where syllabi using week
        numbers would incorrectly place assessments during the break week,
        then shift only that one while leaving subsequent weeks un-offset.
        """
        # Before break: TW8 = CW8
        r8 = resolve_date("Week 8 Monday", semester)
        assert r8.value == date(2026, 3, 2)

        # After break: TW9-12 each shifted +1 calendar week
        r9 = resolve_date("Week 9 Monday", semester)
        assert r9.value == date(2026, 3, 16)  # CW10

        r10 = resolve_date("Week 10 Monday", semester)
        assert r10.value == date(2026, 3, 23)  # CW11

        r11 = resolve_date("Week 11 Monday", semester)
        assert r11.value == date(2026, 3, 30)  # CW12

        r12 = resolve_date("Week 12 Monday", semester)
        assert r12.value == date(2026, 4, 6)  # CW13

    def test_multiple_holidays(self):
        """Two holiday periods: MLK Day (Jan 19) and Spring Break."""
        sem = SemesterContext(
            start=date(2026, 1, 12),
            end=date(2026, 5, 1),
            meeting_days=["tuesday", "thursday"],
            holidays=[
                {"name": "MLK Day", "start": "2026-01-19", "end": "2026-01-19"},
                {"name": "Spring Break", "start": "2026-03-09", "end": "2026-03-13"},
            ],
        )
        # Week 2 Monday = Jan 19 (MLK Day) → next Monday = Jan 26
        result = resolve_date("Week 2 Monday", sem)
        assert result.value == date(2026, 1, 26)

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
        result = resolve_date("Week 9 Tuesday", sem)
        assert result.value == date(2026, 3, 17)

    def test_no_holidays_semester(self):
        """Without holidays, Week 9 Tue falls on the naive date."""
        sem = SemesterContext(
            start=date(2026, 1, 12),
            end=date(2026, 5, 1),
            meeting_days=["tuesday", "thursday"],
        )
        result = resolve_date("Week 9 Tuesday", sem)
        assert result.value == date(2026, 3, 10)


# ---------------------------------------------------------------------------
# Layer 2b — Class/Lecture-relative patterns
# ---------------------------------------------------------------------------


class TestClassRelative:
    """Tests for 'Class N', 'Lecture N', 'Wednesday in Class 3', etc.

    Semester: start=Jan 12 (Mon), meeting_days=[tuesday, thursday].
    So class meetings are:
      Class 1 = Jan 13 (Tue), Class 2 = Jan 15 (Thu),
      Class 3 = Jan 20 (Tue), Class 4 = Jan 22 (Thu), ...
    """

    def test_class_1(self, semester):
        """Class 1 → first meeting = Jan 13 (Tuesday)."""
        result = resolve_date("Class 1", semester)
        assert result.value == date(2026, 1, 13)
        assert result.method == "class_relative"
        assert result.confidence == 0.8

    def test_class_4(self, semester):
        """Class 4 → 4th meeting = Jan 22 (Thursday)."""
        result = resolve_date("Class 4", semester)
        assert result.value == date(2026, 1, 22)

    def test_lecture_3(self, semester):
        """'Lecture 3' works the same as 'Class 3'."""
        result = resolve_date("Lecture 3", semester)
        assert result.value == date(2026, 1, 20)
        assert result.method == "class_relative"

    def test_session_2(self, semester):
        result = resolve_date("Session 2", semester)
        assert result.value == date(2026, 1, 15)

    def test_class_with_day_name(self, semester):
        """'Class 3 Wed' → Wednesday of the week containing Class 3 (Jan 20 Tue)."""
        result = resolve_date("Class 3 Wed", semester)
        # Class 3 = Jan 20 (Tue), week's Wednesday = Jan 21
        assert result.value == date(2026, 1, 21)
        assert result.method == "class_relative"

    def test_day_in_class(self, semester):
        """'Wednesday in Class 3' → Wednesday of Class 3's week."""
        result = resolve_date("Wednesday in Class 3", semester)
        assert result.value == date(2026, 1, 21)

    def test_wednes_in_class(self, semester):
        """'wednes in Class 3' → handles truncated day abbreviation."""
        result = resolve_date("wednes in Class 3", semester)
        assert result.value == date(2026, 1, 21)
        assert result.method == "class_relative"

    def test_class_skips_holidays(self, semester):
        """Class meetings skip holiday dates.

        Spring Break: Mar 9–13. Meetings that would fall on Mar 10 (Tue)
        and Mar 12 (Thu) are skipped, so class numbers after that are offset.
        """
        # Without Spring Break there would be 16 meetings in 8 weeks (Jan 12 – Mar 5).
        # Class 16 = Mar 5 (Thu). Class 17 would naively be Mar 10 (Tue, Spring Break).
        # With holiday skip: Class 17 = Mar 17 (Tue, first meeting after break).
        result = resolve_date("Class 17", semester)
        assert result.value == date(2026, 3, 17)

    def test_class_beyond_semester(self, semester):
        """A class number beyond the semester falls through."""
        result = resolve_date("Class 999", semester)
        assert result.method != "class_relative"

    def test_day_of_lecture(self, semester):
        """'Tue of Lecture 4' pattern."""
        result = resolve_date("Tue of Lecture 4", semester)
        # Lecture 4 = Jan 22 (Thu), week's Tuesday = Jan 20
        assert result.value == date(2026, 1, 20)

    def test_week_pattern_takes_priority(self, semester):
        """'Week 3' should match week_relative before class_relative."""
        result = resolve_date("Week 3", semester)
        assert result.method == "week_relative"


# ---------------------------------------------------------------------------
# Layer 3 — dateparser fallback
# ---------------------------------------------------------------------------


class TestLayer3Dateparser:
    def test_full_date_with_year(self, semester):
        result = resolve_date("January 15, 2026", semester)
        assert result.value == date(2026, 1, 15)
        assert result.confidence == 0.7
        assert result.method == "dateparser"

    def test_us_date_format(self, semester):
        result = resolve_date("1/15/2026", semester)
        assert result.value == date(2026, 1, 15)
        assert result.method == "dateparser"

    def test_month_day_no_year(self, semester):
        """'Jan 15' inferred from semester start year."""
        result = resolve_date("Jan 15", semester)
        assert result.value == date(2026, 1, 15)

    def test_march_5(self, semester):
        result = resolve_date("March 5", semester)
        assert result.value == date(2026, 3, 5)

    def test_february_28(self, semester):
        result = resolve_date("February 28, 2026", semester)
        assert result.value == date(2026, 2, 28)

    def test_april_15(self, semester):
        result = resolve_date("April 15", semester)
        assert result.value == date(2026, 4, 15)

    def test_iso_format(self, semester):
        result = resolve_date("2026-01-20", semester)
        assert result.value == date(2026, 1, 20)

    def test_abbreviated_month_day(self, semester):
        result = resolve_date("Mar 25", semester)
        assert result.value == date(2026, 3, 25)


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
    def test_confidence_ordering(self, semester):
        """LLM (0.9) > week_relative (0.85) > dateparser (0.7)."""
        llm = resolve_date("Jan 15", semester, llm_resolved=date(2026, 1, 15))
        week = resolve_date("Week 1 Tuesday", semester)
        dp = resolve_date("January 15, 2026", semester)
        assert llm.confidence > week.confidence > dp.confidence

    def test_case_insensitive_tba(self, semester):
        for text in ["tba", "TBA", "Tba", "tBa"]:
            result = resolve_date(text, semester)
            assert result.value is None
            assert result.method == "ambiguous"

    def test_extra_whitespace_stripped(self, semester):
        result = resolve_date("  Week 3 Tuesday  ", semester)
        assert result.value == date(2026, 1, 27)

    def test_ambiguous_preserves_original_text(self, semester):
        result = resolve_date("See course website", semester)
        assert result.original_text == "See course website"

    def test_resolved_preserves_original_text(self, semester):
        result = resolve_date("Week 1 Tuesday", semester)
        assert result.original_text == "Week 1 Tuesday"

    def test_week_relative_method_string(self, semester):
        result = resolve_date("Week 5 Monday", semester)
        assert result.method == "week_relative"

    def test_dateparser_method_string(self, semester):
        result = resolve_date("February 1, 2026", semester)
        assert result.method == "dateparser"


# ---------------------------------------------------------------------------
# resolve_all_dates batch processing
# ---------------------------------------------------------------------------


class TestResolveAllDates:
    def test_empty_list(self, semester):
        result = resolve_all_dates([], semester)
        assert result == []

    def test_single_assessment_resolved(self, semester):
        assessments = [_make_assessment(raw="Week 3 Tuesday", resolved=None)]
        result = resolve_all_dates(assessments, semester)
        assert len(result) == 1
        assert result[0].due_date_resolved.value == "2026-01-27"
        assert result[0].due_date_resolved.confidence == 0.85

    def test_preserves_other_fields(self, semester):
        assessments = [_make_assessment(raw="Jan 20", resolved=None)]
        result = resolve_all_dates(assessments, semester)
        assert result[0].title.value == "Test Assessment"
        assert result[0].type.value == "homework"
        assert result[0].weight_percent.value == 10.0

    def test_multiple_assessments(self, semester):
        assessments = [
            _make_assessment(raw="Week 1 Tuesday", resolved=None),
            _make_assessment(raw="Week 3 Thursday", resolved=None),
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
        assert result[0].due_date_resolved.confidence == 0.9

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
        """If the existing resolved value isn't a valid ISO date, ignore it."""
        assessments = [_make_assessment(raw="Week 1 Thursday", resolved="not-a-date")]
        result = resolve_all_dates(assessments, semester)
        assert result[0].due_date_resolved.value == "2026-01-15"
        assert result[0].due_date_resolved.confidence == 0.85

    def test_does_not_mutate_input(self, semester):
        """Input list and its assessments must remain unchanged."""
        original = _make_assessment(raw="Week 1 Tuesday", resolved=None)
        assessments = [original]
        resolve_all_dates(assessments, semester)
        assert assessments[0].due_date_resolved.value is None
