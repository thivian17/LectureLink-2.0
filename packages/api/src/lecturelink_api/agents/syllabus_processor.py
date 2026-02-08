"""Multi-agent syllabus extraction pipeline using Google ADK.

Pipeline stages:
  1. IngestionAgent     – extracts raw text from the uploaded document
  2. ParallelExtraction – three agents run concurrently to extract
     schedule, grading, and course-info data
  3. ValidationLoop     – LoopAgent that merges parallel outputs,
     validates, and iterates up to 3 times to fix issues
"""

from __future__ import annotations

from datetime import date, datetime

from google.adk.agents import LlmAgent, LoopAgent, ParallelAgent, SequentialAgent
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
- due_date_raw: The original date text as written in the syllabus.
- due_date_resolved: Resolved calendar date in YYYY-MM-DD format, or null if ambiguous.
- weight_percent: Grade weight as a percentage.
- topics: Related topics or chapters.

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
    generate_content_config=types.GenerateContentConfig(
        temperature=0.1,
    ),
)

parallel_extraction = ParallelAgent(
    name="ParallelExtraction",
    sub_agents=[schedule_extractor, grading_extractor, info_extractor],
)


# ---------------------------------------------------------------------------
# Stage 3 — Validation via LoopAgent
# ---------------------------------------------------------------------------

_VALIDATOR_INSTRUCTION = """\
You are a syllabus extraction validator. Your job is to merge extraction outputs \
and validate the result.

Schedule data:
{schedule_data}

Grading data:
{grading_data}

Course info:
{info_data}

Previous validation errors (if any — empty on first run):
{validation_errors}

Semester boundaries:
- semester_start: {semester_start}
- semester_end: {semester_end}

MERGE all data into a single SyllabusExtraction JSON object, then VALIDATE:

1. **Grade weights**: The sum of all grade_breakdown weight_percent values must be \
between 98% and 102% (inclusive). If not, adjust weights proportionally or flag the issue.

2. **Date boundaries**: Every assessment due_date_resolved (when not null) must fall \
between {semester_start} and {semester_end}. Flag any dates outside this range.

3. **No duplicate assessments**: No two assessments should have the same title AND \
the same due_date_resolved. Remove exact duplicates.

4. **Assessment completeness**: Every assessment must have a non-null title and type. \
Set missing types to "other".

5. **extraction_confidence**: Compute as the average of all ExtractedField confidence \
values across the entire extraction.

6. **missing_sections**: List any expected sections not found. Expected sections: \
course_name, course_code, instructor_name, instructor_email, office_hours, \
grade_breakdown, assessments, weekly_schedule, policies.

If ALL validations pass, output the final SyllabusExtraction JSON with \
validation_passed set to true in the output.

If ANY validation fails, output the SyllabusExtraction JSON with your best-effort \
fixes applied. The LoopAgent will re-run if issues remain.

Output ONLY valid JSON matching the SyllabusExtraction schema."""

validator = LlmAgent(
    name="Validator",
    model="gemini-2.5-flash",
    instruction=_VALIDATOR_INSTRUCTION,
    output_key="validated_syllabus",
    output_schema=SyllabusExtraction,
    generate_content_config=types.GenerateContentConfig(
        temperature=0.1,
    ),
)

validation_loop = LoopAgent(
    name="ValidationLoop",
    sub_agents=[validator],
    max_iterations=3,
)


# ---------------------------------------------------------------------------
# Full Pipeline
# ---------------------------------------------------------------------------

# Text extraction is handled externally by the service layer (deterministic,
# no LLM needed). The pipeline expects raw_text pre-populated in session state.
extraction_pipeline = SequentialAgent(
    name="ExtractionPipeline",
    sub_agents=[parallel_extraction, validation_loop],
)


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
    """Parse raw agent output into SyllabusExtraction with deterministic re-validation.

    Args:
        raw_result: The raw dict from the agent's validated_syllabus output.
        semester_context: Dict with 'semester_start' and 'semester_end' as YYYY-MM-DD strings.

    Returns:
        A cleaned SyllabusExtraction with recomputed confidence and needs_review flags.
    """
    _patch_extracted_fields(raw_result)
    extraction = SyllabusExtraction(**raw_result)

    semester_start = _parse_date(semester_context.get("semester_start"))
    semester_end = _parse_date(semester_context.get("semester_end"))

    # Recompute extraction_confidence from actual field confidences
    confidences = _collect_confidences(extraction)
    if confidences:
        extraction.extraction_confidence = round(sum(confidences) / len(confidences), 4)

    # Re-validate grade weights (don't trust the LLM's math)
    weight_issues = validate_grade_weights(extraction)

    # Re-validate date boundaries
    date_issues: list[str] = []
    if semester_start and semester_end:
        date_issues = validate_date_boundaries(extraction, semester_start, semester_end)

    # Set needs_review=True for any field with confidence < 0.7
    # We track this via missing_sections as a pragmatic approach since the
    # SyllabusExtraction model doesn't have per-field needs_review flags
    low_confidence_fields: list[str] = []
    for attr in (
        "course_name", "course_code", "instructor_name",
        "instructor_email", "office_hours",
    ):
        field = getattr(extraction, attr, None)
        if field is not None and isinstance(field, ExtractedField):
            if field.confidence < 0.7:
                low_confidence_fields.append(f"low_confidence:{attr}")

    for i, a in enumerate(extraction.assessments):
        for attr in ("title", "type", "due_date_raw", "due_date_resolved", "weight_percent"):
            field = getattr(a, attr)
            if isinstance(field, ExtractedField) and field.confidence < 0.7:
                title_str = a.title.value or f"assessment_{i + 1}"
                low_confidence_fields.append(f"low_confidence:{title_str}.{attr}")

    # Merge any issues into missing_sections for review
    existing_missing = list(extraction.missing_sections)
    all_issues = weight_issues + date_issues + low_confidence_fields
    for issue in all_issues:
        if issue not in existing_missing:
            existing_missing.append(issue)
    extraction.missing_sections = existing_missing

    return extraction
