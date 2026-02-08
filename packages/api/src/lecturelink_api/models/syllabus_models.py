"""Pydantic models for Gemini syllabus extraction output.

These models define the structured JSON schema used with Gemini's constrained
decoding (response_mime_type="application/json" + response_json_schema).
Field descriptions guide the LLM's extraction behavior.
"""

from __future__ import annotations

import uuid
from enum import StrEnum

from pydantic import BaseModel, Field


class ExtractedField(BaseModel):
    """A wrapper that attaches confidence and provenance to any extracted value."""

    value: str | float | None = Field(
        description="The extracted value. Use a string for text, a float for numbers, or null if not found."
    )
    confidence: float = Field(
        ge=0.0,
        le=1.0,
        description="Confidence score from 0.0 (no confidence) to 1.0 (certain).",
    )
    source_text: str | None = Field(
        default=None,
        description="The exact text span from the syllabus where this value was found.",
    )


class AssessmentType(StrEnum):
    """Recognized assessment categories."""

    exam = "exam"
    quiz = "quiz"
    homework = "homework"
    project = "project"
    lab = "lab"
    paper = "paper"
    presentation = "presentation"
    participation = "participation"
    other = "other"


class AssessmentExtraction(BaseModel):
    """A single assessment extracted from the syllabus."""

    title: ExtractedField = Field(description="Name or title of the assessment.")
    type: ExtractedField = Field(
        description="Assessment category. value must be one of: "
        "exam, quiz, homework, project, lab, paper, presentation, participation, other."
    )
    due_date_raw: ExtractedField = Field(
        description="Original due-date text as written in the syllabus (e.g. 'Week 7 Thursday')."
    )
    due_date_resolved: ExtractedField = Field(
        description="Resolved calendar date in YYYY-MM-DD format, or null if ambiguous."
    )
    weight_percent: ExtractedField = Field(
        description="Grade weight as a percentage (e.g. 25.0 for 25%)."
    )
    topics: list[str] = Field(
        default_factory=list,
        description="Topics or chapters covered by this assessment.",
    )


class GradeComponent(BaseModel):
    """A single item in the course grade breakdown."""

    name: ExtractedField = Field(description="Name of the grade component (e.g. 'Midterm Exams').")
    weight_percent: ExtractedField = Field(
        description="Percentage weight of this component in the final grade."
    )
    drop_policy: ExtractedField | None = Field(
        default=None,
        description="Drop policy if any (e.g. 'lowest quiz dropped').",
    )


class WeeklyScheduleEntry(BaseModel):
    """One week of the course schedule."""

    week_number: int = Field(description="Week number in the semester (1-indexed).")
    date_range: ExtractedField | None = Field(
        default=None,
        description="Date range for this week (e.g. 'Jan 15 – Jan 19').",
    )
    topics: list[str] = Field(description="Topics covered during this week.")
    readings: list[str] = Field(
        default_factory=list,
        description="Assigned readings for this week.",
    )
    due_items: list[str] = Field(
        default_factory=list,
        description="Items due during this week.",
    )


class SyllabusExtraction(BaseModel):
    """Complete structured extraction from a course syllabus."""

    course_name: ExtractedField = Field(description="Full name of the course.")
    course_code: ExtractedField | None = Field(
        default=None,
        description="Course code (e.g. 'CS 101').",
    )
    instructor_name: ExtractedField | None = Field(
        default=None,
        description="Primary instructor's name.",
    )
    instructor_email: ExtractedField | None = Field(
        default=None,
        description="Primary instructor's email address.",
    )
    office_hours: ExtractedField | None = Field(
        default=None,
        description="Office hours schedule.",
    )
    grade_breakdown: list[GradeComponent] = Field(
        description="Complete grade breakdown for the course."
    )
    assessments: list[AssessmentExtraction] = Field(
        description="All individual assessments found in the syllabus."
    )
    weekly_schedule: list[WeeklyScheduleEntry] = Field(
        description="Week-by-week course schedule."
    )
    policies: dict[str, str] = Field(
        default_factory=dict,
        description="Course policies keyed by category (e.g. 'late_policy', 'attendance', 'academic_integrity').",
    )
    extraction_confidence: float = Field(
        ge=0.0,
        le=1.0,
        description="Overall confidence in the extraction quality (0.0–1.0).",
    )
    missing_sections: list[str] = Field(
        default_factory=list,
        description="Expected syllabus sections that were not found in the document.",
    )


def extraction_to_db_assessments(
    extraction: SyllabusExtraction,
    course_id: str,
    syllabus_id: str,
) -> list[dict]:
    """Convert extracted assessments into dicts matching the assessments DB table.

    Returns a list of dicts with keys: id, course_id, syllabus_id, title, type,
    due_date, due_date_raw, is_date_ambiguous, weight_percent, topics.
    """
    rows: list[dict] = []
    for a in extraction.assessments:
        resolved = a.due_date_resolved.value if a.due_date_resolved.value else None
        raw = a.due_date_raw.value if a.due_date_raw.value else None

        # A date is ambiguous when raw text exists but couldn't be resolved to a date
        is_ambiguous = raw is not None and resolved is None

        weight = a.weight_percent.value
        if isinstance(weight, str):
            try:
                weight = float(weight)
            except (ValueError, TypeError):
                weight = None

        rows.append(
            {
                "id": str(uuid.uuid4()),
                "course_id": course_id,
                "syllabus_id": syllabus_id,
                "title": str(a.title.value) if a.title.value is not None else "Untitled",
                "type": str(a.type.value) if a.type.value is not None else "other",
                "due_date": str(resolved) if resolved else None,
                "due_date_raw": str(raw) if raw else None,
                "is_date_ambiguous": is_ambiguous,
                "weight_percent": float(weight) if weight is not None else None,
                "topics": a.topics,
            }
        )
    return rows
