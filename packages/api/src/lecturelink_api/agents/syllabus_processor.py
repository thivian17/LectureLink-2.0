"""Multi-agent syllabus extraction pipeline using Google ADK.

Pipeline stages:
  1. ParallelExtraction – three agents run concurrently to extract
     schedule, grading, and course-info data

After the pipeline runs, merge_extraction_outputs() combines the three
structured outputs into a SyllabusExtraction dict, and post_process_extraction()
applies deterministic validation — no extra LLM call needed.
"""

from __future__ import annotations

import json
from datetime import date, datetime

from google.adk.agents import LlmAgent, ParallelAgent
from google.adk.tools import FunctionTool
from google.genai import types
from pydantic import BaseModel, Field

from lecturelink_api.models.syllabus_models import (
    AssessmentExtraction,
    ExtractedField,
    GradeComponent,
    SyllabusExtraction,
    WeeklyScheduleEntry,
)
from lecturelink_api.tools.document_tools import extract_document_text

# ---------------------------------------------------------------------------
# Intermediate output schemas (for Gemini constrained JSON decoding)
# ---------------------------------------------------------------------------


class ScheduleOutput(BaseModel):
    """Schema for the schedule extractor's constrained JSON output."""

    weekly_schedule: list[WeeklyScheduleEntry] = Field(
        description="Week-by-week course schedule extracted from the syllabus."
    )


class GradingOutput(BaseModel):
    """Schema for the grading extractor's constrained JSON output."""

    grade_breakdown: list[GradeComponent] = Field(
        description="Complete grade breakdown for the course."
    )
    assessments: list[AssessmentExtraction] = Field(
        description="All individual assessments found in the syllabus."
    )


class InfoOutput(BaseModel):
    """Schema for the course info extractor's constrained JSON output."""

    course_name: ExtractedField = Field(description="Full name of the course.")
    course_code: ExtractedField | None = Field(
        default=None, description="Course code (e.g. 'CS 101')."
    )
    instructor_name: ExtractedField | None = Field(
        default=None, description="Primary instructor's name."
    )
    instructor_email: ExtractedField | None = Field(
        default=None, description="Primary instructor's email address."
    )
    office_hours: ExtractedField | None = Field(
        default=None, description="Office hours schedule."
    )
    policies: dict[str, str] = Field(
        default_factory=dict,
        description="Course policies keyed by category.",
    )


# ---------------------------------------------------------------------------
# Stage 1 — Document Ingestion
# ---------------------------------------------------------------------------

ingestion_agent = LlmAgent(
    name="IngestionAgent",
    model="gemini-2.5-flash",
    instruction=(
        "Extract text from the uploaded document using the extract_document_text tool. "
        "Pass the file bytes, filename, and mime type."
    ),
    tools=[FunctionTool(func=extract_document_text)],
    output_key="raw_text",
)


# ---------------------------------------------------------------------------
# Stage 2 — Parallel Extraction (3 agents)
# ---------------------------------------------------------------------------

_SCHEDULE_INSTRUCTION = """\
You are an expert course schedule extractor. Analyze the syllabus text below and \
extract the complete week-by-week course schedule.

For each week, extract:
- week_number: The week number (1-indexed).
- date_range: The date range if specified (e.g. "Jan 15 – Jan 19"), with confidence \
and source_text. Leave null if no dates are given.
- topics: All topics covered that week.
- readings: Assigned readings for the week.
- due_items: Items due during the week (assignments, quizzes, exams, etc.).

Semester context for resolving relative dates: {semester_context}

Include every week mentioned in the syllabus, even if some fields are sparse. \
Set confidence (0.0–1.0) on each ExtractedField based on how clearly the information \
was stated, and populate source_text with the exact span from the document.

Syllabus text:
{raw_text}"""

