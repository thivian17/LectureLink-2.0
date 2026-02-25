"""Tests for syllabus extraction Pydantic models."""

import json
import uuid

import pytest
from lecturelink_api.models.syllabus_models import (
    AssessmentType,
    ExtractedField,
    SyllabusExtraction,
    extraction_to_db_assessments,
)
from pydantic import ValidationError

# ---------------------------------------------------------------------------
# Fixtures
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


def _make_extraction(**overrides):
    base = {
        "course_name": _field("Introduction to Computer Science"),
        "course_code": _field("CS 101"),
        "instructor_name": _field("Dr. Smith"),
        "instructor_email": _field("smith@university.edu"),
        "office_hours": _field("Mon/Wed 2-3pm"),
        "grade_breakdown": [
            {
                "name": _field("Midterm Exams"),
                "weight_percent": _field(30.0),
                "drop_policy": None,
            },
            {
                "name": _field("Final Exam"),
                "weight_percent": _field(40.0),
            },
            {
                "name": _field("Homework"),
                "weight_percent": _field(20.0),
                "drop_policy": _field("lowest score dropped"),
            },
            {
                "name": _field("Participation"),
                "weight_percent": _field(10.0),
            },
        ],
        "assessments": [
            _make_assessment(),
            _make_assessment(
                title=_field("Final Exam"),
                due_date_raw=_field("December 15"),
                due_date_resolved=_field("2025-12-15"),
                weight_percent=_field(40.0),
                topics=["Chapters 1-12"],
            ),
            _make_assessment(
                title=_field("Homework 1"),
                type=_field("homework"),
                due_date_raw=_field("Sep 10"),
                due_date_resolved=_field("2025-09-10"),
                weight_percent=_field(5.0),
                topics=["Chapter 1"],
            ),
        ],
        "weekly_schedule": [
            {
                "week_number": 1,
                "date_range": _field("Aug 25 – Aug 29"),
                "topics": ["Course overview", "Intro to Python"],
                "readings": ["Chapter 1"],
                "due_items": [],
            },
            {
                "week_number": 2,
                "topics": ["Variables and types"],
            },
        ],
        "policies": {
            "late_policy": "10% penalty per day, max 3 days",
            "attendance": "Mandatory",
            "academic_integrity": "Zero tolerance for plagiarism",
        },
        "extraction_confidence": 0.92,
        "missing_sections": ["TA information"],
    }
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# ExtractedField tests
# ---------------------------------------------------------------------------

class TestExtractedField:
    def test_valid_string_value(self):
        f = ExtractedField(value="CS 101", confidence=0.95, source_text="Course: CS 101")
        assert f.value == "CS 101"
        assert f.confidence == 0.95
        assert f.source_text == "Course: CS 101"

    def test_valid_float_value(self):
        f = ExtractedField(value=25.0, confidence=0.8)
        assert f.value == 25.0
        assert f.source_text is None

    def test_null_value(self):
        f = ExtractedField(value=None, confidence=0.0)
        assert f.value is None

    def test_confidence_at_boundaries(self):
        ExtractedField(value="x", confidence=0.0)
        ExtractedField(value="x", confidence=1.0)

    def test_confidence_below_zero_rejected(self):
        with pytest.raises(ValidationError) as exc_info:
            ExtractedField(value="x", confidence=-0.1)
        assert "greater than or equal to 0" in str(exc_info.value)

    def test_confidence_above_one_rejected(self):
        with pytest.raises(ValidationError) as exc_info:
            ExtractedField(value="x", confidence=1.1)
        assert "less than or equal to 1" in str(exc_info.value)


# ---------------------------------------------------------------------------
# AssessmentType tests
# ---------------------------------------------------------------------------

class TestAssessmentType:
    def test_all_values(self):
        expected = {
            "exam", "quiz", "homework", "project", "lab",
            "paper", "presentation", "participation", "other",
        }
        assert {t.value for t in AssessmentType} == expected

    def test_is_str_enum(self):
        assert isinstance(AssessmentType.exam, str)
        assert AssessmentType.exam == "exam"


# ---------------------------------------------------------------------------
# SyllabusExtraction validation tests
# ---------------------------------------------------------------------------

class TestSyllabusExtraction:
    def test_valid_full_extraction(self):
        data = _make_extraction()
        extraction = SyllabusExtraction(**data)

        assert extraction.course_name.value == "Introduction to Computer Science"
        assert extraction.course_code.value == "CS 101"
        assert extraction.instructor_name.value == "Dr. Smith"
        assert len(extraction.grade_breakdown) == 4
        assert len(extraction.assessments) == 3
        assert len(extraction.weekly_schedule) == 2
        assert extraction.policies["late_policy"] == "10% penalty per day, max 3 days"
        assert extraction.extraction_confidence == 0.92
        assert extraction.missing_sections == ["TA information"]

    def test_minimal_extraction(self):
        """Only required fields, everything optional left out."""
        data = {
            "course_name": _field("Math 200"),
            "grade_breakdown": [],
            "assessments": [],
            "weekly_schedule": [],
            "extraction_confidence": 0.5,
        }
        extraction = SyllabusExtraction(**data)
        assert extraction.course_code is None
        assert extraction.instructor_name is None
        assert extraction.policies == {}
        assert extraction.missing_sections == []

    def test_extraction_confidence_validated(self):
        data = _make_extraction(extraction_confidence=1.5)
        with pytest.raises(ValidationError):
            SyllabusExtraction(**data)

    def test_grade_component_with_drop_policy(self):
        data = _make_extraction()
        extraction = SyllabusExtraction(**data)
        hw = extraction.grade_breakdown[2]
        assert hw.drop_policy is not None
        assert hw.drop_policy.value == "lowest score dropped"

    def test_weekly_schedule_defaults(self):
        data = _make_extraction()
        extraction = SyllabusExtraction(**data)
        week2 = extraction.weekly_schedule[1]
        assert week2.date_range is None
        assert week2.readings == []
        assert week2.due_items == []


