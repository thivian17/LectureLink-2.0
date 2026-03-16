"""Tests for syllabus validation logic and post-processing."""

from __future__ import annotations

from datetime import date

import pytest
from lecturelink_api.agents.syllabus_processor import (
    _fill_missing_fields,
    _normalize_assessment_types,
    _reconcile_assessment_weights,
    finalize_extraction,
    post_process_extraction,
    validate_assessment_completeness,
    validate_date_boundaries,
    validate_grade_weights,
    validate_no_duplicates,
    validate_no_near_duplicates,
)
from lecturelink_api.models.syllabus_models import SyllabusExtraction

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _field(value, confidence=0.9, source_text=None):
    """Shorthand for building an ExtractedField dict."""
    return {"value": value, "confidence": confidence, "source_text": source_text}


def _make_assessment(**overrides):
    base = {
        "title": _field("Midterm Exam"),
        "type": _field("exam"),
        "due_date_raw": _field("Week 7 Thursday"),
        "due_date_resolved": _field("2025-10-16"),
        "weight_percent": _field(25.0),
        "topics": ["Chapters 1-5"],
    }
    base.update(overrides)
    return base


def _make_grade_component(name="Exams", weight=50.0, **overrides):
    base = {
        "name": _field(name),
        "weight_percent": _field(weight),
        "drop_policy": None,
    }
    base.update(overrides)
    return base


def _make_extraction(**overrides):
    base = {
        "course_name": _field("Introduction to CS"),
        "course_code": _field("CS 101"),
        "instructor_name": _field("Dr. Smith"),
        "instructor_email": _field("smith@uni.edu"),
        "office_hours": _field("Mon/Wed 2-3pm"),
        "grade_breakdown": [
            _make_grade_component("Midterm", 30.0),
            _make_grade_component("Final", 40.0),
            _make_grade_component("Homework", 20.0),
            _make_grade_component("Participation", 10.0),
        ],
        "assessments": [
            _make_assessment(),
            _make_assessment(
                title=_field("Final Exam"),
                due_date_raw=_field("December 15"),
                due_date_resolved=_field("2025-12-15"),
                weight_percent=_field(40.0),
                topics=["All chapters"],
            ),
        ],
        "weekly_schedule": [
            {
                "week_number": 1,
                "date_range": _field("Aug 25 – Aug 29"),
                "topics": ["Intro"],
                "readings": [],
                "due_items": [],
            }
        ],
        "policies": {"late_policy": "10% per day"},
        "extraction_confidence": 0.9,
        "missing_sections": [],
    }
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# Grade weight validation
# ---------------------------------------------------------------------------


class TestGradeWeightValidation:
    def test_exact_100_passes(self):
        data = _make_extraction()  # 30+40+20+10 = 100
        extraction = SyllabusExtraction(**data)
        issues = validate_grade_weights(extraction)
        assert issues == []

    def test_98_percent_passes(self):
        """98% is within the 2% tolerance."""
        data = _make_extraction(
            grade_breakdown=[
                _make_grade_component("Midterm", 28.0),
                _make_grade_component("Final", 40.0),
                _make_grade_component("Homework", 20.0),
                _make_grade_component("Participation", 10.0),
            ]
        )
        extraction = SyllabusExtraction(**data)
        issues = validate_grade_weights(extraction)
        assert issues == []

    def test_102_percent_passes(self):
        """102% is within the 2% tolerance (rounding edge case)."""
        data = _make_extraction(
            grade_breakdown=[
                _make_grade_component("Midterm", 32.0),
                _make_grade_component("Final", 40.0),
                _make_grade_component("Homework", 20.0),
                _make_grade_component("Participation", 10.0),
            ]
        )
        extraction = SyllabusExtraction(**data)
        issues = validate_grade_weights(extraction)
        assert issues == []

    def test_85_percent_fails(self):
        """85% is well below tolerance — should fail."""
        data = _make_extraction(
            grade_breakdown=[
                _make_grade_component("Midterm", 25.0),
                _make_grade_component("Final", 35.0),
                _make_grade_component("Homework", 15.0),
                _make_grade_component("Participation", 10.0),
            ]
        )
        extraction = SyllabusExtraction(**data)
        issues = validate_grade_weights(extraction)
        assert len(issues) == 1
        assert "85.0%" in issues[0]

    def test_110_percent_fails(self):
        """110% exceeds tolerance."""
        data = _make_extraction(
            grade_breakdown=[
                _make_grade_component("Midterm", 40.0),
                _make_grade_component("Final", 40.0),
                _make_grade_component("Homework", 20.0),
                _make_grade_component("Participation", 10.0),
            ]
        )
        extraction = SyllabusExtraction(**data)
        issues = validate_grade_weights(extraction)
        assert len(issues) == 1
        assert "110.0%" in issues[0]

    def test_empty_grade_breakdown_fails(self):
        """No grade components means 0% total — should fail."""
        data = _make_extraction(grade_breakdown=[])
        extraction = SyllabusExtraction(**data)
        issues = validate_grade_weights(extraction)
        assert len(issues) == 1
        assert "0.0%" in issues[0]


