"""Assessment readiness score computation."""

from __future__ import annotations

import logging
from datetime import UTC, datetime

logger = logging.getLogger(__name__)

# Urgency bands
URGENCY_BANDS = [
    (80, "ready"),
    (60, "strong"),
    (30, "building"),
    (0, "danger"),
]


def _classify_urgency(score: float) -> str:
    """Classify readiness score into urgency band."""
    for threshold, label in URGENCY_BANDS:
        if score >= threshold:
            return label
    return "danger"


def _days_until(due_date: datetime | str | None) -> int | None:
    """Compute days until a due date. Returns negative values for past dates."""
    if not due_date:
        return None
    if isinstance(due_date, str):
        try:
            due_date = datetime.fromisoformat(due_date)
        except ValueError:
            return None
    now = datetime.now(UTC)
    if due_date.tzinfo is None:
        due_date = due_date.replace(tzinfo=UTC)
    return (due_date - now).days


def _is_past_due(due_date: datetime | str | None) -> bool:
    """Return True if the assessment's due date is in the past."""
    days = _days_until(due_date)
    return days is not None and days < 0


def _grade_letter(score: float) -> str:
    """Convert a percentage score to a letter grade."""
    if score >= 93:
        return "A"
    if score >= 90:
        return "A-"
    if score >= 87:
        return "B+"
    if score >= 83:
        return "B"
    if score >= 80:
        return "B-"
    if score >= 77:
        return "C+"
    if score >= 73:
        return "C"
    if score >= 70:
        return "C-"
    if score >= 67:
        return "D+"
    if score >= 60:
        return "D"
    return "F"


async def get_assessment_readiness(
    supabase, user_id: str, assessment_id: str
) -> dict:
    """Compute readiness for a single assessment.

    Readiness = weighted average of concept mastery scores, weighted by
    relevance_score from concept_assessment_links.
    """
    # 1. Get assessment info
    assessment_result = (
        supabase.table("assessments")
        .select("id, title, due_date, weight_percent, type, course_id")
        .eq("id", assessment_id)
        .execute()
    )
    if not assessment_result.data:
        return {"assessment_id": assessment_id, "readiness_score": 0, "error": "not_found"}

    assessment = assessment_result.data[0]
    course_id = assessment["course_id"]

    # 2. Get concept-assessment links
    links_result = (
        supabase.table("concept_assessment_links")
        .select("concept_id, relevance_score")
        .eq("assessment_id", assessment_id)
        .execute()
    )
    links = links_result.data or []

    if not links:
        return {
            "assessment_id": assessment_id,
            "title": assessment["title"],
            "due_date": assessment.get("due_date"),
            "weight_percent": assessment.get("weight_percent"),
            "type": assessment.get("type", "exam"),
            "readiness_score": 0.0,
            "concept_scores": [],
            "days_until_due": _days_until(assessment.get("due_date")),
            "urgency": "danger",
            "trend": 0.0,
        }

    # 3. Get mastery data for this course
    try:
        mastery_result = supabase.rpc(
            "get_concept_mastery",
            {"p_course_id": course_id, "p_user_id": user_id},
        ).execute()
        mastery_data = {
            m["concept_id"]: m for m in (mastery_result.data or [])
        }
    except Exception:
        logger.warning("get_concept_mastery RPC failed", exc_info=True)
        mastery_data = {}

    # 4. Compute weighted readiness
    total_weight = 0.0
    weighted_sum = 0.0
    concept_scores = []

    for link in links:
        cid = link["concept_id"]
        relevance = link.get("relevance_score", 0.5)
        m_data = mastery_data.get(cid, {})

        attempts = m_data.get("total_attempts", 0)
        accuracy = m_data.get("accuracy", 0.0)
        recent = m_data.get("recent_accuracy", 0.0)
        mastery = 0.0 if attempts == 0 else round(accuracy * 0.6 + recent * 0.4, 4)

        weight = max(relevance, 0.1)
        total_weight += weight
        weighted_sum += mastery * weight

        concept_scores.append({
            "concept_id": cid,
            "title": m_data.get("concept_title", "Unknown"),
            "mastery": mastery,
            "total_attempts": attempts,
            "relevance": relevance,
            "weighted_score": round(mastery * weight, 4),
        })

    readiness = (weighted_sum / total_weight * 100) if total_weight > 0 else 0.0
    readiness = round(min(readiness, 100.0), 1)

    return {
        "assessment_id": assessment_id,
        "title": assessment["title"],
        "due_date": assessment.get("due_date"),
        "weight_percent": assessment.get("weight_percent"),
        "type": assessment.get("type", "exam"),
        "readiness_score": readiness,
        "concept_scores": concept_scores,
        "days_until_due": _days_until(assessment.get("due_date")),
        "urgency": _classify_urgency(readiness),
        "trend": 0.0,  # TODO: compare to 7-day-ago mastery when historical data available
    }


