"""4-layer date resolution for syllabus processing.

Resolution cascade (first match wins):
  1. Fast-exit: empty/whitespace/ambiguous/ongoing → ambiguous
  2. Layer 1: LLM validation — validate llm_resolved against semester bounds + holidays
  3. Layer 2a: Week-relative — "Week 3", "Week 3 Tuesday", "End of Week 5"
  4. Layer 2b: Class-relative — "Class 4", "Lecture 10", "Wed in Class 3"
  5. Layer 3: Dateparser fallback — "January 15", "1/15/2026"
  6. Catch-all: ambiguous
"""

from __future__ import annotations

import contextlib
import re
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta

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

# Day name → Python weekday int (Monday=0 .. Sunday=6)
DAY_MAP: dict[str, int] = {
    "monday": 0, "mon": 0,
    "tuesday": 1, "tue": 1, "tues": 1,
    "wednesday": 2, "wed": 2, "wednes": 2,
    "thursday": 3, "thu": 3, "thur": 3, "thurs": 3,
    "friday": 4, "fri": 4,
    "saturday": 5, "sat": 5,
    "sunday": 6, "sun": 6,
}

_DAY_ABBREV: dict[str, str] = {
    "mon": "monday",
    "tue": "tuesday", "tues": "tuesday",
    "wed": "wednesday", "wednes": "wednesday",
    "thu": "thursday", "thur": "thursday", "thurs": "thursday",
    "fri": "friday",
    "sat": "saturday",
    "sun": "sunday",
}

# Regex building block for day names (used in compound patterns)
_DAY_NAMES = (
    r"(?:monday|tuesday|wednesday|thursday|friday|saturday|sunday"
    r"|mon|tue|tues|wed|wednes|thu|thur|thurs|fri|sat|sun)"
)

# ---------------------------------------------------------------------------
# Regex patterns
# ---------------------------------------------------------------------------

# Week patterns (order matters — more specific first)
_WEEK_DAY_RE = re.compile(
    r"week\s*(\d+)\s+(" + _DAY_NAMES + r")", re.I,
)
_END_WEEK_RE = re.compile(
    r"(?:due\s+)?end\s+of\s+week\s+(\d+)", re.I,
)
_WEEK_ONLY_RE = re.compile(r"(?:week|wk)\s*#?\s*(\d+)\b", re.I)

# Class patterns
_CLASS_KEYWORD = r"(?:class|lecture|session)"
_CLASS_DAY_RE = re.compile(
    rf"{_CLASS_KEYWORD}\s*(\d+)\s+({_DAY_NAMES})\b", re.I,
)
_DAY_IN_CLASS_RE = re.compile(
    rf"({_DAY_NAMES})\s+(?:in|of|during)\s+{_CLASS_KEYWORD}\s*(\d+)", re.I,
)
_CLASS_ONLY_RE = re.compile(
    rf"(?:^|\b){_CLASS_KEYWORD}\s*#?\s*(\d{{1,2}})\b", re.I,
)


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------


@dataclass
class SemesterContext:
    start: date
    end: date
    meeting_days: list[str]  # ['monday', 'wednesday']
    # [{'name': str, 'start': date|str, 'end': date|str}]
    holidays: list[dict] = field(default_factory=list)


@dataclass
class ResolvedDate:
    value: date | None
    confidence: float
    method: str  # 'llm_validated', 'week_relative', 'class_relative', 'dateparser', 'ambiguous', 'deterministic'
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


def _normalize_day(name: str) -> str:
    """Normalize a day abbreviation to its full lowercase name."""
    lower = name.strip().lower()
    return _DAY_ABBREV.get(lower, lower)


def _is_break_week(week_monday: date, holidays: list[dict]) -> bool:
    """A week is a break if a holiday period of 3+ consecutive days overlaps its weekdays."""
    week_fri = week_monday + timedelta(days=4)
    for h in holidays:
        h_start = _parse_holiday_date(h["start"])
        h_end = _parse_holiday_date(h["end"])
        duration = (h_end - h_start).days + 1
        if duration < 3:
            continue
        # Check if the holiday overlaps with Mon-Fri of this week
        if h_start <= week_fri and h_end >= week_monday:
            return True
    return False


def _teaching_week_monday(week_num: int, semester: SemesterContext) -> date | None:
    """Get the Monday of teaching week N, skipping break weeks."""
    if week_num < 1:
        return None
    # Find the Monday of the week containing semester.start
    sem_monday = semester.start - timedelta(days=semester.start.weekday())
    teaching_count = 0
    current_monday = sem_monday
    end_monday = semester.end + timedelta(days=7)
    while current_monday <= end_monday:
        if not _is_break_week(current_monday, semester.holidays):
            teaching_count += 1
            if teaching_count == week_num:
                return current_monday
        current_monday += timedelta(days=7)
    return None


