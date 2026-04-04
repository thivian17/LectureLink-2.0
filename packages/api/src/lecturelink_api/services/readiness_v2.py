"""Readiness V2 service — 4-signal assessment readiness computation.

Signals:
  Coverage  (0.35) — fraction of linked concepts the student has interacted with
  Practice  (0.30) — average correctness across linked concepts
  Freshness (0.20) — recency-decay score across linked concepts
  Effort    (0.15) — completed study sessions targeting the assessment's concepts
"""

from __future__ import annotations

import logging
import math
from datetime import UTC, datetime, timedelta

from ..models.readiness_v2 import (
    EXAM_TYPES,
    AssessmentReadinessV2,
    CourseIntelligenceV2,
    ReadinessBreakdown,
    SuggestedAction,
    WeakConcept,
)

logger = logging.getLogger(__name__)

# Signal weights
COVERAGE_WEIGHT = 0.35
PRACTICE_WEIGHT = 0.30
FRESHNESS_WEIGHT = 0.20
EFFORT_WEIGHT = 0.15

# Freshness decay thresholds: (max_days_ago, score)
_FRESHNESS_THRESHOLDS = [
    (0, 1.0),
    (1, 0.9),
    (3, 0.8),
    (7, 0.5),
    (14, 0.3),
]
_FRESHNESS_FLOOR = 0.1  # 15+ days ago


def _freshness_for_days(days_ago: int) -> float:
    """Return freshness score for a given number of days since last interaction."""
    for max_days, score in _FRESHNESS_THRESHOLDS:
        if days_ago <= max_days:
            return score
    return _FRESHNESS_FLOOR


def _days_until(due_date: str | None) -> int | None:
    if not due_date:
        return None
    try:
        dt = datetime.fromisoformat(due_date)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=UTC)
        return (dt - datetime.now(UTC)).days
    except (ValueError, TypeError):
        return None


def classify_urgency(days_until: int | None, readiness: float) -> str:
    """Classify assessment urgency based on time remaining and readiness."""
    if days_until is None:
        return "low"
    if days_until <= 3 and readiness < 0.7:
        return "critical"
    if days_until <= 7 and readiness < 0.7:
        return "high"
    if days_until <= 14 and readiness < 0.6:
        return "medium"
    return "low"


# ---------------------------------------------------------------------------
# Internal signal helpers
# ---------------------------------------------------------------------------

def _compute_coverage(
    linked_concept_ids: set[str],
    interacted_concept_ids: set[str],
) -> float:
    """Fraction of linked concepts the student has interacted with."""
    if not linked_concept_ids:
        return 0.0
    return len(linked_concept_ids & interacted_concept_ids) / len(linked_concept_ids)


def _compute_practice(
    linked_concept_ids: set[str],
    concept_correct: dict[str, int],
    concept_total: dict[str, int],
) -> float:
    """Average correctness across linked concepts (0 for unattempted)."""
    if not linked_concept_ids:
        return 0.0
    total = 0.0
    for cid in linked_concept_ids:
        attempts = concept_total.get(cid, 0)
        if attempts > 0:
            total += concept_correct.get(cid, 0) / attempts
    return total / len(linked_concept_ids)


def _compute_freshness(
    linked_concept_ids: set[str],
    concept_last_interaction: dict[str, datetime],
    now: datetime,
) -> float:
    """Average recency-decay score across linked concepts."""
    if not linked_concept_ids:
        return 0.0
    total = 0.0
    for cid in linked_concept_ids:
        last = concept_last_interaction.get(cid)
        if last is None:
            # Never interacted → 0.0
            continue
        days_ago = max(0, (now - last).days)
        total += _freshness_for_days(days_ago)
    return total / len(linked_concept_ids)


def _compute_effort(
    completed_sessions: int,
    linked_concept_count: int,
) -> float:
    """Ratio of completed sessions to expected sessions, capped at 1.0."""
    expected = max(1, math.ceil(linked_concept_count / 3))
    return min(1.0, completed_sessions / expected)


def _weighted_readiness(breakdown: ReadinessBreakdown) -> float:
    """Compute final readiness as weighted sum, clamped to [0, 1]."""
    raw = (
        COVERAGE_WEIGHT * breakdown.coverage
        + PRACTICE_WEIGHT * breakdown.practice
        + FRESHNESS_WEIGHT * breakdown.freshness
        + EFFORT_WEIGHT * breakdown.effort
    )
    return max(0.0, min(1.0, raw))