_GRADING_INSTRUCTION = """\
You are an expert grading policy extractor. Analyze the syllabus text below and \
extract the complete grade breakdown and every individual assessment.

Grade breakdown — for each component extract:
- name: Component name (e.g. "Midterm Exams"), with confidence and source_text.
- weight_percent: Percentage weight in the final grade (e.g. 25.0 for 25%).
- drop_policy: Any drop policy (e.g. "lowest quiz dropped"), or null if none.

Individual assessments — for each one extract:
- title: Assessment name (e.g. "Midterm 1", "HW 3").
- type: One of: exam, quiz, homework, project, lab, paper, presentation, participation, other.
- due_date_raw: The original date text as written in the syllabus. For assessments that \
are ongoing throughout the semester (e.g. class participation, attendance), set this to "Ongoing".
- due_date_resolved: Resolved calendar date in YYYY-MM-DD format, or null if ambiguous or ongoing. \
IMPORTANT: When the syllabus uses relative references like "Week 5" or "Class 3", use the \
semester context below to calculate the exact date. Never resolve a date to a holiday/break period — \
if a week number falls on a break, skip the break week and count only teaching weeks.
- weight_percent: Grade weight as a percentage.
- topics: Related topics or chapters.

Semester context for resolving relative dates: {semester_context}

Express all weights as percentages (25.0 for 25%, not 0.25). If the syllabus uses \
point values, convert to percentages. Set confidence and source_text on every \
ExtractedField.

Syllabus text:
{raw_text}"""

_INFO_INSTRUCTION = """\
You are an expert course information extractor. Analyze the syllabus text below and \
extract course metadata and policies.

Extract:
- course_name: Full course name.
- course_code: Course code (e.g. "CS 101").
- instructor_name: Primary instructor's full name.
- instructor_email: Instructor's email address.
- office_hours: Office hours schedule as written.
- policies: A JSON object of course policies keyed by category. Use these keys where \
applicable: late_policy, attendance, academic_integrity, grading_scale, extra_credit, \
technology_policy, accommodation.

Set confidence (0.0–1.0) on each ExtractedField based on clarity, and include \
source_text with the exact span from the document.

Syllabus text:
{raw_text}"""


schedule_extractor = LlmAgent(
    name="ScheduleExtractor",
    model="gemini-2.5-flash",
    instruction=_SCHEDULE_INSTRUCTION,
    output_key="schedule_data",
    output_schema=ScheduleOutput,
    generate_content_config=types.GenerateContentConfig(
        temperature=0.1,
    ),
)

grading_extractor = LlmAgent(
    name="GradingExtractor",
    model="gemini-2.5-flash",
    instruction=_GRADING_INSTRUCTION,
    output_key="grading_data",
    output_schema=GradingOutput,
    generate_content_config=types.GenerateContentConfig(
        temperature=0.1,
    ),
)

info_extractor = LlmAgent(
    name="InfoExtractor",
    model="gemini-2.5-flash",
    instruction=_INFO_INSTRUCTION,
    output_key="info_data",
    output_schema=InfoOutput,
    generate_content_config=types.GenerateContentConfig(
        temperature=0.1,
    ),
)

parallel_extraction = ParallelAgent(
    name="ParallelExtraction",
    sub_agents=[schedule_extractor, grading_extractor, info_extractor],
)


# ---------------------------------------------------------------------------
# Full Pipeline
# ---------------------------------------------------------------------------

# Text extraction is handled externally by the service layer (deterministic,
# no LLM needed). The pipeline expects raw_text pre-populated in session state.
# After the pipeline runs, the service layer calls merge_extraction_outputs()
# to combine the three outputs, then post_process_extraction() for validation.
extraction_pipeline = parallel_extraction


# ---------------------------------------------------------------------------
# Merge parallel outputs (pure Python, no LLM)
# ---------------------------------------------------------------------------


def _parse_json(raw: str | dict | None) -> dict:
    """Parse a JSON string or pass through a dict; return empty dict on failure."""
    if raw is None:
        return {}
    if isinstance(raw, dict):
        return raw
    try:
        parsed = json.loads(raw)
        return parsed if isinstance(parsed, dict) else {}
    except (json.JSONDecodeError, TypeError):
        return {}