# ---------------------------------------------------------------------------
# extraction_to_db_assessments tests
# ---------------------------------------------------------------------------

class TestExtractionToDbAssessments:
    def test_produces_correct_rows(self):
        extraction = SyllabusExtraction(**_make_extraction())
        course_id = str(uuid.uuid4())
        syllabus_id = str(uuid.uuid4())

        rows = extraction_to_db_assessments(extraction, course_id, syllabus_id)

        assert len(rows) == 3

        midterm = rows[0]
        assert midterm["course_id"] == course_id
        assert midterm["syllabus_id"] == syllabus_id
        assert midterm["title"] == "Midterm Exam"
        assert midterm["type"] == "exam"
        assert midterm["due_date"] == "2025-10-16"
        assert midterm["due_date_raw"] == "Week 7 Thursday"
        assert midterm["is_date_ambiguous"] is False
        assert midterm["weight_percent"] == 25.0
        assert midterm["topics"] == ["Chapters 1-5"]
        # id should be a valid UUID
        uuid.UUID(midterm["id"])

    def test_ambiguous_date_flagged(self):
        """When raw date exists but resolved is None, is_date_ambiguous should be True."""
        assessment = _make_assessment(
            due_date_raw=_field("sometime in October"),
            due_date_resolved=_field(None),
        )
        data = _make_extraction(assessments=[assessment])
        extraction = SyllabusExtraction(**data)

        rows = extraction_to_db_assessments(extraction, "cid", "sid")
        assert rows[0]["is_date_ambiguous"] is True
        assert rows[0]["due_date"] is None

    def test_no_date_not_ambiguous(self):
        """When both raw and resolved are None, not ambiguous — just missing."""
        assessment = _make_assessment(
            due_date_raw=_field(None),
            due_date_resolved=_field(None),
        )
        data = _make_extraction(assessments=[assessment])
        extraction = SyllabusExtraction(**data)

        rows = extraction_to_db_assessments(extraction, "cid", "sid")
        assert rows[0]["is_date_ambiguous"] is False

    def test_unique_ids(self):
        extraction = SyllabusExtraction(**_make_extraction())
        rows = extraction_to_db_assessments(extraction, "cid", "sid")
        ids = [r["id"] for r in rows]
        assert len(ids) == len(set(ids))

    def test_empty_assessments(self):
        data = _make_extraction(assessments=[])
        extraction = SyllabusExtraction(**data)
        rows = extraction_to_db_assessments(extraction, "cid", "sid")
        assert rows == []

    def test_row_keys_match_db_schema(self):
        """Every row should have exactly the keys matching the assessments table."""
        expected_keys = {
            "id", "course_id", "syllabus_id", "title", "type",
            "due_date", "due_date_raw", "is_date_ambiguous",
            "weight_percent", "topics",
        }
        extraction = SyllabusExtraction(**_make_extraction())
        rows = extraction_to_db_assessments(extraction, "cid", "sid")
        for row in rows:
            assert set(row.keys()) == expected_keys


# ---------------------------------------------------------------------------
# JSON schema compatibility tests (for Gemini constrained decoding)
# ---------------------------------------------------------------------------

class TestJsonSchemaCompatibility:
    def test_syllabus_extraction_produces_valid_json_schema(self):
        schema = SyllabusExtraction.model_json_schema()

        # Top-level must be an object type
        assert schema["type"] == "object"
        assert "properties" in schema

        # Required fields should be present
        assert "course_name" in schema["properties"]
        assert "assessments" in schema["properties"]
        assert "grade_breakdown" in schema["properties"]

    def test_schema_is_json_serializable(self):
        """Gemini accepts the schema as a JSON string; it must serialize cleanly."""
        schema = SyllabusExtraction.model_json_schema()
        serialized = json.dumps(schema)
        roundtripped = json.loads(serialized)
        assert roundtripped == schema

    def test_extracted_field_schema_has_descriptions(self):
        schema = ExtractedField.model_json_schema()
        props = schema["properties"]
        for key in ("value", "confidence", "source_text"):
            assert "description" in props[key], f"Missing description on ExtractedField.{key}"

    def test_roundtrip_through_json(self):
        """Model -> JSON string -> Model should be lossless."""
        data = _make_extraction()
        original = SyllabusExtraction(**data)
        json_str = original.model_dump_json()
        restored = SyllabusExtraction.model_validate_json(json_str)
        assert original == restored

    def test_schema_definitions_include_all_models(self):
        """The top-level schema should reference all nested model definitions."""
        schema = SyllabusExtraction.model_json_schema()
        defs = schema.get("$defs", {})
        expected_models = {"ExtractedField", "AssessmentExtraction", "GradeComponent", "WeeklyScheduleEntry"}
        assert expected_models.issubset(set(defs.keys()))