# ---------------------------------------------------------------------------
# Date boundary validation
# ---------------------------------------------------------------------------


class TestDateBoundaryValidation:
    def test_dates_within_semester_pass(self):
        data = _make_extraction()
        extraction = SyllabusExtraction(**data)
        issues = validate_date_boundaries(
            extraction,
            semester_start=date(2025, 8, 25),
            semester_end=date(2025, 12, 20),
        )
        assert issues == []

    def test_date_before_semester_start(self):
        data = _make_extraction(
            assessments=[
                _make_assessment(
                    title=_field("Early Quiz"),
                    due_date_resolved=_field("2025-08-01"),
                ),
            ]
        )
        extraction = SyllabusExtraction(**data)
        issues = validate_date_boundaries(
            extraction,
            semester_start=date(2025, 8, 25),
            semester_end=date(2025, 12, 20),
        )
        assert len(issues) == 1
        assert "before semester start" in issues[0]
        assert "Early Quiz" in issues[0]

    def test_date_after_semester_end(self):
        data = _make_extraction(
            assessments=[
                _make_assessment(
                    title=_field("Late Final"),
                    due_date_resolved=_field("2026-01-15"),
                ),
            ]
        )
        extraction = SyllabusExtraction(**data)
        issues = validate_date_boundaries(
            extraction,
            semester_start=date(2025, 8, 25),
            semester_end=date(2025, 12, 20),
        )
        assert len(issues) == 1
        assert "after semester end" in issues[0]
        assert "Late Final" in issues[0]

    def test_null_resolved_date_is_skipped(self):
        """Assessments with unresolved dates shouldn't trigger boundary checks."""
        data = _make_extraction(
            assessments=[
                _make_assessment(due_date_resolved=_field(None)),
            ]
        )
        extraction = SyllabusExtraction(**data)
        issues = validate_date_boundaries(
            extraction,
            semester_start=date(2025, 8, 25),
            semester_end=date(2025, 12, 20),
        )
        assert issues == []

    def test_boundary_dates_are_inclusive(self):
        """Dates exactly on semester start/end should pass."""
        data = _make_extraction(
            assessments=[
                _make_assessment(
                    title=_field("First Day Quiz"),
                    due_date_resolved=_field("2025-08-25"),
                ),
                _make_assessment(
                    title=_field("Last Day Exam"),
                    due_date_resolved=_field("2025-12-20"),
                ),
            ]
        )
        extraction = SyllabusExtraction(**data)
        issues = validate_date_boundaries(
            extraction,
            semester_start=date(2025, 8, 25),
            semester_end=date(2025, 12, 20),
        )
        assert issues == []


# ---------------------------------------------------------------------------
# Duplicate assessment detection
# ---------------------------------------------------------------------------


