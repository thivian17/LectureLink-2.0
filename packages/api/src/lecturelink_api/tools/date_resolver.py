"""Three-layer date resolution for syllabus processing.

Resolves ambiguous academic dates like "Week 3 Tuesday" or "the Monday after
spring break" into specific calendar dates using three layers:

  Layer 1 — LLM-resolved validation
  Layer 2 — Relative week pattern matching
  Layer 3 — dateparser fallback
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta

import dateparser

from lecturelink_api.models.syllabus_models import AssessmentExtraction, ExtractedField

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DAY_MAP: dict[str, int] = {
    "monday": 0,
    "tuesday": 1,
    "wednesday": 2,
    "thursday": 3,
    "friday": 4,
    "saturday": 5,
    "sunday": 6,
}

_DAY_ABBREV: dict[str, str] = {
    "mon": "monday",
    "tue": "tuesday",
    "tues": "tuesday",
    "wed": "wednesday",
    "thu": "thursday",
    "thurs": "thursday",
    "fri": "friday",
    "sat": "saturday",
    "sun": "sunday",
}

# Build regex alternation from all known day names + abbreviations
_DAY_NAMES = "|".join(list(DAY_MAP.keys()) + list(_DAY_ABBREV.keys()))

_WEEK_DAY_RE = re.compile(
    rf"(?:week|wk)\s*(\d+)\s+({_DAY_NAMES})\b",
    re.IGNORECASE,
)

_WEEK_ONLY_RE = re.compile(
    r"(?:week|wk)\s*(\d+)\b",
    re.IGNORECASE,
)

_END_OF_WEEK_RE = re.compile(
    r"(?:due\s+)?end\s+of\s+week\s+(\d+)",
    re.IGNORECASE,
)

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

# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------


@dataclass
class SemesterContext:
    start: date
    end: date
    meeting_days: list[str]  # ['monday', 'wednesday']
    holidays: list[dict] = field(default_factory=list)  # [{'name': str, 'start': date, 'end': date}]


@dataclass
class ResolvedDate:
    value: date | None
    confidence: float
    method: str  # 'llm_validated', 'week_relative', 'dateparser', 'ambiguous'
    original_text: str


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _normalize_day(name: str) -> str:
    """Normalize a day name or abbreviation to its full lowercase form."""
    name = name.lower().strip()
    return _DAY_ABBREV.get(name, name)


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


def _next_valid_day(d: date, weekday: int, holidays: list[dict]) -> date:
    """If *d* is inside a holiday, advance to the next occurrence of *weekday*
    that is not in a holiday period."""
    if not _is_in_holiday(d, holidays):
        return d
    # Walk forward past the current holiday period
    candidate = d + timedelta(days=1)
    while _is_in_holiday(candidate, holidays):
        candidate += timedelta(days=1)
    # Advance to the target weekday
    while candidate.weekday() != weekday:
        candidate += timedelta(days=1)
    # Guard against landing in yet another holiday
    if _is_in_holiday(candidate, holidays):
        return _next_valid_day(candidate, weekday, holidays)
    return candidate


def _in_semester(d: date, semester: SemesterContext) -> bool:
    return semester.start <= d <= semester.end


# ---------------------------------------------------------------------------
# Layer 1 — LLM-resolved validation
# ---------------------------------------------------------------------------


def _try_llm_validated(
    llm_resolved: date | None,
    semester: SemesterContext,
    original_text: str,
) -> ResolvedDate | None:
    """If Gemini already resolved a date, validate it falls within semester."""
    if llm_resolved is None:
        return None
    if _in_semester(llm_resolved, semester):
        return ResolvedDate(
            value=llm_resolved,
            confidence=0.9,
            method="llm_validated",
            original_text=original_text,
        )
    return None


# ---------------------------------------------------------------------------
# Layer 2 — Relative week pattern matching
# ---------------------------------------------------------------------------


def _try_week_relative(
    raw_text: str,
    semester: SemesterContext,
) -> ResolvedDate | None:
    """Parse patterns like 'Week 3', 'Week 3 Tuesday', 'Wk 5 Thurs',
    'end of week 10' and calculate the calendar date."""
    text = raw_text.strip()

    # --- "end of week N" (most specific, check first) ---
    m = _END_OF_WEEK_RE.search(text)
    if m:
        week_num = int(m.group(1))
        week_start = semester.start + timedelta(weeks=week_num - 1)
        friday = week_start + timedelta(days=DAY_MAP["friday"])
        friday = _next_valid_day(friday, DAY_MAP["friday"], semester.holidays)
        if _in_semester(friday, semester):
            return ResolvedDate(
                value=friday,
                confidence=0.85,
                method="week_relative",
                original_text=raw_text,
            )

    # --- "Week N DayName" ---
    m = _WEEK_DAY_RE.search(text)
    if m:
        week_num = int(m.group(1))
        day_name = _normalize_day(m.group(2))
        day_offset = DAY_MAP.get(day_name)
        if day_offset is not None:
            week_start = semester.start + timedelta(weeks=week_num - 1)
            target = week_start + timedelta(days=day_offset)
            target = _next_valid_day(target, day_offset, semester.holidays)
            if _in_semester(target, semester):
                return ResolvedDate(
                    value=target,
                    confidence=0.85,
                    method="week_relative",
                    original_text=raw_text,
                )

    # --- "Week N" (no day — return the Monday of that week) ---
    m = _WEEK_ONLY_RE.search(text)
    if m:
        week_num = int(m.group(1))
        week_start = semester.start + timedelta(weeks=week_num - 1)
        week_start = _next_valid_day(
            week_start, week_start.weekday(), semester.holidays
        )
        if _in_semester(week_start, semester):
            return ResolvedDate(
                value=week_start,
                confidence=0.85,
                method="week_relative",
                original_text=raw_text,
            )

    return None


# ---------------------------------------------------------------------------
# Layer 3 — dateparser fallback
# ---------------------------------------------------------------------------


def _try_dateparser(
    raw_text: str,
    semester: SemesterContext,
) -> ResolvedDate | None:
    """Use the *dateparser* library with semester-aware settings."""
    base_dt = datetime(
        semester.start.year, semester.start.month, semester.start.day
    )
    parsed = dateparser.parse(
        raw_text,
        settings={
            "PREFER_DATES_FROM": "future",
            "RELATIVE_BASE": base_dt,
        },
    )
    if parsed is not None:
        return ResolvedDate(
            value=parsed.date(),
            confidence=0.7,
            method="dateparser",
            original_text=raw_text,
        )
    return None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def resolve_date(
    raw_text: str,
    semester: SemesterContext,
    llm_resolved: date | None = None,
) -> ResolvedDate:
    """Resolve a single raw date string into a calendar date.

    Tries three layers in order:
      1. LLM-resolved validation (confidence 0.9)
      2. Relative week pattern matching (confidence 0.85)
      3. dateparser fallback (confidence 0.7)

    Returns *ResolvedDate* with value=None and method='ambiguous' when all
    layers fail.
    """
    # Fast-exit for empty / whitespace-only text
    if not raw_text or not raw_text.strip():
        return ResolvedDate(
            value=None, confidence=0.0, method="ambiguous", original_text=raw_text
        )

    # Known ambiguous phrases
    if raw_text.strip().lower() in _AMBIGUOUS_PHRASES:
        return ResolvedDate(
            value=None, confidence=0.0, method="ambiguous", original_text=raw_text
        )

    # Layer 1
    result = _try_llm_validated(llm_resolved, semester, raw_text)
    if result is not None:
        return result

    # Layer 2
    result = _try_week_relative(raw_text, semester)
    if result is not None:
        return result

    # Layer 3
    result = _try_dateparser(raw_text, semester)
    if result is not None:
        return result

    # All layers failed
    return ResolvedDate(
        value=None, confidence=0.0, method="ambiguous", original_text=raw_text
    )


def resolve_all_dates(
    assessments: list[AssessmentExtraction],
    semester: SemesterContext,
) -> list[AssessmentExtraction]:
    """Run *resolve_date* on every assessment, returning updated copies.

    For each assessment the function:
      - Reads ``due_date_raw.value`` as the raw text
      - Parses ``due_date_resolved.value`` (if present) as the LLM-resolved date
      - Calls *resolve_date* and writes the result back into ``due_date_resolved``
    """
    results: list[AssessmentExtraction] = []
    for a in assessments:
        raw_text = str(a.due_date_raw.value) if a.due_date_raw.value is not None else ""

        # Parse LLM-resolved date from the existing field (may be a YYYY-MM-DD string)
        llm_resolved: date | None = None
        if a.due_date_resolved.value:
            try:
                llm_resolved = date.fromisoformat(str(a.due_date_resolved.value))
            except (ValueError, TypeError):
                pass

        resolved = resolve_date(raw_text, semester, llm_resolved)

        new_resolved = ExtractedField(
            value=resolved.value.isoformat() if resolved.value else None,
            confidence=resolved.confidence,
            source_text=a.due_date_resolved.source_text,
        )

        updated = a.model_copy(update={"due_date_resolved": new_resolved})
        results.append(updated)

    return results