# ---------------------------------------------------------------------------
# Suggested actions
# ---------------------------------------------------------------------------

def _generate_actions(
    breakdown: ReadinessBreakdown,
    course_id: str,
    assessment_id: str,
    urgency: str,
) -> list[SuggestedAction]:
    """Generate suggested actions based on which signal is lowest."""
    signals = [
        ("coverage", breakdown.coverage),
        ("practice", breakdown.practice),
        ("freshness", breakdown.freshness),
        ("effort", breakdown.effort),
    ]
    signals.sort(key=lambda s: s[1])
    actions: list[SuggestedAction] = []

    for signal_name, value in signals:
        if value >= 0.8:
            continue  # signal is healthy

        if signal_name == "coverage":
            actions.append(SuggestedAction(
                action_type="practice_test",
                title="Quiz Uncovered Material",
                description="Take a practice quiz on concepts you haven't studied yet.",
                estimated_minutes=10,
                target_course_id=course_id,
                target_assessment_id=assessment_id,
                urgency=urgency,
                expected_impact=f"+{int((1.0 - value) * COVERAGE_WEIGHT * 100)}% readiness",
            ))
        elif signal_name == "practice":
            actions.append(SuggestedAction(
                action_type="practice_test",
                title="Practice Test",
                description="Take a practice quiz on your weak concepts to improve accuracy.",
                estimated_minutes=15,
                target_course_id=course_id,
                target_assessment_id=assessment_id,
                urgency=urgency,
                expected_impact=f"+{int((1.0 - value) * PRACTICE_WEIGHT * 100)}% readiness",
            ))
        elif signal_name == "freshness":
            actions.append(SuggestedAction(
                action_type="flash_review",
                title="Flash Review",
                description="Quick review of concepts you haven't studied recently.",
                estimated_minutes=10,
                target_course_id=course_id,
                target_assessment_id=assessment_id,
                urgency=urgency,
                expected_impact=f"+{int((1.0 - value) * FRESHNESS_WEIGHT * 100)}% readiness",
            ))
        elif signal_name == "effort":
            actions.append(SuggestedAction(
                action_type="study_session",
                title="Study Session",
                description="Complete a focused study session targeting this assessment's concepts.",
                estimated_minutes=25,
                target_course_id=course_id,
                target_assessment_id=assessment_id,
                urgency=urgency,
                expected_impact=f"+{int((1.0 - value) * EFFORT_WEIGHT * 100)}% readiness",
            ))

    return actions


# ---------------------------------------------------------------------------
# DB data fetching helpers
# ---------------------------------------------------------------------------

async def _fetch_linked_concepts(supabase, assessment_id: str, course_id: str = "", user_id: str = "") -> list[dict]:
    """Fetch relevant concepts for an assessment.

    Uses the assessment_prep service for intelligent concept identification
    when course_id and user_id are provided. Falls back to
    concept_assessment_links for backwards compatibility.
    """
    if course_id and user_id:
        try:
            from .assessment_prep import get_assessment_concepts
            concepts = await get_assessment_concepts(
                supabase, assessment_id, course_id, user_id,
            )
            return [{"concept_id": c["concept_id"]} for c in concepts]
        except Exception:
            logger.warning(
                "assessment_prep failed for %s, falling back to links",
                assessment_id, exc_info=True,
            )

    try:
        result = (
            supabase.table("concept_assessment_links")
            .select("concept_id")
            .eq("assessment_id", assessment_id)
            .execute()
        )
        return result.data or []
    except Exception:
        logger.warning("Failed to fetch concept_assessment_links for %s", assessment_id, exc_info=True)
        return []


async def _fetch_concept_titles(supabase, concept_ids: list[str]) -> dict[str, str]:
    """Fetch concept titles by IDs. Returns {concept_id: title}."""
    if not concept_ids:
        return {}
    try:
        result = (
            supabase.table("concepts")
            .select("id, title")
            .in_("id", concept_ids)
            .execute()
        )
        return {r["id"]: r.get("title", "Unknown") for r in (result.data or [])}
    except Exception:
        logger.warning("Failed to fetch concept titles", exc_info=True)
        return {}