def merge_extraction_outputs(
    schedule_data: str | dict | None,
    grading_data: str | dict | None,
    info_data: str | dict | None,
) -> dict:
    """Merge the three parallel extractor outputs into a SyllabusExtraction-shaped dict.

    This replaces the former Validator LLM agent — a pure Python merge that
    takes milliseconds instead of an extra LLM round-trip.

    Args:
        schedule_data: ScheduleOutput JSON (has 'weekly_schedule').
        grading_data: GradingOutput JSON (has 'grade_breakdown', 'assessments').
        info_data: InfoOutput JSON (has course_name, course_code, etc.).

    Returns:
        A dict compatible with SyllabusExtraction(**result).
    """
    schedule = _parse_json(schedule_data)
    grading = _parse_json(grading_data)
    info = _parse_json(info_data)

    # Detect missing sections
    missing: list[str] = []
    if not info.get("course_name"):
        missing.append("course_name")
    if not info.get("course_code"):
        missing.append("course_code")
    if not info.get("instructor_name"):
        missing.append("instructor_name")
    if not info.get("instructor_email"):
        missing.append("instructor_email")
    if not info.get("office_hours"):
        missing.append("office_hours")
    if not grading.get("grade_breakdown"):
        missing.append("grade_breakdown")
    if not grading.get("assessments"):
        missing.append("assessments")
    if not schedule.get("weekly_schedule"):
        missing.append("weekly_schedule")
    if not info.get("policies"):
        missing.append("policies")

    return {
        # Course info
        "course_name": info.get("course_name", {"value": None, "confidence": 0.0}),
        "course_code": info.get("course_code"),
        "instructor_name": info.get("instructor_name"),
        "instructor_email": info.get("instructor_email"),
        "office_hours": info.get("office_hours"),
        "policies": info.get("policies", {}),
        # Grading
        "grade_breakdown": grading.get("grade_breakdown", []),
        "assessments": grading.get("assessments", []),
        # Schedule
        "weekly_schedule": schedule.get("weekly_schedule", []),
        # Metadata (recomputed by post_process_extraction)
        "extraction_confidence": 0.0,
        "missing_sections": missing,
    }


# ---------------------------------------------------------------------------
# Post-processing (pure Python, no LLM)
# ---------------------------------------------------------------------------


def _collect_confidences(extraction: SyllabusExtraction) -> list[float]:
    """Gather all confidence scores from ExtractedField instances in the extraction."""
    confidences: list[float] = []

    # Top-level ExtractedField attributes
    for attr in (
        "course_name", "course_code", "instructor_name",
        "instructor_email", "office_hours",
    ):
        field = getattr(extraction, attr, None)
        if field is not None and isinstance(field, ExtractedField):
            confidences.append(field.confidence)

    # Grade breakdown
    for comp in extraction.grade_breakdown:
        confidences.append(comp.name.confidence)
        confidences.append(comp.weight_percent.confidence)
        if comp.drop_policy is not None:
            confidences.append(comp.drop_policy.confidence)

    # Assessments
    for a in extraction.assessments:
        for attr in ("title", "type", "due_date_raw", "due_date_resolved", "weight_percent"):
            field = getattr(a, attr)
            if isinstance(field, ExtractedField):
                confidences.append(field.confidence)

    # Weekly schedule
    for week in extraction.weekly_schedule:
        if week.date_range is not None:
            confidences.append(week.date_range.confidence)

    return confidences