def _build_class_dates(semester: SemesterContext) -> list[date]:
    """Build an ordered list of class meeting dates for the semester."""
    if not semester.meeting_days:
        return []

    meeting_weekdays = set()
    for day_name in semester.meeting_days:
        wd = DAY_MAP.get(day_name.lower().strip())
        if wd is not None:
            meeting_weekdays.add(wd)

    if not meeting_weekdays:
        return []

    dates: list[date] = []
    current = semester.start
    while current <= semester.end:
        if (
            current.weekday() in meeting_weekdays
            and not _is_in_holiday(current, semester.holidays)
        ):
            dates.append(current)
        current += timedelta(days=1)

    return dates


def _nth_meeting_date(n: int, semester: SemesterContext) -> date | None:
    """Find the date of the Nth class meeting, skipping holidays."""
    class_dates = _build_class_dates(semester)
    if 1 <= n <= len(class_dates):
        return class_dates[n - 1]
    return None


def _next_valid_day(
    d: date, target_weekday: int, holidays: list[dict], semester_end: date,
) -> date | None:
    """If d falls on a holiday, advance to next non-holiday occurrence of target_weekday."""
    # First find the target weekday in the same week as d
    days_ahead = (target_weekday - d.weekday()) % 7
    candidate = d + timedelta(days=days_ahead)
    # If the candidate is on a holiday, advance by 7 until clear
    attempts = 0
    while _is_in_holiday(candidate, holidays) and attempts < 52:
        candidate += timedelta(days=7)
        attempts += 1
    if candidate <= semester_end:
        return candidate
    return None


# ---------------------------------------------------------------------------
# Layer 2a: Week-relative resolution
# ---------------------------------------------------------------------------


def _try_week_relative(raw_text: str, semester: SemesterContext) -> ResolvedDate | None:
    """Try to resolve 'Week N', 'Week N DayName', 'End of Week N'."""

    # "End of Week N" — last meeting day in teaching week N
    m = _END_WEEK_RE.search(raw_text)
    if m:
        week_num = int(m.group(1))
        monday = _teaching_week_monday(week_num, semester)
        if monday is None:
            return None
        sunday = monday + timedelta(days=6)
        class_dates = _build_class_dates(semester)
        last_meeting = None
        for d in class_dates:
            if monday <= d <= sunday:
                last_meeting = d
        if last_meeting:
            return ResolvedDate(
                value=last_meeting, confidence=0.85,
                method="week_relative", original_text=raw_text,
            )
        return None

    # "Week N DayName" — specific day of teaching week N
    m = _WEEK_DAY_RE.search(raw_text)
    if m:
        week_num = int(m.group(1))
        day_name = _normalize_day(m.group(2))
        target_wd = DAY_MAP.get(day_name)
        if target_wd is None:
            return None
        monday = _teaching_week_monday(week_num, semester)
        if monday is None:
            return None
        target_date = monday + timedelta(days=target_wd)
        if _in_semester(target_date, semester) and not _is_in_holiday(
            target_date, semester.holidays
        ):
            return ResolvedDate(
                value=target_date, confidence=0.85,
                method="week_relative", original_text=raw_text,
            )
        return None

    # "Week N" / "WK N" — first meeting day of teaching week N
    m = _WEEK_ONLY_RE.search(raw_text)
    if m:
        week_num = int(m.group(1))
        monday = _teaching_week_monday(week_num, semester)
        if monday is None:
            return None
        sunday = monday + timedelta(days=6)
        class_dates = _build_class_dates(semester)
        for d in class_dates:
            if monday <= d <= sunday:
                return ResolvedDate(
                    value=d, confidence=0.85,
                    method="week_relative", original_text=raw_text,
                )
        # No meeting in that week — return monday if in semester
        if _in_semester(monday, semester):
            return ResolvedDate(
                value=monday, confidence=0.85,
                method="week_relative", original_text=raw_text,
            )
        return None

    return None


# ---------------------------------------------------------------------------
# Layer 2b: Class-relative resolution
# ---------------------------------------------------------------------------


