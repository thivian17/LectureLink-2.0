"""Dashboard actions service — timeline and best-next-actions for the academic command center."""

from __future__ import annotations

import logging
from datetime import UTC, date, datetime, timedelta

from lecturelink_api.models.readiness_v2 import (
    EXAM_TYPES,
    DashboardActionsResponse,
    DashboardTimelineResponse,
    StatsRow,
    SuggestedAction,
    TimelineItem,
)
from lecturelink_api.services.assessment_prep import get_assessment_concepts

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _classify_urgency(days_until: int, readiness: float) -> str:
    """Classify urgency based on days until due and readiness proxy."""
    if days_until <= 3 and readiness < 0.5:
        return "critical"
    if days_until <= 3 or readiness < 0.4:
        return "high"
    if days_until <= 7 or readiness < 0.6:
        return "medium"
    return "low"


def _urgency_sort_key(urgency: str | None) -> int:
    """Lower number = more urgent (for sorting)."""
    return {"critical": 0, "high": 1, "medium": 2, "low": 3}.get(urgency or "low", 4)


def _urgency_factor(days_until: int) -> float:
    """Compute urgency factor: closer deadlines get higher weight."""
    if days_until <= 3:
        return 1.0
    if days_until <= 7:
        return 0.7
    return 0.4


def _start_of_week() -> datetime:
    """Return midnight UTC of the most recent Monday."""
    today = datetime.now(UTC).date()
    monday = today - timedelta(days=today.weekday())
    return datetime(monday.year, monday.month, monday.day, tzinfo=UTC)


# ---------------------------------------------------------------------------
# Timeline
# ---------------------------------------------------------------------------


