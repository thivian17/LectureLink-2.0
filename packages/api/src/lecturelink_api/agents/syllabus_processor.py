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
import re
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
- topics: All topics covered that week. Include module names if the course uses modules \
  (e.g. "Module 1: AI Strategy").
- readings: Assigned readings for the week. Include case studies, textbook chapters, \
  and research papers.
- due_items: Items due during the week (assignments, quizzes, exams, etc.). Include \
  the item title and any details like "submit by end of class".

IMPORTANT:
- If the schedule table has merged or duplicated columns, focus on extracting unique \
  content only (ignore repeated column values).
- If a week says "READING WEEK" or "NO CLASS" or "BREAK", still include it with \
  week_number but set topics to ["No class - Reading Week"] or similar.
- If week numbering skips (e.g., WK 1, WK 2, ... WK 6, WK 8 — no WK 7), do NOT \
  invent the missing week. Only extract weeks explicitly listed.
- Some syllabi use "WK" abbreviation instead of "Week" — treat identically.

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
- title: Assessment name (e.g. "Midterm 1", "HW 3", "Group Project #2").
- type: One of: exam, quiz, homework, project, lab, paper, presentation, participation, other.
- due_date_raw: The original date text as written in the syllabus. Follow these rules:
  * For assessments that are ongoing throughout the semester (e.g. class participation, \
    attendance, weekly reflections), set this to "Ongoing".
  * For assessments with a specific date, copy the exact text (e.g. "Feb 11, 2026", \
    "Week 6", "WK 10").
  * For assessments with multiple dates (e.g. "WK 6, 8, 9, 10, 11"), use the LAST \
    date as the due date (e.g. "WK 11") since that represents the final deadline.
- due_date_resolved: Resolved calendar date in YYYY-MM-DD format, or null if \
  ambiguous, ongoing, or if you cannot determine the exact date.
- weight_percent: Grade weight as a percentage.
- topics: Related topics or chapters.

IMPORTANT RULES:
1. Express all weights as percentages (25.0 for 25%, not 0.25). If the syllabus uses \
   point values, convert to percentages.
2. If a grade component has multiple sub-items (e.g. "Group Projects" = 45% total, with \
   "Project #1" = 15% and "Project #2" = 30%), extract BOTH the component AND the \
   individual assessments separately.
3. For peer evaluations, set type to "other".
4. For Data Camp modules, practice labs, or similar online exercises, set type to "homework".
5. Grade breakdown weights should sum to approximately 100%. If they don't, flag \
   low confidence on the weight_percent fields.
6. When a syllabus lists a QUANTITY of assessments (e.g. "4 Tableau Quizzes × 4% = 16%", \
   "6 Group Discussions × 1.5% = 9%"), create INDIVIDUAL assessment entries for each one. \
   Example: "4 Tableau Quizzes × 4% = 16%" → create 4 assessments: \
   "Tableau Quiz 1" (4%), "Tableau Quiz 2" (4%), "Tableau Quiz 3" (4%), "Tableau Quiz 4" (4%).
7. For each individual assessment instance, search the ENTIRE document (including schedule \
   tables, weekly overviews) to find its specific due date. Schedules often list \
   "Tableau Quiz 1" under a specific class or week.
8. If due dates are listed as "Class N", "Session N", or "Week N", preserve that EXACT text \
   as the due_date_raw. Do NOT attempt to resolve it to a calendar date.
9. RECURRING ASSESSMENT DUE DATES: For recurring assessments like discussion posts that \
   have a SPECIFIC submission deadline different from the class meeting day, use that \
   deadline as the due_date_raw. Example: If discussions open after Wednesday class but \
   are due "Monday at 11:59pm", set due_date_raw to the specific Monday date or \
   "Monday after Class N". Look for phrases like "due by", "must be posted by", \
   "no later than", "deadline" to find the actual submission date, which may differ \
   from the class meeting date.

Set confidence and source_text on every ExtractedField.

Syllabus text:
{raw_text}"""

_INFO_INSTRUCTION = """\
You are an expert course information extractor. Analyze the syllabus text below and \
extract course metadata and policies.