async def _fetch_learning_events(
    supabase, user_id: str, concept_ids: list[str],
) -> list[dict]:
    """Fetch learning_events for a user filtered to specific concepts."""
    if not concept_ids:
        return []
    try:
        result = (
            supabase.table("learning_events")
            .select("concept_id, is_correct, created_at")
            .eq("user_id", user_id)
            .in_("concept_id", concept_ids)
            .execute()
        )
        return result.data or []
    except Exception:
        logger.warning("Failed to fetch learning_events", exc_info=True)
        return []


async def _fetch_quiz_attempts(
    supabase, user_id: str, concept_ids: list[str],
) -> list[dict]:
    """Fetch quiz_attempts for a user filtered to specific concepts."""
    if not concept_ids:
        return []
    try:
        result = (
            supabase.table("quiz_attempts")
            .select("concept_id, is_correct, created_at")
            .eq("user_id", user_id)
            .in_("concept_id", concept_ids)
            .execute()
        )
        return result.data or []
    except Exception:
        logger.warning("Failed to fetch quiz_attempts", exc_info=True)
        return []


async def _fetch_completed_sessions(
    supabase, user_id: str, course_id: str, concept_ids: set[str],
) -> int:
    """Count completed learn + tutor sessions in last 14 days for relevant concepts."""
    cutoff = (datetime.now(UTC) - timedelta(days=14)).isoformat()
    count = 0

    # learn_sessions
    try:
        result = (
            supabase.table("learn_sessions")
            .select("id, concepts_planned")
            .eq("user_id", user_id)
            .eq("course_id", course_id)
            .eq("status", "completed")
            .gte("completed_at", cutoff)
            .execute()
        )
        for session in (result.data or []):
            planned = session.get("concepts_planned") or []
            session_concepts = set()
            for c in planned:
                if isinstance(c, dict):
                    session_concepts.add(c.get("concept_id", c.get("id", "")))
                elif isinstance(c, str):
                    session_concepts.add(c)
            if session_concepts & concept_ids:
                count += 1
    except Exception:
        logger.warning("Failed to fetch learn_sessions for effort", exc_info=True)

    # tutor_sessions
    try:
        result = (
            supabase.table("tutor_sessions")
            .select("id, concept_id")
            .eq("user_id", user_id)
            .eq("course_id", course_id)
            .eq("status", "completed")
            .gte("completed_at", cutoff)
            .execute()
        )
        for session in (result.data or []):
            if session.get("concept_id") in concept_ids:
                count += 1
    except Exception:
        logger.warning("Failed to fetch tutor_sessions for effort", exc_info=True)

    return count


# ---------------------------------------------------------------------------
# Main public API
# ---------------------------------------------------------------------------

