"""Onboarding business logic for guided course setup."""

from __future__ import annotations

import logging
from datetime import date, datetime, timedelta

from .genai_client import get_genai_client as _get_client

logger = logging.getLogger(__name__)


PERSONALIZED_MESSAGE_MODEL = "gemini-2.5-flash"

PERSONALIZED_MESSAGE_SYSTEM_PROMPT = """\
Generate a personalized study briefing for a university student who just \
set up their course in LectureLink. You have their full syllabus data.
Your message should:

Name the course and acknowledge where they are in the semester.
Highlight the NEXT upcoming assessment — name it, state its date, \
state its grade weight, and state how many days until it's due.
If multiple big assessments are coming up in the next 30 days, \
mention the 2-3 most important ones by grade weight.
End with a clear, actionable next step (upload lectures, start \
studying, etc.).

The goal is to make the student think: "This app actually understands \
my course and is going to help me prepare for what matters."
Tone: Direct, confident, like a tutor who has read the syllabus. Not \
corporate, not sycophantic. 2-3 short paragraphs max. \
The message must be a complete, grammatically correct paragraph — never \
cut off mid-sentence.
For course_complete path: Congratulate them, reference the breadth of \
topics covered during the semester, and set expectations for practice mode.
Do NOT:

Use excessive exclamation marks or emojis.
Be vague ("you have some assignments coming up").
List every single assessment — focus on the important ones.
Mention features by name (don't say "Bayesian Knowledge Tracing").

Output plain text, no markdown formatting."""

# ---------------------------------------------------------------------------
# Onboarding path detection
# ---------------------------------------------------------------------------

def _parse_due_date(val) -> date | None:
    """Parse a due_date value (TIMESTAMPTZ string or date) to a date."""
    if val is None:
        return None
    if isinstance(val, date) and not isinstance(val, datetime):
        return val
    if isinstance(val, datetime):
        return val.date()
    if isinstance(val, str):
        try:
            return datetime.fromisoformat(val).date()
        except ValueError:
            return date.fromisoformat(val[:10])
    return None


DAY_OF_WEEK_MAP = {
    "monday": 0, "mon": 0,
    "tuesday": 1, "tue": 1,
    "wednesday": 2, "wed": 2,
    "thursday": 3, "thu": 3,
    "friday": 4, "fri": 4,
    "saturday": 5, "sat": 5,
    "sunday": 6, "sun": 6,
}


def suggest_onboarding_path(
    semester_start: date | str | None,
    semester_end: date | str | None,
) -> str:
    """Auto-detect the best onboarding path based on semester dates."""
    if semester_start is None or semester_end is None:
        return "mid_semester"

    if isinstance(semester_start, str):
        semester_start = date.fromisoformat(semester_start)
    if isinstance(semester_end, str):
        semester_end = date.fromisoformat(semester_end)

    today = date.today()
    total_days = (semester_end - semester_start).days

    if total_days <= 0:
        return "just_starting"

    if today < semester_start:
        return "just_starting"
    if today > semester_end:
        return "course_complete"

    elapsed = (today - semester_start).days
    pct = elapsed / total_days

    if pct < 0.15:
        return "just_starting"
    if pct > 0.95:
        return "course_complete"
    return "mid_semester"


# ---------------------------------------------------------------------------
# Semester progress
# ---------------------------------------------------------------------------


