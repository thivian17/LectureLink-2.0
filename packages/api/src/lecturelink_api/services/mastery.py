"""
Bayesian Knowledge Tracing (BKT) mastery service.

BKT models P(student knows concept) as a hidden state updated
after each quiz answer using Bayes' theorem + learning transition.

Parameters per concept:
  p_mastery:  P(knows) -- the belief state [default: 0.3]
  p_transit:  P(learn | didn't know) [default: 0.1]
  p_guess:    P(correct | don't know) [default: 0.25]
  p_slip:     P(incorrect | know) [default: 0.1]
"""
import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)

# Default BKT parameters
DEFAULT_P_MASTERY = 0.3
DEFAULT_P_TRANSIT = 0.1
DEFAULT_P_GUESS = 0.25
DEFAULT_P_SLIP = 0.10


@dataclass
class BKTState:
    concept_id: str
    p_mastery: float
    p_transit: float
    p_guess: float
    p_slip: float
    total_attempts: int
    correct_attempts: int


def bkt_update(state: BKTState, is_correct: bool) -> BKTState:
    """
    Apply one BKT observation and return updated state.

    Uses standard BKT update equations:
    1. Compute P(observation | current mastery belief)
    2. Bayesian posterior update
    3. Apply learning transition
    """
    p = state.p_mastery
    p_t = state.p_transit
    p_g = state.p_guess
    p_s = state.p_slip

    if is_correct:
        likelihood = p * (1 - p_s) + (1 - p) * p_g
        if likelihood < 1e-10:
            likelihood = 1e-10
        posterior = (p * (1 - p_s)) / likelihood
    else:
        likelihood = p * p_s + (1 - p) * (1 - p_g)
        if likelihood < 1e-10:
            likelihood = 1e-10
        posterior = (p * p_s) / likelihood

    # Apply learning transition
    p_new = posterior + (1 - posterior) * p_t

    # Clamp to valid probability range
    p_new = max(0.01, min(0.99, p_new))

    return BKTState(
        concept_id=state.concept_id,
        p_mastery=p_new,
        p_transit=state.p_transit,
        p_guess=state.p_guess,
        p_slip=state.p_slip,
        total_attempts=state.total_attempts + 1,
        correct_attempts=state.correct_attempts + (1 if is_correct else 0),
    )


async def get_or_create_bkt_state(
    supabase,
    user_id: str,
    concept_id: str,
) -> BKTState:
    """Fetch existing BKT state or initialize with defaults."""
    try:
        result = (
            supabase.table("concept_bkt_state")
            .select("*")
            .eq("user_id", user_id)
            .eq("concept_id", concept_id)
            .single()
            .execute()
        )
        row = result.data
        return BKTState(
            concept_id=concept_id,
            p_mastery=row["p_mastery"],
            p_transit=row["p_transit"],
            p_guess=row["p_guess"],
            p_slip=row["p_slip"],
            total_attempts=row["total_attempts"],
            correct_attempts=row["correct_attempts"],
        )
    except Exception:
        # Not found -- return defaults
        return BKTState(
            concept_id=concept_id,
            p_mastery=DEFAULT_P_MASTERY,
            p_transit=DEFAULT_P_TRANSIT,
            p_guess=DEFAULT_P_GUESS,
            p_slip=DEFAULT_P_SLIP,
            total_attempts=0,
            correct_attempts=0,
        )


async def persist_bkt_state(
    supabase,
    user_id: str,
    state: BKTState,
) -> None:
    """Upsert BKT state into concept_bkt_state table."""
    try:
        supabase.table("concept_bkt_state").upsert(
            {
                "user_id": user_id,
                "concept_id": state.concept_id,
                "p_mastery": state.p_mastery,
                "p_transit": state.p_transit,
                "p_guess": state.p_guess,
                "p_slip": state.p_slip,
                "total_attempts": state.total_attempts,
                "correct_attempts": state.correct_attempts,
                "last_updated": "now()",
            },
            on_conflict="user_id,concept_id",
        ).execute()
    except Exception as e:
        logger.error(f"Failed to persist BKT state for concept {state.concept_id}: {e}")


async def update_mastery_from_quiz_result(
    supabase,
    user_id: str,
    concept_id: str,
    is_correct: bool,
) -> BKTState:
    """
    Main entry point: fetch state, apply BKT update, persist, return new state.
    Call this from quiz scoring after each question is evaluated.
    """
    state = await get_or_create_bkt_state(supabase, user_id, concept_id)
    updated = bkt_update(state, is_correct)
    await persist_bkt_state(supabase, user_id, updated)
    return updated


async def record_learning_event(
    supabase,
    user_id: str,
    course_id: str,
    concept_id: str,
    event_type: str,
    is_correct: bool | None = None,
    student_answer: str | None = None,
    time_ms: int | None = None,
    metadata: dict | None = None,
) -> None:
    """Record a learning event and update BKT mastery if applicable."""
    try:
        row = {
            "user_id": user_id,
            "course_id": course_id,
            "concept_id": concept_id,
            "event_type": event_type,
            "is_correct": is_correct,
            "student_answer": student_answer,
            "time_ms": time_ms,
            "metadata": metadata or {},
        }
        supabase.table("learning_events").insert(row).execute()
    except Exception as e:
        logger.error(f"Failed to record learning event: {e}")

    # Update BKT mastery if we have correctness info
    if is_correct is not None and concept_id:
        try:
            await update_mastery_from_quiz_result(
                supabase, user_id, concept_id, is_correct,
            )
        except Exception as e:
            logger.error(f"Failed to update BKT mastery after learning event: {e}")


def compute_mastery(accuracy: float, recent_accuracy: float, total_attempts: int) -> float:
    """Single source of truth for the weighted mastery formula.

    mastery = accuracy * 0.6 + recent_accuracy * 0.4  (0.0 if no attempts)
    """
    if total_attempts == 0:
        return 0.0
    return round(accuracy * 0.6 + recent_accuracy * 0.4, 4)


def mastery_tier(score: float) -> str:
    """Classify a mastery score into a human-readable tier label."""
    if score < 0.3:
        return "novice"
    if score < 0.6:
        return "developing"
    if score < 0.8:
        return "proficient"
    return "advanced"


async def get_course_mastery_summary(
    supabase,
    user_id: str,
    course_id: str,
) -> list[dict]:
    """
    Get BKT mastery summary for all concepts in a course.
    Returns list of {concept_id, concept_title, p_mastery, mastery_label, total_attempts}.
    Falls back to empty list on error (non-fatal).
    """
    try:
        result = supabase.rpc(
            "get_bkt_mastery_summary",
            {"p_user_id": user_id, "p_course_id": course_id},
        ).execute()
        return result.data or []
    except Exception as e:
        logger.error(f"Failed to fetch BKT mastery summary: {e}")
        return []
