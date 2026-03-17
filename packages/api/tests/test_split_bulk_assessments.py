"""Tests for the bulk assessment splitting post-processor."""

from __future__ import annotations

from lecturelink_api.agents.syllabus_processor import _split_bulk_assessments
from lecturelink_api.models.syllabus_models import (
    AssessmentExtraction,
    ExtractedField,
    SyllabusExtraction,
)


def _field(value, confidence=0.9, source_text=None):
    return ExtractedField(value=value, confidence=confidence, source_text=source_text)


def _make_assessment(title, atype="quiz", weight=None, due_raw="Ongoing"):
    return AssessmentExtraction(
        title=_field(title),
        type=_field(atype),
        due_date_raw=_field(due_raw),
        due_date_resolved=_field(None, confidence=0.0),
        weight_percent=_field(weight),
    )


def _make_extraction(assessments, schedule=None):
    return SyllabusExtraction(
        course_name=_field("Test Course"),
        course_code=_field("TEST 101"),
        instructor_name=_field("Test Prof"),
        instructor_email=_field("test@test.com"),
        office_hours=_field(None),
        grade_breakdown=[],
        assessments=assessments,
        weekly_schedule=schedule or [],
        policies={},
        extraction_confidence=0.0,
        missing_sections=[],
    )


class TestSplitBulkAssessments:
    def test_splits_quizzes_with_schedule_data(self):
        """4 Tableau Quizzes at 16% -> 4 individual quizzes at 4% each."""
        assessments = [
            _make_assessment("Tableau Quizzes", atype="quiz", weight=16.0),
        ]
        schedule = [
            {"week_number": 3, "topics": ["Design"], "due_items": ["Tableau Quiz 1"]},
            {"week_number": 5, "topics": ["Dashboards"], "due_items": ["Tableau Quiz 2"]},
            {"week_number": 7, "topics": ["Color"], "due_items": ["Tableau Quiz 3"]},
            {"week_number": 10, "topics": ["Storytelling"], "due_items": ["Tableau Quiz 4"]},
        ]

        extraction = _make_extraction(assessments, schedule)
        _split_bulk_assessments(extraction, schedule)

        quizzes = [a for a in extraction.assessments if "quiz" in str(a.title.value).lower()]
        assert len(quizzes) == 4
        assert all(a.weight_percent.value == 4.0 for a in quizzes)
        assert any("1" in str(a.title.value) for a in quizzes)
        assert any("4" in str(a.title.value) for a in quizzes)

    def test_splits_discussions_with_schedule_data(self):
        """6 Group Discussions at 9% -> 6 individual discussions at 1.5% each."""
        assessments = [
            _make_assessment("Group Discussions", atype="participation", weight=9.0),
        ]
        schedule = [
            {"week_number": 2, "topics": [], "due_items": ["Group Discussion 1"]},
            {"week_number": 3, "topics": [], "due_items": ["Group Discussion 2"]},
            {"week_number": 5, "topics": [], "due_items": ["Group Discussion 3"]},
            {"week_number": 7, "topics": [], "due_items": ["Group Discussion 4"]},
            {"week_number": 8, "topics": [], "due_items": ["Group Discussion 5"]},
            {"week_number": 10, "topics": [], "due_items": ["Group Discussion 6"]},
        ]

        extraction = _make_extraction(assessments, schedule)
        _split_bulk_assessments(extraction, schedule)

        discussions = [a for a in extraction.assessments if "discussion" in str(a.title.value).lower()]
        assert len(discussions) == 6
        assert all(a.weight_percent.value == 1.5 for a in discussions)

    def test_due_dates_assigned_from_schedule(self):
        """Split assessments get 'Class N' due dates from the schedule."""
        assessments = [
            _make_assessment("Quizzes", atype="quiz", weight=12.0),
        ]
        schedule = [
            {"week_number": 2, "topics": [], "due_items": ["Quiz 1"]},
            {"week_number": 4, "topics": [], "due_items": ["Quiz 2"]},
            {"week_number": 6, "topics": [], "due_items": ["Quiz 3"]},
        ]

        extraction = _make_extraction(assessments, schedule)
        _split_bulk_assessments(extraction, schedule)

        assert len(extraction.assessments) == 3
        due_dates = [str(a.due_date_raw.value) for a in extraction.assessments]
        assert "Class 2" in due_dates
        assert "Class 4" in due_dates
        assert "Class 6" in due_dates

    def test_does_not_split_single_assessments(self):
        """A single assessment with no numbered schedule matches stays as-is."""
        assessments = [
            _make_assessment("Final Project", atype="project", weight=30.0),
        ]
        schedule = [
            {"week_number": 12, "topics": [], "due_items": ["Final Project due"]},
        ]

        extraction = _make_extraction(assessments, schedule)
        _split_bulk_assessments(extraction, schedule)

        assert len(extraction.assessments) == 1
        assert extraction.assessments[0].title.value == "Final Project"

    def test_no_schedule_data_no_split(self):
        """Without schedule data, nothing gets split."""
        assessments = [
            _make_assessment("Quizzes", atype="quiz", weight=20.0),
        ]

        extraction = _make_extraction(assessments, [])
        _split_bulk_assessments(extraction, [])

        assert len(extraction.assessments) == 1

    def test_preserves_non_split_assessments(self):
        """Assessments that don't match any split pattern are preserved."""
        assessments = [
            _make_assessment("Tableau Quizzes", atype="quiz", weight=16.0),
            _make_assessment("Final Project", atype="project", weight=30.0),
            _make_assessment("Class Participation", atype="participation", weight=5.0),
        ]
        schedule = [
            {"week_number": 3, "topics": [], "due_items": ["Tableau Quiz 1"]},
            {"week_number": 5, "topics": [], "due_items": ["Tableau Quiz 2"]},
        ]

        extraction = _make_extraction(assessments, schedule)
        _split_bulk_assessments(extraction, schedule)

        titles = [str(a.title.value) for a in extraction.assessments]
        assert "Final Project" in titles
        assert "Class Participation" in titles
        # Original "Tableau Quizzes" replaced by 2 individual quizzes
        assert "Tableau Quizzes" not in titles
        assert any("Tableau Quiz 1" in t for t in titles)
        assert any("Tableau Quiz 2" in t for t in titles)

    def test_weight_math_correct(self):
        """Per-instance weight = total weight / instance count."""
        assessments = [
            _make_assessment("Weekly Exercises", atype="homework", weight=15.0),
        ]
        schedule = [
            {"week_number": i, "topics": [], "due_items": [f"Weekly Exercise {i}"]}
            for i in range(1, 6)
        ]

        extraction = _make_extraction(assessments, schedule)
        _split_bulk_assessments(extraction, schedule)

        assert len(extraction.assessments) == 5
        assert all(a.weight_percent.value == 3.0 for a in extraction.assessments)
