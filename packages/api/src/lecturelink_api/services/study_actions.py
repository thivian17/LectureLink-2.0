"""Deterministic study action engine — primary study recommendation system.

This module is the canonical source of study recommendations. It computes
priorities based on due dates, concept mastery, and assessment weight without
LLM cost. Used by:
  - GET /api/study-actions (fast path, <100ms)
  - GET /api/courses/{course_id}/study-actions
  - Study Coach agent as context provider

For LLM-enhanced natural language framing of these recommendations,
see study_actions_llm.py (called only from /api/study-actions/enhanced).
"""

from __future__ import annotations

import logging
from datetime import date, timedelta

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

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


# ---------------------------------------------------------------------------
# Schedule-aware lecture gap computation
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# Study Action model
# ---------------------------------------------------------------------------


class StudyAction(BaseModel):
    action_type: str
    priority: float
    course_id: str
    course_name: str
    course_code: str | None = None
    title: str
    description: str
    cta_label: str
    cta_url: str
    metadata: dict = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# Per-course context gathering
# ---------------------------------------------------------------------------


async def _gather_course_context(supabase, course: dict, user_id: str) -> dict:
    """Fetch syllabus, lecture count, and upcoming assessments for one course."""
    course_id = course["id"]

    # Latest syllabus
    syllabus_result = (
        supabase.table("syllabi")
        .select("id, status, needs_review, reviewed_at")
        .eq("course_id", course_id)
        .order("created_at", desc=True)
        .limit(1)
        .execute()
    )
    syllabus = syllabus_result.data[0] if syllabus_result.data else None

    # Lecture count — use len(data) for reliability across postgrest-py versions
    lectures_result = (
        supabase.table("lectures")
        .select("id")
        .eq("course_id", course_id)
        .eq("user_id", user_id)
        .execute()
    )
    lecture_count = len(lectures_result.data) if lectures_result.data else 0

    # Upcoming assessments (due within 14 days)
    today_str = f"{date.today().isoformat()}T00:00:00Z"
    future_str = f"{(date.today() + timedelta(days=14)).isoformat()}T23:59:59Z"
    assessments_result = (
        supabase.table("assessments")
        .select("id, title, type, due_date, weight_percent, topics")
        .eq("course_id", course_id)
        .gte("due_date", today_str)
        .lte("due_date", future_str)
        .order("due_date")
        .execute()
    )

    return {
        "syllabus": syllabus,
        "lecture_count": lecture_count,
        "upcoming_assessments": assessments_result.data or [],
    }


# ---------------------------------------------------------------------------
# Action generation per course
# ---------------------------------------------------------------------------


def _lecture_day_label(last_date: date) -> str:
    """Human-readable label for a missed lecture date."""
    day_name = DAY_NAMES.get(last_date.weekday(), "")
    days_ago = (date.today() - last_date).days
    if days_ago == 0:
        return f"today ({day_name})"
    if days_ago == 1:
        return f"yesterday ({day_name})"
    return f"{day_name} ({last_date.strftime('%b %d')})"