def _try_class_relative(raw_text: str, semester: SemesterContext) -> ResolvedDate | None:
    """Try to resolve 'Class N', 'Lecture N', 'Session N', with optional day override."""

    # "Class N DayName" — e.g. "Class 3 Wed"
    m = _CLASS_DAY_RE.search(raw_text)
    if m:
        class_num = int(m.group(1))
        day_name = _normalize_day(m.group(2))
        target_wd = DAY_MAP.get(day_name)
        if target_wd is None:
            return None
        meeting = _nth_meeting_date(class_num, semester)
        if meeting is None:
            return None
        # Find the target day in the same week
        week_monday = meeting - timedelta(days=meeting.weekday())
        target_date = week_monday + timedelta(days=target_wd)
        if _in_semester(target_date, semester) and not _is_in_holiday(
            target_date, semester.holidays
        ):
            return ResolvedDate(
                value=target_date, confidence=0.8,
                method="class_relative", original_text=raw_text,
            )
        return None

    # "DayName in/of/during Class N" — e.g. "Wednesday in Class 3"
    m = _DAY_IN_CLASS_RE.search(raw_text)
    if m:
        day_name = _normalize_day(m.group(1))
        class_num = int(m.group(2))
        target_wd = DAY_MAP.get(day_name)
        if target_wd is None:
            return None
        meeting = _nth_meeting_date(class_num, semester)
        if meeting is None:
            return None
        week_monday = meeting - timedelta(days=meeting.weekday())
        target_date = week_monday + timedelta(days=target_wd)
        if _in_semester(target_date, semester) and not _is_in_holiday(
            target_date, semester.holidays
        ):
            return ResolvedDate(
                value=target_date, confidence=0.8,
                method="class_relative", original_text=raw_text,
            )
        return None

    # "Class N" / "Lecture N" / "Session N" — plain Nth meeting
    m = _CLASS_ONLY_RE.search(raw_text)
    if m:
        class_num = int(m.group(1))
        meeting = _nth_meeting_date(class_num, semester)
        if meeting is not None:
            return ResolvedDate(
                value=meeting, confidence=0.8,
                method="class_relative", original_text=raw_text,
            )
        return None

    return None


# ---------------------------------------------------------------------------
# Layer 3: Dateparser fallback
# ---------------------------------------------------------------------------


def _try_dateparser(raw_text: str, semester: SemesterContext) -> ResolvedDate | None:
    """Use the dateparser library with semester-aware settings."""
    try:
        import dateparser
    except ImportError:
        return None

    settings = {
        "PREFER_DATES_FROM": "future",
        "RELATIVE_BASE": datetime(
            semester.start.year, semester.start.month, semester.start.day
        ),
        "STRICT_PARSING": False,
    }

    parsed = dateparser.parse(raw_text, settings=settings)
    if parsed:
        d = parsed.date()
        if _in_semester(d, semester) and not _is_in_holiday(
            d, semester.holidays
        ):
            return ResolvedDate(
                value=d, confidence=0.7,
                method="dateparser", original_text=raw_text,
            )

    return None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def resolve_date(
    raw_text: str,
    semester: SemesterContext,
    llm_resolved: date | None = None,
    llm_confidence: float = 0.0,
) -> ResolvedDate:
    """Resolve a date string using a 4-layer cascade.

    1. Fast-exit for empty / ambiguous / ongoing phrases
    2. Layer 1: Validate LLM-resolved date against semester bounds + holidays
    3. Layer 2a: Week-relative patterns ("Week 3", "Week 3 Tuesday", "End of Week 5")
    4. Layer 2b: Class-relative patterns ("Class 4", "Wed in Class 3")
    5. Layer 3: Dateparser fallback ("January 15", "1/15/2026")
    6. Catch-all: ambiguous
    """
    # Fast-exit for empty / whitespace-only text
    if not raw_text or not raw_text.strip():
        return ResolvedDate(
            value=None, confidence=0.0, method="ambiguous",
            original_text=raw_text or "",
        )

    # Known ambiguous / ongoing phrases
    normalized = raw_text.strip().lower()
    if normalized in _AMBIGUOUS_PHRASES or normalized in ONGOING_PHRASES:
        return ResolvedDate(
            value=None, confidence=0.0, method="ambiguous",
            original_text=raw_text,
        )

    # Layer 1: Validate the LLM-resolved date
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

    # Layer 2a: Week-relative
    result = _try_week_relative(normalized, semester)
    if result is not None:
        result.original_text = raw_text
        return result

    # Layer 2b: Class-relative
    result = _try_class_relative(normalized, semester)
    if result is not None:
        result.original_text = raw_text
        return result

    # Layer 3: Dateparser fallback
    result = _try_dateparser(raw_text.strip(), semester)
    if result is not None:
        result.original_text = raw_text
        return result

    # Catch-all: ambiguous
    return ResolvedDate(
        value=None, confidence=0.0, method="ambiguous", original_text=raw_text,
    )


def resolve_all_dates(
    assessments: list[AssessmentExtraction],
    semester: SemesterContext,
) -> list[AssessmentExtraction]:
    """Validate and resolve dates for every assessment, returning updated copies.

    For each assessment the function:
      - Reads ``due_date_raw.value`` as the raw text
      - Parses ``due_date_resolved.value`` (if present) as the LLM-resolved date
      - Calls *resolve_date* to validate through all 4 layers
      - Writes the result back
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