async def get_academic_timeline(
    supabase,
    user_id: str,
    days: int = 14,
) -> DashboardTimelineResponse:
    """Gather all timeline items across all courses for the next N days."""
    today = date.today()
    today_iso = today.isoformat()
    future = today + timedelta(days=days)
    future_iso = future.isoformat()

    # 1. Get all user's courses
    try:
        courses_result = (
            supabase.table("courses")
            .select("id, name, code")
            .eq("user_id", user_id)
            .execute()
        )
        courses = courses_result.data or []
    except Exception:
        logger.warning("Failed to fetch courses for timeline", exc_info=True)
        return DashboardTimelineResponse(items=[], today=today_iso)

    if not courses:
        return DashboardTimelineResponse(items=[], today=today_iso)

    course_map = {c["id"]: c for c in courses}
    course_ids = list(course_map.keys())

    items: list[TimelineItem] = []

    # 2a. Assessments within date range
    try:
        assessments_result = (
            supabase.table("assessments")
            .select("id, course_id, title, type, due_date, weight_percent")
            .in_("course_id", course_ids)
            .gte("due_date", today_iso)
            .lte("due_date", future_iso)
            .order("due_date")
            .execute()
        )
        assessments = assessments_result.data or []
    except Exception:
        logger.warning("Failed to fetch assessments for timeline", exc_info=True)
        assessments = []

    # For exam-type assessments, compute lightweight readiness
    # Fetch assessment concepts and learning_events
    exam_assessment_ids = [
        a["id"] for a in assessments if (a.get("type") or "").lower() in EXAM_TYPES
    ]

    # Get linked concept counts per assessment via assessment_prep
    links_by_assessment: dict[str, list[str]] = {}
    if exam_assessment_ids:
        for aid in exam_assessment_ids:
            a_course_id = next(
                (a["course_id"] for a in assessments if a["id"] == aid), ""
            )
            try:
                concepts = await get_assessment_concepts(
                    supabase, aid, a_course_id, user_id,
                )
                links_by_assessment[aid] = [c["concept_id"] for c in concepts]
            except Exception:
                logger.warning("Failed to fetch assessment concepts for %s", aid, exc_info=True)

    # Get all interacted concept IDs for this user across courses
    interacted_concepts: set[str] = set()
    if links_by_assessment:
        try:
            events_result = (
                supabase.table("learning_events")
                .select("concept_id")
                .eq("user_id", user_id)
                .in_("course_id", course_ids)
                .execute()
            )
            interacted_concepts = {
                e["concept_id"] for e in (events_result.data or []) if e.get("concept_id")
            }
        except Exception:
            logger.warning("Failed to fetch learning events for timeline", exc_info=True)

    for a in assessments:
        course = course_map.get(a["course_id"], {})
        a_type = (a.get("type") or "assignment").lower()
        due_str = str(a.get("due_date", ""))[:10]

        readiness: float | None = None
        urgency: str | None = None

        if a_type in EXAM_TYPES:
            # Lightweight readiness: covered / total linked concepts
            linked = links_by_assessment.get(a["id"], [])
            total = len(linked)
            if total > 0:
                covered = sum(1 for cid in linked if cid in interacted_concepts)
                readiness = round(covered / total, 2)
            else:
                readiness = 0.0
            try:
                days_until = (date.fromisoformat(due_str) - today).days
            except (ValueError, TypeError):
                days_until = 14
            urgency = _classify_urgency(days_until, readiness)

        items.append(
            TimelineItem(
                date=due_str,
                item_type=a_type,
                title=a["title"],
                course_id=a["course_id"],
                course_name=course.get("name", ""),
                course_code=course.get("code"),
                assessment_id=a["id"],
                readiness=readiness,
                urgency=urgency,
            )
        )

    # 2b. Lectures needing review
    try:
        lectures_result = (
            supabase.table("lectures")
            .select("id, course_id, title, lecture_date, lecture_number")
            .in_("course_id", course_ids)
            .eq("processing_status", "completed")
            .execute()
        )
        lectures = lectures_result.data or []
    except Exception:
        logger.warning("Failed to fetch lectures for timeline", exc_info=True)
        lectures = []

    if lectures:
        lecture_ids = [lec["id"] for lec in lectures]

        # Get concepts per lecture
        concepts_by_lecture: dict[str, list[str]] = {}
        try:
            concepts_result = (
                supabase.table("concepts")
                .select("id, lecture_id")
                .in_("lecture_id", lecture_ids)
                .execute()
            )
            for c in concepts_result.data or []:
                concepts_by_lecture.setdefault(c["lecture_id"], []).append(c["id"])
        except Exception:
            logger.warning("Failed to fetch concepts for lectures", exc_info=True)

        # Reuse interacted_concepts if we have them, otherwise fetch
        if not interacted_concepts and concepts_by_lecture:
            try:
                events_result = (
                    supabase.table("learning_events")
                    .select("concept_id")
                    .eq("user_id", user_id)
                    .in_("course_id", course_ids)
                    .execute()
                )
                interacted_concepts = {
                    e["concept_id"]
                    for e in (events_result.data or [])
                    if e.get("concept_id")
                }
            except Exception:
                logger.warning("Failed to fetch learning events", exc_info=True)

        for lec in lectures:
            lec_concepts = concepts_by_lecture.get(lec["id"], [])
            if not lec_concepts:
                continue
            # Check if student has zero interactions with ANY of this lecture's concepts
            has_any = any(cid in interacted_concepts for cid in lec_concepts)
            if has_any:
                continue

            course = course_map.get(lec["course_id"], {})
            if not lec.get("lecture_date"):
                continue
            lec_date = str(lec["lecture_date"])[:10]

            items.append(
                TimelineItem(
                    date=lec_date,
                    item_type="lecture_review",
                    title=lec["title"],
                    course_id=lec["course_id"],
                    course_name=course.get("name", ""),
                    course_code=course.get("code"),
                    needs_review=True,
                )
            )

    # 3. Sort by date, then urgency within each date
    items.sort(key=lambda i: (i.date, _urgency_sort_key(i.urgency)))

    return DashboardTimelineResponse(items=items, today=today_iso)


# ---------------------------------------------------------------------------
# Best Next Actions
# ---------------------------------------------------------------------------