class TestDuplicateDetection:
    def test_no_duplicates(self):
        data = _make_extraction()
        extraction = SyllabusExtraction(**data)
        issues = validate_no_duplicates(extraction)
        assert issues == []

    def test_exact_duplicate_detected(self):
        dup = _make_assessment(
            title=_field("Midterm Exam"),
            due_date_resolved=_field("2025-10-16"),
        )
        data = _make_extraction(assessments=[dup, dup])
        extraction = SyllabusExtraction(**data)
        issues = validate_no_duplicates(extraction)
        assert len(issues) == 1
        assert "Duplicate" in issues[0]
        assert "Midterm Exam" in issues[0]

    def test_same_title_different_date_ok(self):
        a1 = _make_assessment(
            title=_field("Quiz"),
            due_date_resolved=_field("2025-10-01"),
        )
        a2 = _make_assessment(
            title=_field("Quiz"),
            due_date_resolved=_field("2025-11-01"),
        )
        data = _make_extraction(assessments=[a1, a2])
        extraction = SyllabusExtraction(**data)
        issues = validate_no_duplicates(extraction)
        assert issues == []

    def test_same_date_different_title_ok(self):
        a1 = _make_assessment(
            title=_field("Midterm"),
            due_date_resolved=_field("2025-10-16"),
        )
        a2 = _make_assessment(
            title=_field("Project"),
            due_date_resolved=_field("2025-10-16"),
        )
        data = _make_extraction(assessments=[a1, a2])
        extraction = SyllabusExtraction(**data)
        issues = validate_no_duplicates(extraction)
        assert issues == []


# ---------------------------------------------------------------------------
# Assessment completeness
# ---------------------------------------------------------------------------


class TestAssessmentCompleteness:
    def test_complete_assessments_pass(self):
        data = _make_extraction()
        extraction = SyllabusExtraction(**data)
        issues = validate_assessment_completeness(extraction)
        assert issues == []

    def test_missing_title_detected(self):
        data = _make_extraction(
            assessments=[_make_assessment(title=_field(None))]
        )
        extraction = SyllabusExtraction(**data)
        issues = validate_assessment_completeness(extraction)
        assert len(issues) == 1
        assert "missing a title" in issues[0]

    def test_missing_type_detected(self):
        data = _make_extraction(
            assessments=[_make_assessment(type=_field(None))]
        )
        extraction = SyllabusExtraction(**data)
        issues = validate_assessment_completeness(extraction)
        assert len(issues) == 1
        assert "missing a type" in issues[0]


# ---------------------------------------------------------------------------
# Post-processing
# ---------------------------------------------------------------------------


class TestPostProcessExtraction:
    """post_process_extraction handles structural cleanup and grade weights.
    finalize_extraction (run after date resolution) handles confidence,
    date boundaries, and low-confidence flagging.
    """

    def test_recomputes_confidence(self):
        data = _make_extraction()
        semester_ctx = {
            "semester_start": "2025-08-25",
            "semester_end": "2025-12-20",
        }
        extraction = post_process_extraction(data, semester_ctx)
        result = finalize_extraction(extraction, semester_ctx)
        assert isinstance(result.extraction_confidence, float)
        assert 0.0 <= result.extraction_confidence <= 1.0
        assert result.extraction_confidence == pytest.approx(0.9, abs=0.01)

    def test_flags_low_confidence_fields(self):
        data = _make_extraction(
            instructor_email=_field("maybe@uni.edu", confidence=0.5),
        )
        semester_ctx = {
            "semester_start": "2025-08-25",
            "semester_end": "2025-12-20",
        }
        extraction = post_process_extraction(data, semester_ctx)
        result = finalize_extraction(extraction, semester_ctx)
        assert any("low_confidence:instructor_email" in s for s in result.missing_sections)

    def test_flags_weight_issues(self):
        data = _make_extraction(
            grade_breakdown=[
                _make_grade_component("Midterm", 20.0),
                _make_grade_component("Final", 30.0),
            ]
        )
        semester_ctx = {
            "semester_start": "2025-08-25",
            "semester_end": "2025-12-20",
        }
        result = post_process_extraction(data, semester_ctx)
        assert any("50.0%" in s for s in result.missing_sections)

    def test_flags_date_boundary_issues(self):
        data = _make_extraction(
            assessments=[
                _make_assessment(
                    title=_field("Late Final"),
                    due_date_resolved=_field("2026-03-01"),
                ),
            ]
        )
        semester_ctx = {
            "semester_start": "2025-08-25",
            "semester_end": "2025-12-20",
        }
        extraction = post_process_extraction(data, semester_ctx)
        result = finalize_extraction(extraction, semester_ctx)
        assert any("after semester end" in s for s in result.missing_sections)

    def test_returns_valid_syllabus_extraction(self):
        data = _make_extraction()
        semester_ctx = {
            "semester_start": "2025-08-25",
            "semester_end": "2025-12-20",
        }
        result = post_process_extraction(data, semester_ctx)
        assert isinstance(result, SyllabusExtraction)
        assert result.course_name.value == "Introduction to CS"

    def test_handles_missing_semester_context(self):
        """Should work gracefully when semester dates are not provided."""
        data = _make_extraction()
        result = post_process_extraction(data, {})
        assert isinstance(result, SyllabusExtraction)

    def test_low_confidence_assessment_fields_flagged(self):
        data = _make_extraction(
            assessments=[
                _make_assessment(
                    title=_field("Fuzzy Quiz", confidence=0.5),
                    weight_percent=_field(10.0, confidence=0.4),
                ),
            ]
        )
        semester_ctx = {
            "semester_start": "2025-08-25",
            "semester_end": "2025-12-20",
        }
        extraction = post_process_extraction(data, semester_ctx)
        result = finalize_extraction(extraction, semester_ctx)
        low_conf_entries = [s for s in result.missing_sections if "low_confidence:" in s]
        assert len(low_conf_entries) >= 2  # title + weight_percent


