"""Tutor session management — CRUD for tutor sessions and events."""

from __future__ import annotations

import logging
from datetime import UTC, datetime

from lecturelink_api.models.tutor_models import (
    AssessmentChoice,
    SessionEntryResponse,
    TutorSessionResponse,
    TutorSessionSummaryResponse,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _session_to_response(row: dict) -> TutorSessionResponse:
    return TutorSessionResponse(
        id=row["id"],
        course_id=row["course_id"],
        mode=row["mode"],
        status=row["status"],
        lesson_plan=row.get("lesson_plan"),
        current_concept_index=row.get("current_concept_index", 0),
        current_step_index=row.get("current_step_index", 0),
        concepts_planned=row.get("concepts_planned", 0),
        concepts_completed=row.get("concepts_completed", 0),
        questions_asked=row.get("questions_asked", 0),
        questions_correct=row.get("questions_correct", 0),
        duration_seconds=row.get("duration_seconds", 0),
        suggested_duration_minutes=row.get("suggested_duration_minutes", 25),
        target_assessment_id=row.get("target_assessment_id"),
        started_at=row.get("started_at", ""),
        created_at=row.get("created_at", ""),
    )


def _parse_due_date(val) -> datetime | None:
    """Parse a TIMESTAMPTZ string to a datetime."""
    if val is None:
        return None
    if isinstance(val, datetime):
        return val
    if isinstance(val, str):
        try:
            return datetime.fromisoformat(val)
        except ValueError:
            return None
    return None


# ---------------------------------------------------------------------------
# 1. Session entry data
# ---------------------------------------------------------------------------


async def get_session_entry_data(
    supabase, course_id: str, user_id: str,
) -> SessionEntryResponse:
    """Fetch everything the tutor entry screen needs."""
    now = datetime.now(UTC)
    now_iso = now.isoformat()

    # Upcoming assessments
    assessments_result = (
        supabase.table("assessments")
        .select("id, title, due_date, weight_percent")
        .eq("course_id", course_id)
        .gte("due_date", now_iso)
        .order("due_date")
        .limit(10)
        .execute()
    )

    upcoming: list[AssessmentChoice] = []
    for a in assessments_result.data or []:
        dd = _parse_due_date(a.get("due_date"))
        days_remaining = (dd.date() - now.date()).days if dd else 0
        upcoming.append(AssessmentChoice(
            id=a["id"],
            title=a.get("title", "Untitled"),
            due_date=a.get("due_date", ""),
            weight_percent=a.get("weight_percent"),
            days_remaining=max(0, days_remaining),
        ))

    # Active session
    active_session = await get_active_session(supabase, course_id, user_id)

    # Mastery summary (Phase 3 tables may not exist)
    mastery_summary: list[dict] = []
    try:
        mastery_result = (
            supabase.table("mastery_scores")
            .select("concept_id, mastery_score, confidence")
            .eq("user_id", user_id)
            .execute()
        )
        if mastery_result.data:
            for m in mastery_result.data:
                score = m.get("mastery_score", 0)
                if score >= 0.8:
                    status = "strong"
                elif score >= 0.5:
                    status = "developing"
                else:
                    status = "needs_work"
                mastery_summary.append({
                    "concept_id": m["concept_id"],
                    "mastery": score,
                    "status": status,
                })
    except Exception:
        logger.warning(
            "Mastery summary unavailable (Phase 3 tables not deployed)"
        )

    return SessionEntryResponse(
        upcoming_assessments=upcoming,
        active_session=active_session,
        mastery_summary=mastery_summary,
        suggested_duration_minutes=25,
    )


# ---------------------------------------------------------------------------
# 2. Create session
# ---------------------------------------------------------------------------


async def create_session(
    supabase,
    course_id: str,
    user_id: str,
    mode: str,
    custom_topic: str | None = None,
    target_assessment_id: str | None = None,
    lesson_plan: dict | None = None,
) -> TutorSessionResponse:
    """Insert a new tutor session."""
    concepts_planned = 0
    if lesson_plan and isinstance(lesson_plan.get("concepts"), list):
        concepts_planned = len(lesson_plan["concepts"])

    payload = {
        "user_id": user_id,
        "course_id": course_id,
        "mode": mode,
        "status": "active",
        "lesson_plan": lesson_plan,
        "concepts_planned": concepts_planned,
    }
    if custom_topic:
        payload["custom_topic"] = custom_topic
    if target_assessment_id:
        payload["target_assessment_id"] = target_assessment_id

    result = supabase.table("tutor_sessions").insert(payload).execute()
    return _session_to_response(result.data[0])


# ---------------------------------------------------------------------------
# 3. Get active session
# ---------------------------------------------------------------------------


async def get_active_session(
    supabase, course_id: str, user_id: str,
) -> TutorSessionResponse | None:
    """Return the most recent active session for a course, or None."""
    result = (
        supabase.table("tutor_sessions")
        .select("*")
        .eq("course_id", course_id)
        .eq("user_id", user_id)
        .eq("status", "active")
        .order("created_at", desc=True)
        .limit(1)
        .execute()
    )
    if not result.data:
        return None
    return _session_to_response(result.data[0])


# ---------------------------------------------------------------------------
# 4. Update session progress
# ---------------------------------------------------------------------------


async def update_session_progress(
    supabase,
    session_id: str,
    user_id: str,
    concept_index: int | None = None,
    step_index: int | None = None,
    questions_asked_delta: int = 0,
    questions_correct_delta: int = 0,
    duration_delta: int = 0,
    concepts_completed_delta: int = 0,
) -> None:
    """Increment session counters and update position."""
    # Fetch current values
    current = (
        supabase.table("tutor_sessions")
        .select(
            "questions_asked, questions_correct, "
            "duration_seconds, concepts_completed"
        )
        .eq("id", session_id)
        .eq("user_id", user_id)
        .limit(1)
        .execute()
    )
    row = current.data
    if isinstance(row, list):
        row = row[0] if row else {}

    update: dict = {
        "questions_asked": (row.get("questions_asked", 0)
                            + questions_asked_delta),
        "questions_correct": (row.get("questions_correct", 0)
                              + questions_correct_delta),
        "duration_seconds": (row.get("duration_seconds", 0)
                             + duration_delta),
        "concepts_completed": (row.get("concepts_completed", 0)
                               + concepts_completed_delta),
    }
    if concept_index is not None:
        update["current_concept_index"] = concept_index
    if step_index is not None:
        update["current_step_index"] = step_index

    (
        supabase.table("tutor_sessions")
        .update(update)
        .eq("id", session_id)
        .eq("user_id", user_id)
        .execute()
    )


# ---------------------------------------------------------------------------
# 5. Pause session
# ---------------------------------------------------------------------------


async def pause_session(supabase, session_id: str, user_id: str) -> None:
    (
        supabase.table("tutor_sessions")
        .update({"status": "paused", "paused_at": _now_iso()})
        .eq("id", session_id)
        .eq("user_id", user_id)
        .execute()
    )


# ---------------------------------------------------------------------------
# 6. Resume session
# ---------------------------------------------------------------------------


async def resume_session(
    supabase, session_id: str, user_id: str,
) -> TutorSessionResponse:
    result = (
        supabase.table("tutor_sessions")
        .update({"status": "active", "paused_at": None})
        .eq("id", session_id)
        .eq("user_id", user_id)
        .execute()
    )
    return _session_to_response(result.data[0])


# ---------------------------------------------------------------------------
# 7. Complete session
# ---------------------------------------------------------------------------


async def complete_session(
    supabase, session_id: str, user_id: str,
) -> TutorSessionSummaryResponse:
    # Mark completed
    result = (
        supabase.table("tutor_sessions")
        .update({"status": "completed", "completed_at": _now_iso()})
        .eq("id", session_id)
        .eq("user_id", user_id)
        .execute()
    )
    session = result.data[0]

    return await _build_summary(supabase, session_id, user_id, session)


# ---------------------------------------------------------------------------
# 8. Log session event
# ---------------------------------------------------------------------------


async def log_session_event(
    supabase,
    session_id: str,
    user_id: str,
    course_id: str,
    event_type: str,
    **kwargs,
) -> str:
    """Insert a session event and return its id."""
    payload = {
        "session_id": session_id,
        "user_id": user_id,
        "course_id": course_id,
        "event_type": event_type,
        **kwargs,
    }
    result = (
        supabase.table("tutor_session_events").insert(payload).execute()
    )
    return result.data[0]["id"]


# ---------------------------------------------------------------------------
# 9. Session history
# ---------------------------------------------------------------------------


async def get_session_history(
    supabase, course_id: str, user_id: str, limit: int = 20,
) -> list[TutorSessionResponse]:
    result = (
        supabase.table("tutor_sessions")
        .select("*")
        .eq("course_id", course_id)
        .eq("user_id", user_id)
        .order("created_at", desc=True)
        .limit(limit)
        .execute()
    )
    return [_session_to_response(row) for row in (result.data or [])]


# ---------------------------------------------------------------------------
# 10. Get session summary (for any session, including active)
# ---------------------------------------------------------------------------


async def get_session_summary(
    supabase, session_id: str, user_id: str,
) -> TutorSessionSummaryResponse:
    session_result = (
        supabase.table("tutor_sessions")
        .select("*")
        .eq("id", session_id)
        .eq("user_id", user_id)
        .limit(1)
        .execute()
    )
    data = session_result.data
    session = data[0] if isinstance(data, list) else data
    return await _build_summary(supabase, session_id, user_id, session)


# ---------------------------------------------------------------------------
# Summary builder (shared between complete_session and get_session_summary)
# ---------------------------------------------------------------------------


async def _build_summary(
    supabase, session_id: str, user_id: str, session: dict,
) -> TutorSessionSummaryResponse:
    """Compute a session summary from events."""
    events_result = (
        supabase.table("tutor_session_events")
        .select("*")
        .eq("session_id", session_id)
        .eq("event_type", "question_answer")
        .order("created_at")
        .execute()
    )
    events = events_result.data or []

    # Group by concept
    concept_map: dict[str, dict] = {}
    for ev in events:
        title = ev.get("concept_title") or "General"
        if title not in concept_map:
            concept_map[title] = {
                "concept_title": title,
                "questions_asked": 0,
                "questions_correct": 0,
            }
        concept_map[title]["questions_asked"] += 1
        if ev.get("is_correct"):
            concept_map[title]["questions_correct"] += 1

    total_q = session.get("questions_asked", 0)
    total_c = session.get("questions_correct", 0)
    accuracy = (total_c / total_q * 100) if total_q > 0 else 0.0

    # Attempt mastery changes (Phase 3 tables)
    mastery_changes = None
    try:
        mastery_result = (
            supabase.table("mastery_scores")
            .select("concept_id, mastery_score")
            .eq("user_id", user_id)
            .execute()
        )
        if mastery_result.data:
            mastery_changes = [
                {"concept_id": m["concept_id"], "mastery": m["mastery_score"]}
                for m in mastery_result.data
            ]
    except Exception:
        logger.warning(
            "Mastery changes unavailable (Phase 3 tables not deployed)"
        )

    return TutorSessionSummaryResponse(
        session_id=session_id,
        mode=session.get("mode", ""),
        concepts_covered=list(concept_map.values()),
        total_questions=total_q,
        total_correct=total_c,
        accuracy_percent=round(accuracy, 1),
        duration_seconds=session.get("duration_seconds", 0),
        mastery_changes=mastery_changes,
    )