async def get_best_next_actions(
    supabase,
    user_id: str,
    limit: int = 4,
) -> DashboardActionsResponse:
    """Generate ranked action recommendations across all courses."""
    today = date.today()
    today_iso = today.isoformat()
    future = today + timedelta(days=14)
    future_iso = future.isoformat()

    # 1. Get courses
    try:
        courses_result = (
            supabase.table("courses")
            .select("id, name, code")
            .eq("user_id", user_id)
            .execute()
        )
        courses = courses_result.data or []
    except Exception:
        logger.warning("Failed to fetch courses for actions", exc_info=True)
        return DashboardActionsResponse(actions=[])

    if not courses:
        return DashboardActionsResponse(actions=[])

    course_map = {c["id"]: c for c in courses}
    course_ids = list(course_map.keys())

    actions: list[tuple[float, SuggestedAction]] = []  # (priority_score, action)

    # 2. Upcoming exam-type assessments
    try:
        assessments_result = (
            supabase.table("assessments")
            .select("id, course_id, title, type, due_date, weight_percent")
            .in_("course_id", course_ids)
            .gte("due_date", today_iso)
            .lte("due_date", future_iso)
            .order("due_date")
            .execute()
        )
        assessments = assessments_result.data or []
    except Exception:
        logger.warning("Failed to fetch assessments for actions", exc_info=True)
        assessments = []

    exam_assessments = [
        a for a in assessments if (a.get("type") or "").lower() in EXAM_TYPES
    ]

    # Get concept links via assessment_prep for readiness proxy
    links_by_assessment: dict[str, list[str]] = {}
    if exam_assessments:
        for a in exam_assessments:
            try:
                concepts = await get_assessment_concepts(
                    supabase, a["id"], a["course_id"], user_id,
                )
                links_by_assessment[a["id"]] = [c["concept_id"] for c in concepts]
            except Exception:
                pass

    interacted_concepts: set[str] = set()
    if links_by_assessment:
        try:
            events_result = (
                supabase.table("learning_events")
                .select("concept_id")
                .eq("user_id", user_id)
                .in_("course_id", course_ids)
                .execute()
            )
            interacted_concepts = {
                e["concept_id"] for e in (events_result.data or []) if e.get("concept_id")
            }
        except Exception:
            pass

    for a in exam_assessments:
        due_str = str(a.get("due_date", ""))[:10]
        try:
            days_until = (date.fromisoformat(due_str) - today).days
        except (ValueError, TypeError):
            days_until = 14

        linked = links_by_assessment.get(a["id"], [])
        total = len(linked)
        if total > 0:
            covered = sum(1 for cid in linked if cid in interacted_concepts)
            readiness = covered / total
        else:
            readiness = 0.0

        if readiness >= 0.8:
            continue  # Skip well-prepared assessments

        weak_count = total - (
            sum(1 for cid in linked if cid in interacted_concepts) if total else 0
        )
        uf = _urgency_factor(days_until)
        priority = uf * (1.0 - readiness)
        estimated_gain = round((1.0 - readiness) * 100 * 0.3)

        actions.append((
            priority,
            SuggestedAction(
                action_type="study_session",
                title=f"Prepare for {a['title']}",
                description=f"Focus on {weak_count} weak concepts",
                estimated_minutes=20,
                target_course_id=a["course_id"],
                target_assessment_id=a["id"],
                urgency=_classify_urgency(days_until, readiness),
                expected_impact=f"+{estimated_gain}% readiness",
            ),
        ))

    # 3. Unreviewed lectures
    try:
        lectures_result = (
            supabase.table("lectures")
            .select("id, course_id, title, lecture_date, lecture_number")
            .in_("course_id", course_ids)
            .eq("processing_status", "completed")
            .execute()
        )
        lectures = lectures_result.data or []
    except Exception:
        lectures = []

    if lectures:
        lecture_ids = [lec["id"] for lec in lectures]
        concepts_by_lecture: dict[str, list[str]] = {}
        try:
            concepts_result = (
                supabase.table("concepts")
                .select("id, lecture_id")
                .in_("lecture_id", lecture_ids)
                .execute()
            )
            for c in concepts_result.data or []:
                concepts_by_lecture.setdefault(c["lecture_id"], []).append(c["id"])
        except Exception:
            pass

        # Refresh interacted if needed
        if not interacted_concepts and concepts_by_lecture:
            try:
                events_result = (
                    supabase.table("learning_events")
                    .select("concept_id")
                    .eq("user_id", user_id)
                    .in_("course_id", course_ids)
                    .execute()
                )
                interacted_concepts = {
                    e["concept_id"]
                    for e in (events_result.data or [])
                    if e.get("concept_id")
                }
            except Exception:
                pass

        for lec in lectures:
            lec_concepts = concepts_by_lecture.get(lec["id"], [])
            if not lec_concepts:
                continue
            has_any = any(cid in interacted_concepts for cid in lec_concepts)
            if has_any:
                continue

            concept_count = len(lec_concepts)
            actions.append((
                0.5,  # medium priority for lecture reviews
                SuggestedAction(
                    action_type="lecture_review",
                    title=f"Review {lec['title']}",
                    description=f"Covers {concept_count} new concepts",
                    estimated_minutes=15,
                    target_course_id=lec["course_id"],
                    urgency="medium",
                    expected_impact=f"Unlock {concept_count} concepts",
                ),
            ))

    # 4. Low freshness concepts (flash review opportunities)
    try:
        # Concepts with old learning events — stale knowledge
        cutoff = (datetime.now(UTC) - timedelta(days=7)).isoformat()
        stale_result = (
            supabase.table("learning_events")
            .select("concept_id, course_id")
            .eq("user_id", user_id)
            .in_("course_id", course_ids)
            .lte("created_at", cutoff)
            .execute()
        )
        stale_concepts = stale_result.data or []
        # Deduplicate
        seen: set[str] = set()
        unique_stale: list[dict] = []
        for s in stale_concepts:
            cid = s.get("concept_id", "")
            if cid and cid not in seen:
                seen.add(cid)
                unique_stale.append(s)

        if unique_stale and not actions:
            # Only suggest flash review if no higher-priority actions
            actions.append((
                0.3,
                SuggestedAction(
                    action_type="flash_review",
                    title="Flash review stale concepts",
                    description=f"Refresh {min(len(unique_stale), 10)} concepts you haven't practiced recently",
                    estimated_minutes=10,
                    target_course_id=unique_stale[0].get("course_id"),
                    urgency="low",
                    expected_impact=f"Refresh {min(len(unique_stale), 10)} concepts",
                ),
            ))
    except Exception:
        logger.warning("Failed to check stale concepts", exc_info=True)

    # 5. Sort by priority descending, return top N
    actions.sort(key=lambda x: x[0], reverse=True)
    return DashboardActionsResponse(actions=[a for _, a in actions[:limit]])