Extract:
- course_name: Full official course name (e.g. "Business Applications of AI II", \
"Introduction to Computer Science"). This is the formal course title, NOT a description \
of the course topic. Look for it near the top of the document, often on a cover page, \
in a header, or next to the course code.
- course_code: Course code exactly as written. Examples of real formats: \
"CS 101", "MMAI 5090 3.00", "SB/MBAN 5140", "EECS 4404", "OMIS 6750 3.00", \
"MGMT 6100". Include credit hours if shown (e.g. "3.00"). \
The code is usually 2-5 uppercase letters followed by 3-5 digits.
- instructor_name: Primary instructor's full name (not TAs or assistants).
- instructor_email: Instructor's email address.
- office_hours: Office hours schedule as written. Include location if specified.
- policies: A JSON object of course policies keyed by category. Use these keys where \
applicable: late_policy, attendance, academic_integrity, grading_scale, extra_credit, \
technology_policy, accommodation.

IMPORTANT:
- The course name and code may appear in document headers, footers, or at the very \
beginning of the text (before any headings). Do not skip this content.
- If the document begins with what looks like a cover page (course code + title on \
separate lines), use that as the authoritative source for course_name and course_code.
- If "Course Outline" or "Syllabus" appears as a heading, the course name is NOT \
"Course Outline" — look for the actual course title nearby.
- Do not confuse a course description paragraph with the course name. The name is \
typically short (3-10 words), not a full sentence.

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


def _normalize_assessment_types(extraction: SyllabusExtraction) -> None:
    """Normalize assessment types to lowercase and map common variants."""
    _type_map = {
        "exam": "exam", "quiz": "quiz", "homework": "homework",
        "project": "project", "lab": "lab", "paper": "paper",
        "presentation": "presentation", "participation": "participation",
        "other": "other",
        "midterm": "exam", "final": "exam", "final exam": "exam",
        "midterm exam": "exam", "test": "exam",
        "assignment": "homework", "problem set": "homework",
        "essay": "paper", "report": "paper",
        "peer evaluation": "other", "peer review": "other",
        "discussion": "participation", "attendance": "participation",
        "reflection": "homework", "case study": "homework",
        "data camp": "homework",
    }
    for assessment in extraction.assessments:
        if assessment.type.value:
            raw_type = str(assessment.type.value).strip().lower()
            assessment.type.value = _type_map.get(raw_type, "other")


def _fill_missing_fields(extraction: SyllabusExtraction) -> None:
    """Fill missing required fields with sensible defaults."""
    for i, assessment in enumerate(extraction.assessments):
        if not assessment.title.value or not str(assessment.title.value).strip():
            assessment.title.value = f"Assessment {i + 1}"
            assessment.title.confidence = 0.1

        if not assessment.type.value or not str(assessment.type.value).strip():
            assessment.type.value = "other"
            assessment.type.confidence = 0.1

        if assessment.weight_percent.value is not None:
            try:
                assessment.weight_percent.value = float(
                    assessment.weight_percent.value,
                )
            except (ValueError, TypeError):
                assessment.weight_percent.value = None
                assessment.weight_percent.confidence = 0.0


def _reconcile_assessment_weights(extraction: SyllabusExtraction) -> None:
    """Infer missing assessment weights from grade breakdown when possible."""
    component_weights: dict[str, float] = {}
    for comp in extraction.grade_breakdown:
        name = str(comp.name.value or "").strip().lower()
        weight = comp.weight_percent.value
        if name and weight is not None:
            component_weights[name] = float(weight)

    for assessment in extraction.assessments:
        if (
            assessment.weight_percent.value is None
            or assessment.weight_percent.value == 0
        ):
            title = str(assessment.title.value or "").strip().lower()
            atype = str(assessment.type.value or "").strip().lower()

            for comp_name, comp_weight in component_weights.items():
                if (
                    comp_name in title
                    or title in comp_name
                    or atype in comp_name
                    or comp_name in atype
                ):
                    matching = [
                        a
                        for a in extraction.assessments
                        if comp_name in str(a.title.value or "").lower()
                        or str(a.title.value or "").lower() in comp_name
                    ]
                    if len(matching) == 1:
                        assessment.weight_percent.value = comp_weight
                        assessment.weight_percent.confidence = 0.6
                    break


def _singularize(word: str) -> str:
    """Rough English singularization for matching plural assessment names."""
    w = word.lower().strip()
    if w.endswith("zes"):  # quizzes → quiz
        return w[:-3]
    if w.endswith("ies"):  # activities → activit
        return w[:-3] + "y"
    if w.endswith("sses"):  # classes → class
        return w[:-2]
    if w.endswith("ses"):  # analyses → analys
        return w[:-2]
    if w.endswith("es"):  # exercises → exercis
        return w[:-2]
    if w.endswith("s") and not w.endswith("ss"):  # projects → project
        return w[:-1]
    return w