# ---------------------------------------------------------------------------
# Assessment type normalization
# ---------------------------------------------------------------------------


class TestAssessmentTypeNormalization:
    def test_lowercase_preserved(self):
        data = _make_extraction(assessments=[_make_assessment(type=_field("quiz"))])
        extraction = SyllabusExtraction(**data)
        _normalize_assessment_types(extraction)
        assert extraction.assessments[0].type.value == "quiz"

    def test_uppercase_normalized(self):
        data = _make_extraction(assessments=[_make_assessment(type=_field("Exam"))])
        extraction = SyllabusExtraction(**data)
        _normalize_assessment_types(extraction)
        assert extraction.assessments[0].type.value == "exam"

    def test_midterm_maps_to_exam(self):
        data = _make_extraction(assessments=[_make_assessment(type=_field("midterm"))])
        extraction = SyllabusExtraction(**data)
        _normalize_assessment_types(extraction)
        assert extraction.assessments[0].type.value == "exam"

    def test_peer_eval_maps_to_other(self):
        data = _make_extraction(
            assessments=[_make_assessment(type=_field("peer evaluation"))],
        )
        extraction = SyllabusExtraction(**data)
        _normalize_assessment_types(extraction)
        assert extraction.assessments[0].type.value == "other"

    def test_unknown_maps_to_other(self):
        data = _make_extraction(
            assessments=[_make_assessment(type=_field("portfolio"))],
        )
        extraction = SyllabusExtraction(**data)
        _normalize_assessment_types(extraction)
        assert extraction.assessments[0].type.value == "other"


# ---------------------------------------------------------------------------
# Fill missing fields
# ---------------------------------------------------------------------------


class TestFillMissingFields:
    def test_missing_title_defaults(self):
        data = _make_extraction(assessments=[_make_assessment(title=_field(None))])
        extraction = SyllabusExtraction(**data)
        _fill_missing_fields(extraction)
        assert extraction.assessments[0].title.value == "Assessment 1"
        assert extraction.assessments[0].title.confidence == 0.1

    def test_missing_type_defaults(self):
        data = _make_extraction(assessments=[_make_assessment(type=_field(None))])
        extraction = SyllabusExtraction(**data)
        _fill_missing_fields(extraction)
        assert extraction.assessments[0].type.value == "other"
        assert extraction.assessments[0].type.confidence == 0.1

    def test_string_weight_to_float(self):
        data = _make_extraction(
            assessments=[_make_assessment(weight_percent=_field("15.5"))],
        )
        extraction = SyllabusExtraction(**data)
        _fill_missing_fields(extraction)
        assert extraction.assessments[0].weight_percent.value == 15.5

    def test_invalid_weight_cleared(self):
        data = _make_extraction(
            assessments=[_make_assessment(weight_percent=_field("not_a_number"))],
        )
        extraction = SyllabusExtraction(**data)
        _fill_missing_fields(extraction)
        assert extraction.assessments[0].weight_percent.value is None
        assert extraction.assessments[0].weight_percent.confidence == 0.0