# ---------------------------------------------------------------------------
# Weekly Stats
# ---------------------------------------------------------------------------


async def get_weekly_stats(
    supabase,
    user_id: str,
) -> StatsRow:
    """Compact stats for the command center header."""
    week_start = _start_of_week()
    week_start_iso = week_start.isoformat()

    # Streak
    streak = 0
    try:
        streak_result = (
            supabase.table("user_streaks")
            .select("current_streak")
            .eq("user_id", user_id)
            .execute()
        )
        if streak_result.data:
            streak = streak_result.data[0].get("current_streak", 0)
    except Exception:
        pass

    # XP this week
    xp_this_week = 0
    try:
        xp_result = (
            supabase.table("xp_events")
            .select("amount")
            .eq("user_id", user_id)
            .gte("created_at", week_start_iso)
            .execute()
        )
        xp_this_week = sum(e.get("amount", 0) for e in (xp_result.data or []))
    except Exception:
        pass

    # Study minutes this week (learn_sessions + tutor_sessions)
    study_minutes = 0
    try:
        learn_result = (
            supabase.table("learn_sessions")
            .select("duration_seconds")
            .eq("user_id", user_id)
            .gte("created_at", week_start_iso)
            .execute()
        )
        for s in learn_result.data or []:
            study_minutes += (s.get("duration_seconds") or 0) // 60
    except Exception:
        pass

    try:
        tutor_result = (
            supabase.table("tutor_sessions")
            .select("duration_seconds")
            .eq("user_id", user_id)
            .gte("created_at", week_start_iso)
            .execute()
        )
        for s in tutor_result.data or []:
            study_minutes += (s.get("duration_seconds") or 0) // 60
    except Exception:
        pass

    # Concepts practiced this week
    concepts_practiced = 0
    try:
        events_result = (
            supabase.table("learning_events")
            .select("concept_id")
            .eq("user_id", user_id)
            .gte("created_at", week_start_iso)
            .execute()
        )
        concepts_practiced = len({
            e["concept_id"] for e in (events_result.data or []) if e.get("concept_id")
        })
    except Exception:
        pass

    return StatsRow(
        streak=streak,
        xp_this_week=xp_this_week,
        study_minutes_this_week=study_minutes,
        concepts_practiced_this_week=concepts_practiced,
    )