def _split_bulk_assessments(
    extraction: SyllabusExtraction,
    schedule: list[dict],
) -> None:
    """Split bulk assessments into individual instances using schedule due dates.

    Detects patterns like:
    - Assessment list has "Tableau Quizzes" at 16%
    - Schedule data has "Tableau Quiz 1" in week 3, "Tableau Quiz 2" in week 5, etc.

    Splits into individual assessments with per-instance weights and due dates.

    IMPORTANT: If Gemini already split the assessments (individual numbered
    entries already exist), this function skips the split to avoid duplication
    and removes the bulk parent entry instead.
    """
    # Build map: normalized title → "Class N" from schedule due_items
    schedule_due_map: dict[str, str] = {}
    for week in schedule:
        week_num = week.get("week_number")
        for item in week.get("due_items") or []:
            item_str = str(item).strip() if item else ""
            if item_str:
                schedule_due_map[item_str.lower()] = f"Class {week_num}" if week_num else ""

    if not schedule_due_map:
        return

    # Build set of existing assessment titles for already-split detection
    existing_titles = {
        str(a.title.value or "").strip().lower()
        for a in extraction.assessments
    }

    indices_to_remove: list[int] = []
    new_assessments: list[AssessmentExtraction] = []

    for i, assessment in enumerate(extraction.assessments):
        title = str(assessment.title.value or "").strip()
        weight = assessment.weight_percent.value
        if not title or weight is None or weight == 0:
            continue

        # Find numbered instances in schedule that match this assessment's base name
        title_singular = _singularize(title)

        matching_instances: list[dict] = []
        for due_key, due_value in schedule_due_map.items():
            # Strip the trailing number to get the base: "tableau quiz 1" → "tableau quiz"
            due_base = re.sub(r"\s*#?\d+\s*$", "", due_key).strip()
            due_singular = _singularize(due_base)

            if not title_singular or not due_singular:
                continue

            # Check if bases match (either direction substring)
            if title_singular in due_singular or due_singular in title_singular:
                num_match = re.search(r"(\d+)\s*$", due_key)
                if num_match:
                    matching_instances.append({
                        "number": int(num_match.group(1)),
                        "due_raw": due_value,
                        "original_key": due_key,
                    })

        if len(matching_instances) < 2:
            continue

        matching_instances.sort(key=lambda x: x["number"])

        # Check if Gemini already created the individual entries
        already_split = any(
            inst["original_key"] in existing_titles
            for inst in matching_instances
        )

        if already_split:
            # Individual entries already exist — don't re-split.
            # If this is the bulk parent (no trailing number), remove it.
            if not re.search(r"\d+\s*$", title):
                indices_to_remove.append(i)
            continue

        # Not already split — create individual assessments
        per_weight = round(float(weight) / len(matching_instances), 2)

        for inst in matching_instances:
            inst_title = inst["original_key"].title()
            new_assessments.append(AssessmentExtraction(
                title=ExtractedField(
                    value=inst_title, confidence=0.8, source_text=inst["original_key"],
                ),
                type=ExtractedField(
                    value=assessment.type.value, confidence=assessment.type.confidence,
                ),
                due_date_raw=ExtractedField(
                    value=inst["due_raw"], confidence=0.7, source_text=inst["original_key"],
                ),
                due_date_resolved=ExtractedField(value=None, confidence=0.0),
                weight_percent=ExtractedField(value=per_weight, confidence=0.7),
                topics=list(assessment.topics),
            ))

        indices_to_remove.append(i)

    if indices_to_remove or new_assessments:
        extraction.assessments = [
            a for idx, a in enumerate(extraction.assessments)
            if idx not in indices_to_remove
        ] + new_assessments


def _dedup_assessments(extraction: SyllabusExtraction) -> None:
    """Remove duplicate assessments with the same title and due date.

    Keeps the first occurrence (or higher-confidence one if tied).
    Handles the case where Gemini AND the post-processor both created
    the same individual assessment.
    """
    seen: dict[tuple[str, str], int] = {}  # (title, due_date) → index
    to_keep: list[int] = []

    for i, a in enumerate(extraction.assessments):
        title = str(a.title.value or "").strip().lower()
        due = str(a.due_date_raw.value or "").strip().lower()
        key = (title, due)

        if key not in seen:
            seen[key] = i
            to_keep.append(i)
        else:
            # Keep the one with higher confidence
            existing_idx = seen[key]
            existing = extraction.assessments[existing_idx]
            existing_conf = existing.title.confidence or 0
            new_conf = a.title.confidence or 0

            if new_conf > existing_conf:
                to_keep.remove(existing_idx)
                to_keep.append(i)
                seen[key] = i

    if len(to_keep) < len(extraction.assessments):
        extraction.assessments = [extraction.assessments[i] for i in sorted(to_keep)]