# ---------------------------------------------------------------------------
# Weight reconciliation
# ---------------------------------------------------------------------------


class TestWeightReconciliation:
    def test_infers_weight_from_grade_breakdown(self):
        """Single matching assessment gets weight from grade breakdown."""
        data = _make_extraction(
            grade_breakdown=[
                _make_grade_component("Participation", 10.0),
                _make_grade_component("Final", 40.0),
                _make_grade_component("Homework", 50.0),
            ],
            assessments=[
                _make_assessment(
                    title=_field("Participation"),
                    type=_field("participation"),
                    weight_percent=_field(None),
                ),
            ],
        )
        extraction = SyllabusExtraction(**data)
        _reconcile_assessment_weights(extraction)
        assert extraction.assessments[0].weight_percent.value == 10.0
        assert extraction.assessments[0].weight_percent.confidence == 0.6

    def test_does_not_infer_when_multiple_match(self):
        """Multiple assessments match a component — don't guess."""
        data = _make_extraction(
            grade_breakdown=[
                _make_grade_component("Homework", 30.0),
                _make_grade_component("Final", 70.0),
            ],
            assessments=[
                _make_assessment(
                    title=_field("Homework 1"),
                    weight_percent=_field(None),
                ),
                _make_assessment(
                    title=_field("Homework 2"),
                    weight_percent=_field(None),
                ),
            ],
        )
        extraction = SyllabusExtraction(**data)
        _reconcile_assessment_weights(extraction)
        assert extraction.assessments[0].weight_percent.value is None
        assert extraction.assessments[1].weight_percent.value is None


# ---------------------------------------------------------------------------
# Near-duplicate detection
# ---------------------------------------------------------------------------


class TestNearDuplicateDetection:
    def test_substring_duplicates_detected(self):
        data = _make_extraction(
            assessments=[
                _make_assessment(
                    title=_field("Midterm Exam"),
                    due_date_resolved=_field("2026-03-10"),
                ),
                _make_assessment(
                    title=_field("Midterm"),
                    due_date_resolved=_field("2026-03-10"),
                ),
            ],
        )
        extraction = SyllabusExtraction(**data)
        issues = validate_no_near_duplicates(extraction)
        assert len(issues) == 1
        assert "Possible duplicate" in issues[0]

    def test_same_title_different_date_ok(self):
        data = _make_extraction(
            assessments=[
                _make_assessment(
                    title=_field("Quiz"),
                    due_date_resolved=_field("2026-02-10"),
                ),
                _make_assessment(
                    title=_field("Quiz"),
                    due_date_resolved=_field("2026-03-10"),
                ),
            ],
        )
        extraction = SyllabusExtraction(**data)
        issues = validate_no_near_duplicates(extraction)
        assert len(issues) == 0

    def test_different_titles_same_date_ok(self):
        data = _make_extraction(
            assessments=[
                _make_assessment(
                    title=_field("Midterm"),
                    due_date_resolved=_field("2026-03-10"),
                ),
                _make_assessment(
                    title=_field("Project #1"),
                    due_date_resolved=_field("2026-03-10"),
                ),
            ],
        )
        extraction = SyllabusExtraction(**data)
        issues = validate_no_near_duplicates(extraction)
        assert len(issues) == 0

    def test_exact_same_titles_not_near_duplicate(self):
        """Exact same titles are caught by validate_no_duplicates, not here."""
        data = _make_extraction(
            assessments=[
                _make_assessment(
                    title=_field("Quiz"),
                    due_date_resolved=_field("2026-03-10"),
                ),
                _make_assessment(
                    title=_field("Quiz"),
                    due_date_resolved=_field("2026-03-10"),
                ),
            ],
        )
        extraction = SyllabusExtraction(**data)
        issues = validate_no_near_duplicates(extraction)
        assert len(issues) == 0