async def _actions_for_course(
    supabase,
    course: dict,
    user_id: str,
    ctx: dict,
) -> list[StudyAction]:
    """Generate prioritized actions for a single course."""
    actions: list[StudyAction] = []
    cid = course["id"]
    name = course["name"]
    code = course.get("code")
    label = code or name
    base_url = f"/dashboard/courses/{cid}"

    syllabus = ctx["syllabus"]
    lecture_count = ctx["lecture_count"]
    upcoming = ctx["upcoming_assessments"]

    # Tier 1: No syllabus
    if not syllabus or syllabus.get("status") == "error":
        actions.append(StudyAction(
            action_type="upload_syllabus",
            priority=1.0,
            course_id=cid,
            course_name=name,
            course_code=code,
            title=f"Upload your syllabus for {label}",
            description=(
                "Upload a syllabus to unlock assessment tracking, "
                "study priorities, and personalized quiz generation."
            ),
            cta_label="Upload Syllabus",
            cta_url=base_url,
        ))
        return actions  # Can't analyse further without a syllabus

    # Tier 2: Syllabus needs review
    if syllabus.get("needs_review") and not syllabus.get("reviewed_at"):
        actions.append(StudyAction(
            action_type="review_syllabus",
            priority=0.95,
            course_id=cid,
            course_name=name,
            course_code=code,
            title=f"Review the AI extraction for {label}",
            description=(
                "The AI has extracted assessments and grading info from your syllabus. "
                "Review it for accuracy to improve your study recommendations."
            ),
            cta_label="Review Extraction",
            cta_url=f"{base_url}/syllabus/review",
        ))

    # Tier 3: Missing lectures (schedule-aware)
    meeting_days = course.get("meeting_days") or []
    semester_start_str = course.get("semester_start")
    holidays = course.get("holidays") or []

    if meeting_days and semester_start_str:
        try:
            sem_start = date.fromisoformat(str(semester_start_str))
        except (ValueError, TypeError):
            sem_start = None

        if sem_start:
            gap = compute_lecture_gap(
                sem_start, meeting_days, holidays, lecture_count
            )
            if gap.missing_count > 0:
                priority = 0.85 + min(gap.missing_count, 10) * 0.007

                if gap.last_expected_date:
                    day_label = _lecture_day_label(gap.last_expected_date)
                    title = (
                        f"You're {gap.missing_count} lecture"
                        f"{'s' if gap.missing_count != 1 else ''}"
                        f" behind in {label}"
                    )
                    desc = (
                        f"Your last scheduled class was {day_label} and "
                        f"hasn't been uploaded yet. Upload your recent "
                        f"lectures to keep your study plan current."
                    )
                else:
                    title = f"Upload your first lecture for {label}"
                    desc = (
                        "Upload lecture slides or audio to unlock "
                        "search, quizzes, and study recommendations."
                    )

                actions.append(StudyAction(
                    action_type="upload_lectures",
                    priority=priority,
                    course_id=cid,
                    course_name=name,
                    course_code=code,
                    title=title,
                    description=desc,
                    cta_label="Upload Lecture",
                    cta_url=f"{base_url}/lectures/new",
                    metadata={
                        "missing_count": gap.missing_count,
                        "expected_count": gap.expected_count,
                        "actual_count": gap.actual_count,
                    },
                ))

    # Tier 4 & 5: Assessment prep + weak concepts (need performance data)
    if upcoming or lecture_count > 0:
        try:
            from .performance import get_performance

            perf = await get_performance(supabase, cid, user_id)
            weak_concepts = perf.get("concepts", [])
            weak_map = {
                c["concept_id"]: c
                for c in weak_concepts
                if c.get("mastery", 1.0) < 0.5 and c.get("total_attempts", 0) > 0
            }

            # Tier 4: Upcoming assessment + weak linked concepts
            for assessment in upcoming:
                due_str = assessment.get("due_date")
                if not due_str:
                    continue
                try:
                    due = date.fromisoformat(str(due_str)[:10])
                except (ValueError, TypeError):
                    continue

                days_until = (due - date.today()).days
                logger.debug(
                    "Assessment %s due=%s days_until=%d",
                    assessment.get("title"), due, days_until,
                )
                weight = assessment.get("weight_percent") or 10

                # Find weak concepts linked to this assessment
                linked_weak = []
                for concept in weak_concepts:
                    for link in concept.get("linked_assessments", []):
                        if link.get("assessment_id") == assessment["id"]:
                            if concept["concept_id"] in weak_map:
                                linked_weak.append(concept)
                            break

                if linked_weak:
                    urgency = 1.0 / (1.0 + days_until)
                    weight_factor = weight / 100.0
                    priority = 0.70 + urgency * 0.10 + weight_factor * 0.05
                    priority = min(priority, 0.85)

                    weakest = min(linked_weak, key=lambda c: c["mastery"])
                    mastery_pct = round(weakest["mastery"] * 100)
                    a_title = assessment["title"]

                    actions.append(StudyAction(
                        action_type="assessment_prep",
                        priority=priority,
                        course_id=cid,
                        course_name=name,
                        course_code=code,
                        title=(
                            f"{a_title} in {days_until} day"
                            f"{'s' if days_until != 1 else ''}"
                            f" \u2014 focus on {weakest['title']}"
                        ),
                        description=(
                            f"Your mastery of \"{weakest['title']}\" is at "
                            f"{mastery_pct}%. This concept appears on the "
                            f"upcoming {assessment['type']}. Start a study "
                            f"session to improve before the deadline."
                        ),
                        cta_label="Study Now",
                        cta_url=f"{base_url}/tutor",
                        metadata={
                            "assessment_id": assessment["id"],
                            "assessment_title": a_title,
                            "days_until": days_until,
                            "weak_concept": weakest["title"],
                            "mastery": weakest["mastery"],
                        },
                    ))

            # Tier 5: General weak concept study (no imminent exam)
            if not upcoming and weak_map:
                weakest = min(
                    weak_map.values(), key=lambda c: c["mastery"]
                )
                mastery_pct = round(weakest["mastery"] * 100)
                priority = 0.40 + (1 - weakest["mastery"]) * 0.20

                actions.append(StudyAction(
                    action_type="take_quiz",
                    priority=priority,
                    course_id=cid,
                    course_name=name,
                    course_code=code,
                    title=(
                        f"Review \"{weakest['title']}\" in {label}"
                        f" ({mastery_pct}% mastery)"
                    ),
                    description=(
                        f"Start a study session to strengthen your "
                        f"understanding of \"{weakest['title']}\". "
                        f"Your mastery is currently at {mastery_pct}%."
                    ),
                    cta_label="Study Now",
                    cta_url=f"{base_url}/tutor",
                    metadata={
                        "concept_title": weakest["title"],
                        "mastery": weakest["mastery"],
                    },
                ))
        except Exception:
            logger.debug(
                "Skipping performance-based actions for course %s", cid,
                exc_info=True,
            )

    return actions


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------


async def get_study_actions(
    supabase,
    user_id: str,
    course_id: str | None = None,
    limit: int = 5,
) -> list[StudyAction]:
    """Compute ranked study actions across all (or one) course(s).

    Returns actions sorted by priority descending, limited to *limit*.
    """
    # Fetch courses
    query = (
        supabase.table("courses")
        .select("*")
        .eq("user_id", user_id)
    )
    if course_id:
        query = query.eq("id", course_id)

    courses_result = query.execute()
    courses = courses_result.data or []

    all_actions: list[StudyAction] = []
    for course in courses:
        try:
            ctx = await _gather_course_context(supabase, course, user_id)
            actions = await _actions_for_course(supabase, course, user_id, ctx)
            all_actions.extend(actions)
        except Exception:
            logger.warning(
                "Failed to compute actions for course %s, skipping",
                course.get("id"),
                exc_info=True,
            )

    all_actions.sort(key=lambda a: a.priority, reverse=True)
    return all_actions[:limit]