def _fix_split_assessment_weights(extraction: SyllabusExtraction) -> None:
    """Correct weights for assessments that Gemini split but assigned total weight to each.

    Detects groups of assessments with the same base name and numbered suffixes
    where each has the total group weight instead of per-instance weight.

    Example: 6 × "Group Discussion N" each at 9% → should be 1.5% each.
    Cross-references grade_breakdown to detect the error.
    """
    # Build component weight map from grade breakdown
    component_weights: dict[str, float] = {}
    for comp in extraction.grade_breakdown:
        name = str(comp.name.value or "").strip().lower()
        weight = comp.weight_percent.value
        if name and weight is not None:
            component_weights[name] = float(weight)

    if not component_weights:
        return

    # Group assessments by base name (strip trailing numbers)
    groups: dict[str, list[int]] = {}
    for i, a in enumerate(extraction.assessments):
        title = str(a.title.value or "").strip()
        base = re.sub(r"\s*#?\d+\s*$", "", title).strip().lower()
        if base:
            groups.setdefault(base, []).append(i)

    # For each group with 2+ members, check if weights match a component total
    for base, indices in groups.items():
        if len(indices) < 2:
            continue

        # Find matching grade breakdown component
        matching_comp_weight = None
        base_singular = _singularize(base)
        for comp_name, comp_weight in component_weights.items():
            comp_singular = _singularize(comp_name)
            if base_singular in comp_singular or comp_singular in base_singular:
                matching_comp_weight = comp_weight
                break

        if matching_comp_weight is None:
            continue

        # Check if ALL instances have the SAME weight AND that weight matches
        # the component total.  This detects: Gemini assigned the total group
        # weight to each individual.
        # Skip if weights differ — they're already individually weighted
        # (e.g., Project 1=10%, Project 2=28%, Project 3=32%).
        instance_weights = [
            float(extraction.assessments[idx].weight_percent.value)
            for idx in indices
            if extraction.assessments[idx].weight_percent.value is not None
        ]

        if not instance_weights:
            continue

        # All weights must be the same to indicate a "total assigned to each" error
        if len(set(instance_weights)) != 1:
            continue  # Different weights = individually weighted, don't touch

        common_weight = instance_weights[0]

        # The common weight should match the component total (within tolerance)
        if abs(common_weight - matching_comp_weight) > 0.5:
            continue

        # Fix: divide total by count
        per_instance_weight = round(matching_comp_weight / len(indices), 2)

        for idx in indices:
            a = extraction.assessments[idx]
            a.weight_percent.value = per_instance_weight
            a.weight_percent.confidence = min(a.weight_percent.confidence, 0.7)


def validate_no_near_duplicates(extraction: SyllabusExtraction) -> list[str]:
    """Check for near-duplicate assessments (similar titles, same date)."""
    issues: list[str] = []
    for i, a in enumerate(extraction.assessments):
        for j, b in enumerate(extraction.assessments):
            if j <= i:
                continue
            title_a = str(a.title.value or "").strip().lower()
            title_b = str(b.title.value or "").strip().lower()
            date_a = str(a.due_date_resolved.value or "")
            date_b = str(b.due_date_resolved.value or "")

            if (
                date_a
                and date_a == date_b
                and (title_a in title_b or title_b in title_a)
                and title_a != title_b
            ):
                issues.append(
                    f"Possible duplicate: '{a.title.value}' and "
                    f"'{b.title.value}' on {date_a}"
                )
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

    # Normalize and fill before validation
    _normalize_assessment_types(extraction)
    _fill_missing_fields(extraction)
    _reconcile_assessment_weights(extraction)
    _fix_split_assessment_weights(extraction)

    # Split bulk assessments (e.g. "4 Quizzes at 4% each") into individuals
    schedule = raw_result.get("weekly_schedule", [])
    _split_bulk_assessments(extraction, schedule)
    _dedup_assessments(extraction)

    # Re-validate grade weights (don't trust the LLM's math)
    weight_issues = validate_grade_weights(extraction)

    # Check for duplicates
    duplicate_issues = validate_no_duplicates(extraction)
    near_dup_issues = validate_no_near_duplicates(extraction)

    # Merge all issues into missing_sections
    existing_missing = list(extraction.missing_sections)
    for issue in weight_issues + duplicate_issues + near_dup_issues:
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