async def compute_assessment_readiness(
    supabase, user_id: str, assessment_id: str,
) -> AssessmentReadinessV2:
    """Compute full readiness report for one assessment."""
    # 1. Fetch assessment metadata
    try:
        assessment_result = (
            supabase.table("assessments")
            .select("id, title, due_date, type, course_id")
            .eq("id", assessment_id)
            .execute()
        )
        assessment = (assessment_result.data or [{}])[0]
    except Exception:
        logger.warning("Failed to fetch assessment %s", assessment_id, exc_info=True)
        assessment = {}

    course_id = assessment.get("course_id", "")
    title = assessment.get("title", "Unknown Assessment")
    assessment_type = assessment.get("type", "exam")
    due_date = assessment.get("due_date")
    days_until = _days_until(due_date)

    # Fetch course name
    course_name: str | None = None
    try:
        course_result = (
            supabase.table("courses")
            .select("name")
            .eq("id", course_id)
            .execute()
        )
        if course_result.data:
            course_name = course_result.data[0].get("name")
    except Exception:
        pass

    # 2. Fetch linked concept IDs
    links = await _fetch_linked_concepts(supabase, assessment_id, course_id, user_id)
    linked_ids = {link["concept_id"] for link in links}
    concept_id_list = list(linked_ids)

    # Edge case: no linked concepts
    if not linked_ids:
        breakdown = ReadinessBreakdown(coverage=0.0, practice=0.0, freshness=0.0, effort=0.0)
        return AssessmentReadinessV2(
            assessment_id=assessment_id,
            title=title,
            course_id=course_id,
            course_name=course_name,
            assessment_type=assessment_type,
            due_date=due_date,
            days_until_due=days_until,
            readiness=0.0,
            breakdown=breakdown,
            weak_concepts=[],
            suggested_actions=[],
            urgency=classify_urgency(days_until, 0.0),
            concept_count=0,
            covered_count=0,
        )

    # 3. Fetch interaction data
    learning_events = await _fetch_learning_events(supabase, user_id, concept_id_list)
    quiz_attempts = await _fetch_quiz_attempts(supabase, user_id, concept_id_list)

    # Build per-concept aggregates
    interacted: set[str] = set()
    concept_correct: dict[str, int] = {}
    concept_total: dict[str, int] = {}
    concept_last: dict[str, datetime] = {}
    now = datetime.now(UTC)

    for event in learning_events:
        cid = event.get("concept_id", "")
        if cid not in linked_ids:
            continue
        interacted.add(cid)
        if event.get("is_correct") is not None:
            concept_total[cid] = concept_total.get(cid, 0) + 1
            if event["is_correct"]:
                concept_correct[cid] = concept_correct.get(cid, 0) + 1
        created = event.get("created_at")
        if created:
            try:
                dt = datetime.fromisoformat(str(created))
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=UTC)
                if cid not in concept_last or dt > concept_last[cid]:
                    concept_last[cid] = dt
            except (ValueError, TypeError):
                pass

    for attempt in quiz_attempts:
        cid = attempt.get("concept_id", "")
        if cid not in linked_ids:
            continue
        interacted.add(cid)
        if attempt.get("is_correct") is not None:
            concept_total[cid] = concept_total.get(cid, 0) + 1
            if attempt["is_correct"]:
                concept_correct[cid] = concept_correct.get(cid, 0) + 1
        created = attempt.get("created_at")
        if created:
            try:
                dt = datetime.fromisoformat(str(created))
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=UTC)
                if cid not in concept_last or dt > concept_last[cid]:
                    concept_last[cid] = dt
            except (ValueError, TypeError):
                pass

    # 4. Compute signals
    coverage = _compute_coverage(linked_ids, interacted)
    practice = _compute_practice(linked_ids, concept_correct, concept_total)
    freshness = _compute_freshness(linked_ids, concept_last, now)
    completed_sessions = await _fetch_completed_sessions(supabase, user_id, course_id, linked_ids)
    effort = _compute_effort(completed_sessions, len(linked_ids))

    breakdown = ReadinessBreakdown(
        coverage=round(coverage, 4),
        practice=round(practice, 4),
        freshness=round(freshness, 4),
        effort=round(effort, 4),
    )
    readiness = round(_weighted_readiness(breakdown), 4)
    urgency = classify_urgency(days_until, readiness)

    # 5. Weak concepts (top 5 by combined score ascending)
    concept_titles = await _fetch_concept_titles(supabase, concept_id_list)
    weak_concepts: list[WeakConcept] = []
    for cid in linked_ids:
        c_coverage = cid in interacted
        c_total = concept_total.get(cid, 0)
        c_practice = (concept_correct.get(cid, 0) / c_total) if c_total > 0 else 0.0
        last = concept_last.get(cid)
        if last is None:
            c_freshness = 0.0
        else:
            c_freshness = _freshness_for_days(max(0, (now - last).days))
        combined = (
            COVERAGE_WEIGHT * (1.0 if c_coverage else 0.0)
            + PRACTICE_WEIGHT * c_practice
            + FRESHNESS_WEIGHT * c_freshness
            + EFFORT_WEIGHT * effort  # effort is assessment-level, same for all concepts
        )
        weak_concepts.append(WeakConcept(
            concept_id=cid,
            title=concept_titles.get(cid, "Unknown"),
            coverage=c_coverage,
            practice_score=round(c_practice, 4),
            freshness_score=round(c_freshness, 4),
            combined_score=round(combined, 4),
        ))

    weak_concepts.sort(key=lambda w: w.combined_score)
    weak_concepts = weak_concepts[:5]

    # 6. Suggested actions
    actions = _generate_actions(breakdown, course_id, assessment_id, urgency)

    return AssessmentReadinessV2(
        assessment_id=assessment_id,
        title=title,
        course_id=course_id,
        course_name=course_name,
        assessment_type=assessment_type,
        due_date=due_date,
        days_until_due=days_until,
        readiness=readiness,
        breakdown=breakdown,
        weak_concepts=weak_concepts,
        suggested_actions=actions,
        urgency=urgency,
        concept_count=len(linked_ids),
        covered_count=len(linked_ids & interacted),
    )


