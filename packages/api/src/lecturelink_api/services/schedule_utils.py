"""Schedule-aware utilities for lecture gap computation.

Extracted from study_actions.py — used by dashboard_briefing and other services
that need to compare expected vs actual lecture uploads.
"""

from __future__ import annotations

from datetime import date, timedelta

from pydantic import BaseModel

DAY_MAP: dict[str, int] = {
    "Monday": 0, "Mon": 0,
    "Tuesday": 1, "Tue": 1,
    "Wednesday": 2, "Wed": 2,
    "Thursday": 3, "Thu": 3,
    "Friday": 4, "Fri": 4,
    "Saturday": 5, "Sat": 5,
    "Sunday": 6, "Sun": 6,
}

DAY_NAMES = {0: "Monday", 1: "Tuesday", 2: "Wednesday", 3: "Thursday",
             4: "Friday", 5: "Saturday", 6: "Sunday"}


def _build_holiday_dates(holidays: list[dict] | None) -> set[date]:
    """Expand holiday ranges into a set of individual dates."""
    result: set[date] = set()
    for h in holidays or []:
        try:
            h_start = date.fromisoformat(str(h["start_date"]))
            h_end = date.fromisoformat(str(h["end_date"]))
            d = h_start
            while d <= h_end:
                result.add(d)
                d += timedelta(days=1)
        except (KeyError, ValueError, TypeError):
            continue
    return result


def compute_expected_meetings(
    semester_start: date,
    meeting_days: list[str],
    holidays: list[dict] | None = None,
    as_of: date | None = None,
) -> list[date]:
    """Generate all expected class meeting dates up to *as_of*.

    Skips dates that fall within any holiday range.
    """
    today = as_of or date.today()
    if not meeting_days:
        return []

    target_weekdays = [DAY_MAP[d] for d in meeting_days if d in DAY_MAP]
    if not target_weekdays:
        return []

    holiday_dates = _build_holiday_dates(holidays)

    meetings: list[date] = []
    current = semester_start
    while current <= today:
        if current.weekday() in target_weekdays and current not in holiday_dates:
            meetings.append(current)
        current += timedelta(days=1)

    return meetings


class LectureGap(BaseModel):
    expected_count: int
    actual_count: int
    missing_count: int
    next_expected_date: date | None = None
    last_expected_date: date | None = None
    days_since_last_expected: int | None = None


def compute_lecture_gap(
    semester_start: date,
    meeting_days: list[str],
    holidays: list[dict] | None,
    actual_lecture_count: int,
    as_of: date | None = None,
) -> LectureGap:
    """Compare expected meetings with actual uploaded lecture count."""
    today = as_of or date.today()
    meetings = compute_expected_meetings(
        semester_start, meeting_days, holidays, as_of=today
    )

    expected = len(meetings)
    missing = max(0, expected - actual_lecture_count)

    # Find next expected meeting date after today
    target_weekdays = [DAY_MAP[d] for d in meeting_days if d in DAY_MAP]
    holiday_dates = _build_holiday_dates(holidays)
    next_expected: date | None = None
    cursor = today + timedelta(days=1)
    for _ in range(30):
        if cursor.weekday() in target_weekdays and cursor not in holiday_dates:
            next_expected = cursor
            break
        cursor += timedelta(days=1)

    last_expected = meetings[-1] if meetings else None
    days_since = (today - last_expected).days if last_expected else None

    return LectureGap(
        expected_count=expected,
        actual_count=actual_lecture_count,
        missing_count=missing,
        next_expected_date=next_expected,
        last_expected_date=last_expected,
        days_since_last_expected=days_since,
    )