async def get_all_assessment_readiness(
    supabase, user_id: str, course_id: str | None = None
) -> list[dict]:
    """Get readiness for all upcoming assessments, sorted by urgency."""
    query = (
        supabase.table("assessments")
        .select("id, course_id, due_date")
        .is_("student_score", "null")
    )
    if course_id:
        query = query.eq("course_id", course_id)

    assessments_result = query.execute()
    assessments = assessments_result.data or []

    results = []
    for a in assessments:
        # Skip past-due assessments — they are not "upcoming"
        if _is_past_due(a.get("due_date")):
            continue
        readiness = await get_assessment_readiness(supabase, user_id, a["id"])
        results.append(readiness)

    # Sort: closest due date first, then lowest readiness
    def sort_key(r: dict) -> tuple:
        days = r.get("days_until_due")
        if days is None:
            days = 9999
        return (days, r.get("readiness_score", 0))

    results.sort(key=sort_key)
    return results


async def get_course_readiness_summary(
    supabase, user_id: str, course_id: str
) -> dict:
    """Overall course readiness summary for home screen."""
    # Get course info
    course_result = (
        supabase.table("courses")
        .select("id, name")
        .eq("id", course_id)
        .execute()
    )
    course_name = course_result.data[0]["name"] if course_result.data else "Unknown"

    # Get mastery data
    try:
        mastery_result = supabase.rpc(
            "get_concept_mastery",
            {"p_course_id": course_id, "p_user_id": user_id},
        ).execute()
        mastery_data = mastery_result.data or []
    except Exception:
        mastery_data = []

    concepts_total = len(mastery_data)
    concepts_mastered = 0
    mastery_sum = 0.0
    for m in mastery_data:
        attempts = m.get("total_attempts", 0)
        accuracy = m.get("accuracy", 0.0)
        recent = m.get("recent_accuracy", 0.0)
        mastery = 0.0 if attempts == 0 else accuracy * 0.6 + recent * 0.4
        mastery_sum += mastery
        if mastery >= 0.8:
            concepts_mastered += 1

    overall = (mastery_sum / concepts_total * 100) if concepts_total > 0 else 0.0

    # Next upcoming assessment (must be in the future)
    assessments_result = (
        supabase.table("assessments")
        .select("id, title, due_date, weight_percent")
        .eq("course_id", course_id)
        .is_("student_score", "null")
        .order("due_date")
        .execute()
    )

    next_assessment = None
    for a in (assessments_result.data or []):
        if _is_past_due(a.get("due_date")):
            continue
        readiness = await get_assessment_readiness(supabase, user_id, a["id"])
        next_assessment = {
            "title": a["title"],
            "due_date": a.get("due_date"),
            "readiness": readiness["readiness_score"],
            "days_until": _days_until(a.get("due_date")),
        }
        break

    return {
        "course_id": course_id,
        "course_name": course_name,
        "overall_readiness": round(overall, 1),
        "next_assessment": next_assessment,
        "concepts_mastered": concepts_mastered,
        "concepts_total": concepts_total,
    }


async def get_grade_projection(
    supabase, user_id: str, course_id: str
) -> dict:
    """Project final grade based on current mastery + past scores."""
    # All assessments for the course
    assessments_result = (
        supabase.table("assessments")
        .select("id, title, type, weight_percent, student_score, due_date")
        .eq("course_id", course_id)
        .execute()
    )
    assessments = assessments_result.data or []

    completed_list = []
    upcoming_list = []
    weighted_total = 0.0
    total_weight = 0.0

    for a in assessments:
        weight = a.get("weight_percent") or 0.0
        if a.get("student_score") is not None:
            score = a["student_score"]
            completed_list.append({
                "title": a["title"],
                "score": score,
                "weight": weight,
            })
            weighted_total += score * weight
            total_weight += weight
        elif not _is_past_due(a.get("due_date")):
            # Only project scores for future assessments
            readiness = await get_assessment_readiness(supabase, user_id, a["id"])
            projected = readiness["readiness_score"] * 0.95
            upcoming_list.append({
                "title": a["title"],
                "projected_score": round(projected, 1),
                "weight": weight,
            })
            weighted_total += projected * weight
            total_weight += weight
        # Past-due with no score: excluded from projection (no data to use)

    projected_mid = weighted_total / total_weight if total_weight > 0 else 0.0

    # Range: +/- 5 percentage points
    projected_low = max(0.0, projected_mid - 5)
    projected_high = min(100.0, projected_mid + 5)

    return {
        "projected_grade_low": round(projected_low, 1),
        "projected_grade_high": round(projected_high, 1),
        "grade_letter": _grade_letter(projected_mid),
        "completed_assessments": completed_list,
        "upcoming_assessments": upcoming_list,
    }