async def compute_course_readiness(
    supabase, user_id: str, course_id: str,
) -> CourseIntelligenceV2:
    """Course-level readiness aggregated across exam-type assessments."""
    # Fetch course info
    course_name = "Unknown"
    course_code: str | None = None
    try:
        course_result = (
            supabase.table("courses")
            .select("name, code")
            .eq("id", course_id)
            .execute()
        )
        if course_result.data:
            course_name = course_result.data[0].get("name", "Unknown")
            course_code = course_result.data[0].get("code")
    except Exception:
        pass

    # Fetch assessments
    try:
        assessments_result = (
            supabase.table("assessments")
            .select("id, title, type, due_date")
            .eq("course_id", course_id)
            .execute()
        )
        assessments = assessments_result.data or []
    except Exception:
        logger.warning("Failed to fetch assessments for course %s", course_id, exc_info=True)
        assessments = []

    # Filter to exam types
    exam_assessments = [
        a for a in assessments
        if (a.get("type", "").lower() in EXAM_TYPES)
    ]

    if not exam_assessments:
        return CourseIntelligenceV2(
            course_id=course_id,
            course_name=course_name,
            course_code=course_code,
            readiness=0.0,
            risk="low",
            assessment_count=0,
        )

    # Compute readiness for each
    readiness_scores: list[float] = []
    next_assessment_data: dict | None = None
    closest_days: int | None = None
    recommended_action: SuggestedAction | None = None
    highest_urgency_priority = -1
    urgency_order = {"critical": 3, "high": 2, "medium": 1, "low": 0}

    for a in exam_assessments:
        result = await compute_assessment_readiness(supabase, user_id, a["id"])
        readiness_scores.append(result.readiness)

        # Track next upcoming assessment
        if result.days_until_due is not None and result.days_until_due >= 0:
            if closest_days is None or result.days_until_due < closest_days:
                closest_days = result.days_until_due
                next_assessment_data = {
                    "title": result.title,
                    "type": result.assessment_type,
                    "due_date": result.due_date,
                    "days_until": result.days_until_due,
                    "readiness": result.readiness,
                }

        # Track highest-urgency action
        u_priority = urgency_order.get(result.urgency, 0)
        if u_priority > highest_urgency_priority and result.suggested_actions:
            highest_urgency_priority = u_priority
            recommended_action = result.suggested_actions[0]

    avg_readiness = sum(readiness_scores) / len(readiness_scores)

    # Risk classification
    if avg_readiness < 0.4:
        risk = "high"
    elif avg_readiness < 0.7:
        risk = "medium"
    else:
        risk = "low"

    return CourseIntelligenceV2(
        course_id=course_id,
        course_name=course_name,
        course_code=course_code,
        readiness=round(avg_readiness, 4),
        risk=risk,
        next_assessment=next_assessment_data,
        recommended_action=recommended_action,
        assessment_count=len(exam_assessments),
    )


async def get_all_course_readiness(
    supabase, user_id: str,
) -> list[CourseIntelligenceV2]:
    """Readiness for all courses the user is enrolled in, sorted by risk."""
    try:
        courses_result = (
            supabase.table("courses")
            .select("id")
            .eq("user_id", user_id)
            .execute()
        )
        courses = courses_result.data or []
    except Exception:
        logger.warning("Failed to fetch courses for user %s", user_id, exc_info=True)
        return []

    results: list[CourseIntelligenceV2] = []
    for course in courses:
        result = await compute_course_readiness(supabase, user_id, course["id"])
        results.append(result)

    risk_order = {"high": 0, "medium": 1, "low": 2}
    results.sort(key=lambda r: risk_order.get(r.risk, 2))
    return results