def _parse_date(value: str | float | None) -> date | None:
    """Try to parse a date string in YYYY-MM-DD format."""
    if value is None:
        return None
    try:
        return datetime.strptime(str(value), "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return None


def validate_grade_weights(extraction: SyllabusExtraction) -> list[str]:
    """Check that grade_breakdown weights sum to ~100% (98-102% tolerance)."""
    total = 0.0
    for comp in extraction.grade_breakdown:
        w = comp.weight_percent.value
        if w is not None:
            total += float(w)
    if not (98.0 <= total <= 102.0):
        return [f"Grade weights sum to {total:.1f}%, expected 98-102%"]
    return []


def validate_date_boundaries(
    extraction: SyllabusExtraction,
    semester_start: date,
    semester_end: date,
) -> list[str]:
    """Check that all resolved assessment dates fall within semester boundaries."""
    issues: list[str] = []
    for a in extraction.assessments:
        resolved = _parse_date(a.due_date_resolved.value)
        if resolved is None:
            continue
        title = a.title.value or "Untitled"
        if resolved < semester_start:
            issues.append(
                f"Assessment '{title}' due {resolved} is before semester start {semester_start}"
            )
        if resolved > semester_end:
            issues.append(
                f"Assessment '{title}' due {resolved} is after semester end {semester_end}"
            )
    return issues


def validate_no_duplicates(extraction: SyllabusExtraction) -> list[str]:
    """Check for duplicate assessments (same title + same due date)."""
    seen: set[tuple[str | None, str | None]] = set()
    issues: list[str] = []
    for a in extraction.assessments:
        title = str(a.title.value) if a.title.value is not None else None
        due = str(a.due_date_resolved.value) if a.due_date_resolved.value is not None else None
        key = (title, due)
        if key in seen:
            issues.append(f"Duplicate assessment: '{title}' due {due}")
        seen.add(key)
    return issues


def validate_assessment_completeness(extraction: SyllabusExtraction) -> list[str]:
    """Check that every assessment has a title and type."""
    issues: list[str] = []
    for i, a in enumerate(extraction.assessments):
        if a.title.value is None:
            issues.append(f"Assessment #{i + 1} is missing a title")
        if a.type.value is None:
            issues.append(f"Assessment #{i + 1} is missing a type")
    return issues


def _patch_extracted_fields(obj):
    """Ensure all ExtractedField-shaped dicts have the required 'value' key.

    Gemini sometimes omits 'value' when it should be null. This walks the raw
    dict and adds value=None where missing.
    """
    if isinstance(obj, dict):
        # Detect ExtractedField-shaped dicts (has 'confidence' but no 'value')
        if "confidence" in obj and "value" not in obj:
            obj["value"] = None
        for v in obj.values():
            _patch_extracted_fields(v)
    elif isinstance(obj, list):
        for item in obj:
            _patch_extracted_fields(item)


def post_process_extraction(
    raw_result: dict,
    semester_context: dict,
) -> SyllabusExtraction:
    """Parse raw agent output into SyllabusExtraction with deterministic cleanup.

    This runs BEFORE date resolution.  It only patches structural issues from
    Gemini output (missing keys, weight validation).  Confidence scoring and
    date boundary validation happen AFTER date resolution in
    ``finalize_extraction`` so they use the final resolved values.

    Args:
        raw_result: The raw dict from the agent's validated_syllabus output.
        semester_context: Dict with 'semester_start' and 'semester_end' as YYYY-MM-DD strings.

    Returns:
        A cleaned SyllabusExtraction ready for date resolution.
    """
    _patch_extracted_fields(raw_result)
    extraction = SyllabusExtraction(**raw_result)

    # Re-validate grade weights (don't trust the LLM's math)
    weight_issues = validate_grade_weights(extraction)

    # Merge weight issues into missing_sections
    existing_missing = list(extraction.missing_sections)
    for issue in weight_issues:
        if issue not in existing_missing:
            existing_missing.append(issue)
    extraction.missing_sections = existing_missing

    return extraction


def finalize_extraction(
    extraction: SyllabusExtraction,
    semester_context: dict,
) -> SyllabusExtraction:
    """Run AFTER date resolution to compute final confidence and flag issues.

    This is the single place where extraction_confidence is computed and
    low-confidence / date-boundary issues are flagged.  It uses the final
    resolved date values and their confidence scores.
    """
    semester_start = _parse_date(semester_context.get("semester_start"))
    semester_end = _parse_date(semester_context.get("semester_end"))

    # Compute extraction_confidence from all field confidences (including resolved dates)
    confidences = _collect_confidences(extraction)
    if confidences:
        extraction.extraction_confidence = round(sum(confidences) / len(confidences), 4)

    # Validate date boundaries against semester (now using resolver output)
    date_issues: list[str] = []
    if semester_start and semester_end:
        date_issues = validate_date_boundaries(extraction, semester_start, semester_end)

    # Flag low-confidence fields (< 0.7) for user review
    low_confidence_fields: list[str] = []
    for attr in (
        "course_name", "course_code", "instructor_name",
        "instructor_email", "office_hours",
    ):
        field = getattr(extraction, attr, None)
        if field is not None and isinstance(field, ExtractedField) and field.confidence < 0.7:
            low_confidence_fields.append(f"low_confidence:{attr}")

    for i, a in enumerate(extraction.assessments):
        for attr in ("title", "type", "due_date_raw", "due_date_resolved", "weight_percent"):
            field = getattr(a, attr)
            if isinstance(field, ExtractedField) and field.confidence < 0.7:
                title_str = a.title.value or f"assessment_{i + 1}"
                low_confidence_fields.append(f"low_confidence:{title_str}.{attr}")

    # Merge into missing_sections
    existing_missing = list(extraction.missing_sections)
    all_issues = date_issues + low_confidence_fields
    for issue in all_issues:
        if issue not in existing_missing:
            existing_missing.append(issue)
    extraction.missing_sections = existing_missing

    return extraction