def get_semester_progress(course: dict) -> dict:
    """Calculate where the student is in the semester."""
    sem_start = course.get("semester_start")
    sem_end = course.get("semester_end")

    if sem_start is None or sem_end is None:
        return {
            "status": "in_progress",
            "progress_pct": 50,
            "weeks_elapsed": 0,
            "estimated_lectures_passed": 0,
            "days_remaining": 0,
        }

    if isinstance(sem_start, str):
        sem_start = date.fromisoformat(sem_start)
    if isinstance(sem_end, str):
        sem_end = date.fromisoformat(sem_end)

    today = date.today()
    total_days = (sem_end - sem_start).days
    if total_days <= 0:
        total_days = 1

    meeting_days = course.get("meeting_days") or []
    lectures_per_week = len(meeting_days) if meeting_days else 2

    if today < sem_start:
        return {
            "status": "not_started",
            "progress_pct": 0,
            "weeks_elapsed": 0,
            "estimated_lectures_passed": 0,
            "days_remaining": (sem_end - sem_start).days,
        }

    if today > sem_end:
        total_weeks = max(1, total_days // 7)
        return {
            "status": "complete",
            "progress_pct": 100,
            "weeks_elapsed": total_weeks,
            "estimated_lectures_passed": total_weeks * lectures_per_week,
            "days_remaining": 0,
        }

    elapsed = (today - sem_start).days
    pct = min(100, int((elapsed / total_days) * 100))
    weeks = elapsed // 7
    remaining = (sem_end - today).days

    return {
        "status": "in_progress",
        "progress_pct": pct,
        "weeks_elapsed": weeks,
        "estimated_lectures_passed": weeks * lectures_per_week,
        "days_remaining": remaining,
    }


# ---------------------------------------------------------------------------
# Lecture checklist generation
# ---------------------------------------------------------------------------


def generate_lecture_checklist(
    course: dict,
    syllabus_weekly_schedule: list[dict] | None = None,
    holidays: list[dict] | None = None,
) -> list[dict]:
    """Generate expected lecture slots from semester start to today."""
    sem_start = course.get("semester_start")
    sem_end = course.get("semester_end")

    if sem_start is None or sem_end is None:
        return []

    if isinstance(sem_start, str):
        sem_start = date.fromisoformat(sem_start)
    if isinstance(sem_end, str):
        sem_end = date.fromisoformat(sem_end)

    today = date.today()
    end_date = min(today, sem_end)

    if end_date < sem_start:
        return []

    meeting_days = course.get("meeting_days") or []
    meeting_day_nums = []
    for day_name in meeting_days:
        day_num = DAY_OF_WEEK_MAP.get(day_name.lower())
        if day_num is not None:
            meeting_day_nums.append(day_num)

    if not meeting_day_nums:
        return []

    # Build holiday date ranges for fast lookup
    holiday_dates: set[date] = set()
    for h in holidays or []:
        h_start = h.get("start_date")
        h_end = h.get("end_date")
        if not h_start:
            continue
        if isinstance(h_start, str):
            h_start = date.fromisoformat(h_start)
        if h_end is None:
            h_end = h_start
        elif isinstance(h_end, str):
            h_end = date.fromisoformat(h_end)
        d = h_start
        while d <= h_end:
            holiday_dates.add(d)
            d += timedelta(days=1)

    # Build weekly schedule topic map and detect break weeks
    # Use word-boundary regex to avoid false positives (e.g. "Breakdowns" matching "break")
    import re
    _BREAK_PATTERNS = [
        re.compile(r"\breading\s+week\b", re.IGNORECASE),
        re.compile(r"\b(?<![\w])break(?![\w])\b", re.IGNORECASE),
        re.compile(r"\bno\s+class\b", re.IGNORECASE),
        re.compile(r"\bno\s+lecture\b", re.IGNORECASE),
        re.compile(r"\bholiday\b", re.IGNORECASE),
        re.compile(r"\brecess\b", re.IGNORECASE),
        re.compile(r"\bstudy\s+week\b", re.IGNORECASE),
        re.compile(r"\boff\s+week\b", re.IGNORECASE),
    ]
    topic_map: dict[int, str | None] = {}
    break_weeks: set[int] = set()
    for entry in syllabus_weekly_schedule or []:
        wn = entry.get("week_number")
        topics = entry.get("topics") or []
        if wn is not None and topics:
            joined = ", ".join(topics)
            topic_map[wn] = joined
            if any(pat.search(joined) for pat in _BREAK_PATTERNS):
                break_weeks.add(wn)

    checklist: list[dict] = []
    lecture_number = 0
    current = sem_start

    while current <= end_date:
        if current.weekday() in meeting_day_nums and current not in holiday_dates:
            week_number = ((current - sem_start).days // 7) + 1
            if week_number in break_weeks:
                current += timedelta(days=1)
                continue
            lecture_number += 1
            day_name = current.strftime("%A").lower()
            topic_hint = topic_map.get(week_number)

            checklist.append({
                "lecture_number": lecture_number,
                "expected_date": current.isoformat(),
                "week_number": week_number,
                "topic_hint": topic_hint,
                "day_of_week": day_name,
                "status": "pending",
            })
        current += timedelta(days=1)

    return checklist


# ---------------------------------------------------------------------------
# Personalized message generation
# ---------------------------------------------------------------------------


async def generate_personalized_message(
    course: dict,
    assessments: list[dict],
    onboarding_path: str,
    semester_progress: dict | None = None,
    student_name: str | None = None,
) -> str:
    """Generate a personalized study briefing via Gemini Flash."""
    today = date.today()
    name = student_name or "Student"

    # Separate past and upcoming assessments
    past = []
    upcoming = []
    for a in assessments:
        dd = _parse_due_date(a.get("due_date"))
        if dd is None:
            upcoming.append(a)
            continue
        if dd < today:
            past.append(a)
        else:
            upcoming.append(a)

    # Top 5 by weight
    by_weight = sorted(
        assessments,
        key=lambda a: a.get("weight_percent") or 0,
        reverse=True,
    )[:5]

    # Next 3 upcoming by date
    upcoming_sorted = sorted(
        [a for a in upcoming if a.get("due_date")],
        key=lambda a: a["due_date"],
    )[:3]

    def _fmt_assessment(a: dict) -> str:
        raw_dd = a.get("due_date", "TBD")
        w = a.get("weight_percent")
        weight_str = f"{w}%" if w else "unweighted"
        days_until = ""
        dd_date = _parse_due_date(raw_dd) if raw_dd != "TBD" else None
        if dd_date:
            diff = (dd_date - today).days
            days_until = f" ({diff} days away)"
        dd_display = dd_date.isoformat() if dd_date else "TBD"
        return f"- {a.get('title', 'Untitled')}: {weight_str}, due {dd_display}{days_until}"

    top_assessments_text = "\n".join(_fmt_assessment(a) for a in by_weight)
    next_upcoming_text = "\n".join(_fmt_assessment(a) for a in upcoming_sorted)

    progress_text = ""
    if semester_progress:
        progress_text = (
            f"Semester progress: {semester_progress.get('progress_pct', 0)}% "
            f"({semester_progress.get('weeks_elapsed', 0)} weeks elapsed, "
            f"~{semester_progress.get('estimated_lectures_passed', 0)} "
            f"lectures passed)"
        )

    user_message = (
        f"Student name: {name}\n"
        f"Course: {course.get('name', 'Unknown')} "
        f"({course.get('code') or 'no code'})\n"
        f"Semester: {course.get('semester_start')} to "
        f"{course.get('semester_end')}\n"
        f"Meeting days: {', '.join(course.get('meeting_days') or ['N/A'])}\n"
        f"Today: {today.isoformat()}\n"
        f"Onboarding path: {onboarding_path}\n"
        f"Total assessments: {len(assessments)}, "
        f"past: {len(past)}, upcoming: {len(upcoming)}\n\n"
        f"Top 5 assessments by grade weight:\n{top_assessments_text}\n\n"
        f"Next 3 upcoming assessments:\n{next_upcoming_text}\n\n"
        f"{progress_text}"
    )

    client = _get_client()
    response = await client.aio.models.generate_content(
        model=PERSONALIZED_MESSAGE_MODEL,
        contents=user_message,
        config={
            "system_instruction": PERSONALIZED_MESSAGE_SYSTEM_PROMPT,
            "temperature": 0.7,
            "max_output_tokens": 500,
        },
    )
    return response.text


# ---------------------------------------------------------------------------
# Seed mastery from past scores (Path 2)
# ---------------------------------------------------------------------------


async def seed_mastery_from_scores(
    supabase,
    course_id: str,
    user_id: str,
) -> int:
    """Seed mastery_scores from past assessment results.

    Gracefully no-ops if Phase 2/3 tables don't exist yet.
    Returns count of mastery scores seeded.
    """
    try:
        result = (
            supabase.table("assessments")
            .select("id, student_score")
            .eq("course_id", course_id)
            .not_.is_("student_score", "null")
            .execute()
        )

        scored = result.data or []
        if not scored:
            return 0

        # Collect all (assessment_id, normalized_score) pairs
        assessment_scores: dict[str, float] = {}
        for assessment in scored:
            score_raw = assessment.get("student_score")
            if score_raw is None:
                continue
            assessment_scores[assessment["id"]] = max(0.1, min(0.95, score_raw / 100.0))

        if not assessment_scores:
            return 0

        # Bulk fetch all concept links for these assessments
        try:
            links = (
                supabase.table("concept_assessment_links")
                .select("concept_id, assessment_id")
                .in_("assessment_id", list(assessment_scores.keys()))
                .execute()
            )
        except Exception:
            logger.debug("concept_assessment_links bulk query failed")
            return 0

        # Build batch rows for upsert
        batch_rows = []
        for link in links.data or []:
            score = assessment_scores.get(link["assessment_id"])
            if score is None:
                continue
            batch_rows.append({
                "user_id": user_id,
                "concept_id": link["concept_id"],
                "mastery_score": score,
                "confidence": 0.3,
                "source": "onboarding_score",
            })

        if not batch_rows:
            return 0

        # Single bulk upsert
        try:
            supabase.table("mastery_scores").upsert(
                batch_rows,
                on_conflict="user_id,concept_id",
            ).execute()
        except Exception:
            logger.debug("mastery_scores bulk upsert failed")
            return 0

        return len(batch_rows)
    except Exception as e:
        logger.warning(
            "Mastery seeding skipped (Phase 3 tables not yet deployed): %s",
            e,
        )
        return 0
