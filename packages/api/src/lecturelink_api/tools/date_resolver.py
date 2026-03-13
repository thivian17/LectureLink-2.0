"""LLM date validation for syllabus processing.

The LLM extraction agent (with full semester + holiday context) is the primary
date resolver.  This module validates those dates and flags low-confidence or
invalid ones for user confirmation.
"""

from __future__ import annotations

import contextlib
from dataclasses import dataclass, field
from datetime import date

from lecturelink_api.models.syllabus_models import AssessmentExtraction, ExtractedField

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_AMBIGUOUS_PHRASES: set[str] = {
    "tba",
    "tbd",
    "to be announced",
    "to be determined",
    "see course website",
    "see canvas",
    "see blackboard",
    "end of semester",
    "last day of class",
}

# Phrases that indicate an ongoing/recurring assessment with no single due date.
# Shared with extraction_to_db_assessments() via import.
ONGOING_PHRASES: set[str] = {
    "ongoing",
    "throughout semester",
    "throughout the semester",
    "continuous",
    "weekly",
    "every class",
    "every week",
    "all semester",
}

# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------


@dataclass
class SemesterContext:
    start: date
    end: date
    meeting_days: list[str]  # ['monday', 'wednesday']
    # [{'name': str, 'start': date, 'end': date}]
    holidays: list[dict] = field(default_factory=list)


@dataclass
class ResolvedDate:
    value: date | None
    confidence: float
    method: str  # 'llm_validated', 'ambiguous'
    original_text: str


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _parse_holiday_date(d: date | str) -> date:
    """Accept either a date object or an ISO-format string."""
    if isinstance(d, date):
        return d
    return date.fromisoformat(str(d))


def _is_in_holiday(d: date, holidays: list[dict]) -> bool:
    """Check if a date falls within any holiday period."""
    for h in holidays:
        h_start = _parse_holiday_date(h["start"])
        h_end = _parse_holiday_date(h["end"])
        if h_start <= d <= h_end:
            return True
    return False


def _in_semester(d: date, semester: SemesterContext) -> bool:
    return semester.start <= d <= semester.end


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def resolve_date(
    raw_text: str,
    semester: SemesterContext,
    llm_resolved: date | None = None,
    llm_confidence: float = 0.0,
) -> ResolvedDate:
    """Validate an LLM-resolved date against semester boundaries and holidays.

    The LLM (with full semester + holiday context in its prompt) is the primary
    resolver.  This function validates the result:

      - If the raw text is empty, ambiguous, or ongoing → ambiguous
      - If the LLM resolved a valid date (in semester, not on holiday) → keep it
        with the LLM's own confidence
      - Otherwise → ambiguous (user confirmation needed)

    Returns *ResolvedDate* with value=None and method='ambiguous' when
    validation fails.
    """
    # Fast-exit for empty / whitespace-only text
    if not raw_text or not raw_text.strip():
        return ResolvedDate(
            value=None, confidence=0.0, method="ambiguous", original_text=raw_text or ""
        )

    # Known ambiguous / ongoing phrases
    normalized = raw_text.strip().lower()
    if normalized in _AMBIGUOUS_PHRASES or normalized in ONGOING_PHRASES:
        return ResolvedDate(
            value=None, confidence=0.0, method="ambiguous", original_text=raw_text
        )

    # Validate the LLM-resolved date
    if llm_resolved is not None:
        if _in_semester(llm_resolved, semester) and not _is_in_holiday(
            llm_resolved, semester.holidays
        ):
            return ResolvedDate(
                value=llm_resolved,
                confidence=llm_confidence if llm_confidence > 0 else 0.9,
                method="llm_validated",
                original_text=raw_text,
            )

    # LLM date invalid or missing — mark ambiguous
    return ResolvedDate(
        value=None, confidence=0.0, method="ambiguous", original_text=raw_text
    )


def resolve_all_dates(
    assessments: list[AssessmentExtraction],
    semester: SemesterContext,
) -> list[AssessmentExtraction]:
    """Validate LLM-resolved dates for every assessment, returning updated copies.

    For each assessment the function:
      - Reads ``due_date_raw.value`` as the raw text
      - Parses ``due_date_resolved.value`` (if present) as the LLM-resolved date
      - Calls *resolve_date* to validate and writes the result back
    """
    results: list[AssessmentExtraction] = []
    for a in assessments:
        raw_text = str(a.due_date_raw.value) if a.due_date_raw.value is not None else ""

        # Parse LLM-resolved date from the existing field (may be a YYYY-MM-DD string)
        llm_resolved: date | None = None
        if a.due_date_resolved.value:
            with contextlib.suppress(ValueError, TypeError):
                llm_resolved = date.fromisoformat(str(a.due_date_resolved.value))

        resolved = resolve_date(
            raw_text,
            semester,
            llm_resolved,
            llm_confidence=a.due_date_resolved.confidence,
        )

        new_resolved = ExtractedField(
            value=resolved.value.isoformat() if resolved.value else None,
            confidence=resolved.confidence,
            source_text=a.due_date_resolved.source_text,
        )

        updated = a.model_copy(update={"due_date_resolved": new_resolved})
        results.append(updated)

    return results
