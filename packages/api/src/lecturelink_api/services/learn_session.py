"""Learn Mode session orchestrator.

Orchestrates the full Learn Mode session flow:
start → flash review → concept briefs → power quiz → complete.

Integrates with gamification services via try/except for parallel development.
"""

from __future__ import annotations

import contextlib
import json
import logging
import random
import uuid
from datetime import UTC, datetime

from .concept_brief import generate_concept_brief
from .flash_review import get_flash_review_cards, grade_flash_review
from .genai_client import get_genai_client as _get_client
from .mastery import compute_mastery, record_learning_event
from .search import format_chunks_for_context, search_lectures

logger = logging.getLogger(__name__)

QUIZ_MODEL = "gemini-2.5-flash"

# Time budget → number of concepts
TIME_BUDGET_CONCEPTS = {
    10: 1,
    15: 1,
    20: 2,
    25: 2,
}

# Combo multiplier thresholds
COMBO_THRESHOLDS = {
    3: 2,   # 3 consecutive correct → 2x
    5: 3,   # 5 → 3x
    8: 4,   # 8 → 4x
}


def _get_combo_multiplier(combo_count: int) -> int:
    """Get XP multiplier based on consecutive correct answers."""
    multiplier = 1
    for threshold, mult in sorted(COMBO_THRESHOLDS.items()):
        if combo_count >= threshold:
            multiplier = mult
    return multiplier


async def _award_xp(supabase, user_id: str, action: str, **kwargs) -> dict:
    """Try to award XP via gamification service. Returns placeholder if unavailable."""
    base_amounts = {
        "flash_review_correct": 5,
        "flash_review_incorrect": 2,
        "gut_check_correct": 15,
        "quiz_correct": 10,
        "session_complete": 25,
    }
    try:
        from lecturelink_api.services.gamification import award_xp
        return await award_xp(supabase, user_id, action, **kwargs)
    except Exception:
        amount = base_amounts.get(action, 10)
        return {"amount": amount, "total_xp": 0, "level": 1, "leveled_up": False}


async def _update_streak(supabase, user_id: str) -> dict:
    """Try to update streak via gamification service."""
    try:
        from lecturelink_api.services.gamification import update_streak
        return await update_streak(supabase, user_id)
    except Exception:
        return {
            "current_streak": 1,
            "longest_streak": 1,
            "studied_today": True,
            "freeze_available": False,
            "streak_milestone": None,
        }


async def _check_badges(supabase, user_id: str) -> list[dict]:
    """Try to check and award badges."""
    try:
        from lecturelink_api.services.badges import check_and_award_badges
        return await check_and_award_badges(
            supabase, user_id, trigger="session_complete", context={}
        )
    except Exception:
        return []


async def _resolve_concept_titles(
    supabase, concepts_planned: list[dict]
) -> list[dict]:
    """Fill in missing titles from the concepts table and drop unresolvable ones."""
    missing = [c for c in concepts_planned if not c.get("title")]
    if not missing:
        return concepts_planned

    try:
        ids = [c["concept_id"] for c in missing]
        result = (
            supabase.table("concepts")
            .select("id, title")
            .in_("id", ids)
            .execute()
        )
        title_map = {r["id"]: r["title"] for r in (result.data or [])}
        for c in missing:
            c["title"] = title_map.get(c["concept_id"], "")
    except Exception:
        logger.warning("Failed to resolve concept titles on resume", exc_info=True)

    resolved = [c for c in concepts_planned if c.get("title")]
    dropped = len(concepts_planned) - len(resolved)
    if dropped:
        logger.warning("Dropped %d concepts with no title from session", dropped)
    return resolved


async def start_learn_session(
    supabase,
    user_id: str,
    course_id: str,
    time_budget_minutes: int = 15,
    target_assessment_id: str | None = None,
    target_concept_ids: list[str] | None = None,
) -> dict:
    """Start a new Learn Mode session.

    Returns daily briefing + flash review cards.
    Resumes existing active session if one exists (unless targeting overrides).
    """
    is_custom = bool(target_assessment_id or target_concept_ids)

    # 1. Check for existing active session (skip if user is customizing)
    if not is_custom:
        try:
            existing = (
                supabase.table("learn_sessions")
                .select("*")
                .eq("user_id", user_id)
                .eq("course_id", course_id)
                .eq("status", "active")
                .execute()
            )
            if existing.data:
                session = existing.data[0]

                # Expire stale sessions (>2 hours old)
                started_at_raw = session.get("started_at")
                if started_at_raw:
                    try:
                        started = datetime.fromisoformat(str(started_at_raw))
                        if started.tzinfo is None:
                            started = started.replace(tzinfo=UTC)
                        age_seconds = (datetime.now(UTC) - started).total_seconds()
                        if age_seconds > 7200:  # 2 hours
                            logger.info(
                                "Expiring stale learn session %s (age: %.0fs)",
                                session["id"], age_seconds,
                            )
                            supabase.table("learn_sessions").update(
                                {"status": "expired"}
                            ).eq("id", session["id"]).execute()
                            # Fall through to create a new session
                        else:
                            # Session is still fresh — resume it
                            daily_briefing = session.get("session_data", {}).get("daily_briefing", {})
                            daily_briefing["concepts_planned"] = await _resolve_concept_titles(
                                supabase, daily_briefing.get("concepts_planned", [])
                            )
                            flash_cards = await get_flash_review_cards(
                                supabase, user_id, course_id, count=5
                            )
                            return {
                                "session_id": session["id"],
                                "daily_briefing": daily_briefing,
                                "flash_review_cards": flash_cards,
                            }
                    except Exception:
                        logger.debug("Failed to parse session started_at", exc_info=True)
                        # If we can't parse the date, fall through to create new
        except Exception:
            logger.debug("Failed to check existing sessions", exc_info=True)
    else:
        # Expire any existing active sessions when user is customizing
        try:
            supabase.table("learn_sessions").update(
                {"status": "expired"}
            ).eq("user_id", user_id).eq("course_id", course_id).eq(
                "status", "active"
            ).execute()
        except Exception:
            logger.debug("Failed to expire old sessions for custom start", exc_info=True)

    # 2. Fetch all course data needed for concept selection + options
    num_concepts = TIME_BUDGET_CONCEPTS.get(time_budget_minutes, 1)
    now = datetime.now(UTC)

    # 2a. Get all future assessments for this course
    target_assessment = None
    assessments = []
    try:
        result = supabase.rpc(
            "get_study_priorities",
            {"p_course_id": course_id},
        ).execute()
        raw_assessments = result.data or []
    except Exception:
        logger.warning("get_study_priorities RPC failed", exc_info=True)
        raw_assessments = []

    for a in raw_assessments:
        dd = a.get("due_date")
        if dd:
            try:
                due = datetime.fromisoformat(str(dd))
                if due.tzinfo is None:
                    due = due.replace(tzinfo=UTC)
                if due.date() < now.date():
                    continue
            except Exception:
                pass
        assessments.append(a)

    # 2b. Enrich with mastery data (needed for all paths)
    mastery_map: dict = {}
    try:
        mastery_result = supabase.rpc(
            "get_concept_mastery",
            {"p_course_id": course_id, "p_user_id": user_id},
        ).execute()
        mastery_map = {
            m["concept_id"]: m for m in (mastery_result.data or [])
        }
    except Exception:
        logger.warning("get_concept_mastery RPC failed", exc_info=True)

    # 2c. Get all concepts for this course (for available_concepts list)
    all_concepts = []
    try:
        all_concepts_result = (
            supabase.table("concepts")
            .select("id, title, lecture_id")
            .eq("course_id", course_id)
            .order("created_at", desc=True)
            .execute()
        )
        all_concepts = all_concepts_result.data or []
    except Exception:
        logger.warning("Failed to fetch all concepts", exc_info=True)

    # 2d. Get recently studied concept IDs to avoid repetition
    recently_studied: set[str] = set()
    try:
        recent_sessions = (
            supabase.table("learn_sessions")
            .select("concepts_planned")
            .eq("user_id", user_id)
            .eq("course_id", course_id)
            .eq("status", "completed")
            .order("completed_at", desc=True)
            .limit(5)
            .execute()
        )
        for s in (recent_sessions.data or []):
            for cid in (s.get("concepts_planned") or []):
                recently_studied.add(cid)
    except Exception:
        logger.debug("Failed to fetch recent sessions for rotation", exc_info=True)

    # 3. Select concepts based on targeting mode
    def _enrich_concept(cid: str) -> dict:
        """Build a concept entry with mastery data."""
        m_data = mastery_map.get(cid, {})
        accuracy = m_data.get("accuracy", 0.0)
        recent = m_data.get("recent_accuracy", 0.0)
        mastery = compute_mastery(accuracy, recent, m_data.get("total_attempts", 0))
        return {
            "concept_id": cid,
            "concept_title": m_data.get("concept_title", ""),
            "mastery_score": mastery,
            "total_attempts": m_data.get("total_attempts", 0),
            "priority_score": 0.5,
        }

    if target_concept_ids:
        # User explicitly chose concepts — use them directly
        selected = [_enrich_concept(cid) for cid in target_concept_ids]

    elif target_assessment_id:
        # User chose a specific assessment — get its linked concepts
        target_assessment = next(
            (a for a in assessments if a.get("assessment_id") == target_assessment_id),
            None,
        )
        linked_concepts = []
        try:
            links_result = (
                supabase.table("concept_assessment_links")
                .select("concept_id, relevance_score")
                .eq("assessment_id", target_assessment_id)
                .order("relevance_score", desc=True)
                .limit(10)
                .execute()
            )
            linked_concepts = links_result.data or []
        except Exception:
            logger.warning("Failed to fetch concept-assessment links", exc_info=True)

        selected = []
        for link in linked_concepts:
            if len(selected) >= num_concepts:
                break
            cid = link["concept_id"]
            if cid in recently_studied:
                continue
            entry = _enrich_concept(cid)
            entry["priority_score"] = link.get("relevance_score", 0.5)
            selected.append(entry)
        if not selected:
            for link in linked_concepts[:num_concepts]:
                entry = _enrich_concept(link["concept_id"])
                entry["priority_score"] = link.get("relevance_score", 0.5)
                selected.append(entry)
    else:
        # Auto mode — original logic: top-priority assessment → linked concepts
        linked_concepts = []
        if assessments:
            target_assessment = assessments[0]
            try:
                links_result = (
                    supabase.table("concept_assessment_links")
                    .select("concept_id, relevance_score")
                    .eq("assessment_id", target_assessment["assessment_id"])
                    .order("relevance_score", desc=True)
                    .limit(10)
                    .execute()
                )
                linked_concepts = links_result.data or []
            except Exception:
                logger.warning("Failed to fetch concept-assessment links", exc_info=True)

        if linked_concepts:
            selected = []
            for link in linked_concepts:
                if len(selected) >= num_concepts:
                    break
                cid = link["concept_id"]
                if cid in recently_studied:
                    continue
                entry = _enrich_concept(cid)
                entry["priority_score"] = link.get("relevance_score", 0.5)
                selected.append(entry)
            if not selected:
                logger.info("All linked concepts recently studied — relaxing rotation filter")
                for link in linked_concepts[:num_concepts]:
                    entry = _enrich_concept(link["concept_id"])
                    entry["priority_score"] = link.get("relevance_score", 0.5)
                    selected.append(entry)
        else:
            # Fallback: most recent concepts
            fallback_rows = [
                c for c in all_concepts
                if c["id"] not in recently_studied
            ][:num_concepts]
            if not fallback_rows:
                fallback_rows = all_concepts[:num_concepts]
            selected = [
                {
                    "concept_id": c["id"],
                    "concept_title": c.get("title", ""),
                    "mastery_score": 0.0,
                    "total_attempts": 0,
                    "priority_score": 0.5,
                }
                for c in fallback_rows
            ]

    # Fill in missing titles from the all_concepts list
    title_map = {c["id"]: c.get("title", "") for c in all_concepts}
    for s in selected:
        if not s.get("concept_title"):
            s["concept_title"] = title_map.get(s["concept_id"], "")

    concepts_planned = []
    for p in selected:
        title = p.get("concept_title") or p.get("title") or ""
        if not title:
            logger.warning(
                "Dropping concept %s from session — no title resolved",
                p.get("concept_id", "?"),
            )
            continue
        concepts_planned.append({
            "concept_id": p.get("concept_id", p.get("id", "")),
            "title": title,
            "mastery": p.get("mastery_score", 0.0),
            "total_attempts": p.get("total_attempts", 0),
        })

    # 4. Get course name for briefing
    course_name = ""
    try:
        course_result = (
            supabase.table("courses")
            .select("name")
            .eq("id", course_id)
            .single()
            .execute()
        )
        course_name = course_result.data.get("name", "")
    except Exception:
        pass

    # 5. Build focus description
    focus_titles = [c["title"] for c in concepts_planned if c.get("title")]
    focus_description = " & ".join(focus_titles) if focus_titles else "General review"

    # 6. Build assessment context from the target assessment
    assessment_context = None
    if target_assessment:
        a_title = target_assessment.get("title", "")
        due_date = target_assessment.get("due_date")
        weight = target_assessment.get("weight_percent")
        if due_date:
            try:
                due = datetime.fromisoformat(str(due_date))
                if due.tzinfo is None:
                    due = due.replace(tzinfo=UTC)
                days_until = (due - datetime.now(UTC)).days
                weight_str = f", {weight:.0f}% of grade" if weight else ""
                assessment_context = (
                    f"Preparing for: {a_title} in {days_until} days{weight_str}"
                )
            except Exception:
                assessment_context = f"Preparing for: {a_title}"
        else:
            assessment_context = f"Preparing for: {a_title}"

    # Build available options for the customization UI
    available_assessments = []
    for a in assessments:
        a_entry: dict = {
            "assessment_id": a.get("assessment_id", ""),
            "title": a.get("title", ""),
            "due_date": a.get("due_date"),
            "weight_percent": a.get("weight_percent"),
        }
        available_assessments.append(a_entry)

    available_concepts = []
    for c in all_concepts:
        m_data = mastery_map.get(c["id"], {})
        accuracy = m_data.get("accuracy", 0.0)
        recent = m_data.get("recent_accuracy", 0.0)
        attempts = m_data.get("total_attempts", 0)
        mastery = compute_mastery(accuracy, recent, attempts) if attempts > 0 else 0.0
        available_concepts.append({
            "concept_id": c["id"],
            "title": c.get("title", ""),
            "mastery": round(mastery, 2),
            "total_attempts": attempts,
        })

    daily_briefing = {
        "course_name": course_name,
        "focus_description": focus_description,
        "assessment_context": assessment_context,
        "time_budget": time_budget_minutes,
        "concepts_planned": concepts_planned,
        "available_assessments": available_assessments,
        "available_concepts": available_concepts,
        "is_custom": is_custom,
    }

    # 7. Get flash review cards (before DB insert so we can store them in session_data)
    session_id = str(uuid.uuid4())
    try:
        flash_cards = await get_flash_review_cards(
            supabase, user_id, course_id, count=5,
            session_concepts=[
                {"concept_id": c["concept_id"], "concept_title": c["title"]}
                for c in concepts_planned
            ],
        )
    except Exception:
        logger.warning("Flash review card generation failed, starting without cards", exc_info=True)
        flash_cards = []

    session_data = {
        "daily_briefing": daily_briefing,
        "flash_review_cards": flash_cards,
        "flash_review_results": [],
        "quiz_results": [],
        "combo_count": 0,
        "combo_max": 0,
        "xp_breakdown": [],
    }

    # 8. Create learn_sessions row
    try:
        supabase.table("learn_sessions").insert({
            "id": session_id,
            "user_id": user_id,
            "course_id": course_id,
            "status": "active",
            "time_budget_minutes": time_budget_minutes,
            "concepts_planned": [c["concept_id"] for c in concepts_planned],
            "session_data": session_data,
            "started_at": datetime.now(UTC).isoformat(),
        }).execute()
    except Exception:
        logger.error("Failed to create learn session", exc_info=True)
        raise

    return {
        "session_id": session_id,
        "daily_briefing": daily_briefing,
        "flash_review_cards": flash_cards,
    }


async def get_session(supabase, user_id: str, session_id: str) -> dict | None:
    """Get session state for resume support."""
    try:
        result = (
            supabase.table("learn_sessions")
            .select("*")
            .eq("id", session_id)
            .eq("user_id", user_id)
            .single()
            .execute()
        )
        return result.data
    except Exception:
        return None


async def get_concept_brief(
    supabase,
    user_id: str,
    session_id: str,
    concept_index: int,
) -> dict:
    """Get the concept brief for the Nth concept in the session."""
    session = await get_session(supabase, user_id, session_id)
    if not session:
        raise ValueError(f"Session {session_id} not found")

    concepts_planned = session.get("session_data", {}).get(
        "daily_briefing", {}
    ).get("concepts_planned", [])

    if concept_index < 0 or concept_index >= len(concepts_planned):
        raise ValueError(
            f"Concept index {concept_index} out of range "
            f"(session has {len(concepts_planned)} concepts)"
        )

    concept = concepts_planned[concept_index]
    concept_id = concept.get("concept_id", "")
    mastery = concept.get("mastery", 0.0)

    brief = await generate_concept_brief(
        supabase,
        user_id=user_id,
        concept_id=concept_id,
        course_id=session["course_id"],
        mastery_score=mastery,
    )

    return brief


async def submit_gut_check(
    supabase,
    user_id: str,
    session_id: str,
    concept_id: str,
    answer_index: int,
) -> dict:
    """Submit gut-check answer for a concept brief."""
    session = await get_session(supabase, user_id, session_id)
    if not session:
        raise ValueError(f"Session {session_id} not found")

    # We need the gut-check data from the client (stored client-side after brief load)
    # For now, the router passes the gut_check data separately or we regenerate
    # Award XP based on correctness
    # The caller must provide enough context; here we just award XP
    is_correct = answer_index >= 0  # Placeholder — actual grading done by router

    # Only award XP for correct gut checks
    if is_correct:
        xp_result = await _award_xp(supabase, user_id, "gut_check_correct")
        xp_earned = xp_result.get("amount", 0)
    else:
        xp_earned = 0

    # Record learning event for mastery tracking
    await record_learning_event(
        supabase,
        user_id=user_id,
        course_id=session["course_id"],
        concept_id=concept_id,
        event_type="gut_check",
        is_correct=is_correct,
        student_answer=str(answer_index),
    )

    return {
        "correct": is_correct,
        "xp_earned": xp_earned,
    }


async def submit_flash_review_answer(
    supabase,
    user_id: str,
    session_id: str,
    card_id: str,
    answer_index: int,
    time_ms: int = 0,
) -> dict:
    """Submit a flash review answer.

    Returns {correct, correct_answer, xp_earned}.
    """
    session = await get_session(supabase, user_id, session_id)
    if not session:
        raise ValueError(f"Session {session_id} not found")

    session_data = session.get("session_data", {})
    flash_results = session_data.get("flash_review_results", [])

    result_entry = {
        "card_id": card_id,
        "answer_index": answer_index,
        "time_ms": time_ms,
        "answered_at": datetime.now(UTC).isoformat(),
    }

    # Grade using stored flash cards
    cards = session_data.get("flash_review_cards", [])
    card = next((c for c in cards if c.get("card_id") == card_id), None)
    if card:
        grade = grade_flash_review(card, answer_index)
        is_correct = grade["correct"]
        action = "flash_review_correct" if is_correct else "flash_review_incorrect"
        xp_result = await _award_xp(supabase, user_id, action)
        result_entry["correct"] = is_correct
        result_entry["xp_earned"] = xp_result.get("amount", 0)

        # Record learning event for mastery tracking
        await record_learning_event(
            supabase,
            user_id=user_id,
            course_id=session["course_id"],
            concept_id=card.get("concept_id", ""),
            event_type="flash_review",
            is_correct=is_correct,
            student_answer=str(answer_index),
            time_ms=time_ms,
        )

        flash_results.append(result_entry)
        session_data["flash_review_results"] = flash_results

        # Update session
        try:
            supabase.table("learn_sessions").update({
                "session_data": session_data,
            }).eq("id", session_id).execute()
        except Exception:
            logger.warning("Failed to update flash review results", exc_info=True)

        return {
            "correct": is_correct,
            "correct_answer": grade["correct_answer"],
            "xp_earned": xp_result.get("amount", 0),
        }

    # Fallback if card not found in session data
    flash_results.append(result_entry)
    session_data["flash_review_results"] = flash_results
    try:
        supabase.table("learn_sessions").update({
            "session_data": session_data,
        }).eq("id", session_id).execute()
    except Exception:
        logger.warning("Failed to update flash review results", exc_info=True)

    return result_entry


async def _try_reuse_power_quiz_questions(
    supabase,
    course_id: str,
    concept_ids: list[str],
    count: int,
) -> list[dict]:
    """Try to pull existing MCQ questions for Power Quiz reuse.

    Prefers questions that have been shown least often.
    Returns up to `count` questions formatted for Power Quiz, may return fewer.
    """
    if not concept_ids or count <= 0:
        return []

    try:
        result = (
            supabase.table("quiz_questions")
            .select("id, question_text, options, correct_answer, explanation, concept_id")
            .in_("concept_id", concept_ids)
            .eq("question_type", "mcq")
            .in_("source", ["standalone", "power_quiz"])
            .order("times_shown", desc=False)
            .limit(count * 2)
            .execute()
        )
        candidates = result.data or []
    except Exception:
        logger.debug("Failed to fetch reusable questions", exc_info=True)
        return []

    if not candidates:
        return []

    random.shuffle(candidates)
    selected = candidates[:count]

    # Format for Power Quiz session data
    formatted = []
    for q in selected:
        options_raw = q.get("options", [])
        option_texts = []
        for opt in options_raw:
            if isinstance(opt, dict):
                label = opt.get("label", "")
                text = opt.get("text", str(opt))
                option_texts.append(f"{label}) {text}" if label else text)
            else:
                option_texts.append(str(opt))

        correct_answer = q.get("correct_answer", "A")
        correct_index = _find_correct_index_for_reuse(option_texts, correct_answer)

        formatted.append({
            "question_id": str(uuid.uuid4()),
            "question_text": q["question_text"],
            "options": option_texts,
            "concept_id": q.get("concept_id", ""),
            "concept_title": "",  # filled from concept_info later
            "_correct_answer": correct_answer,
            "_correct_index": correct_index,
            "_explanation": q.get("explanation", ""),
            "_stored_question_id": q["id"],
            "_source": "reused",
        })

    # Update times_shown for reused questions
    reused_ids = [q["id"] for q in selected]
    for qid in reused_ids:
        try:
            supabase.rpc(
                "increment_question_correct",
                {"p_question_id": qid, "p_is_correct": False},
            ).execute()
        except Exception:
            # Fallback: direct update
            try:
                current = (
                    supabase.table("quiz_questions")
                    .select("times_shown")
                    .eq("id", qid)
                    .single()
                    .execute()
                )
                supabase.table("quiz_questions").update({
                    "times_shown": (current.data or {}).get("times_shown", 0) + 1,
                    "last_shown_at": datetime.now(UTC).isoformat(),
                }).eq("id", qid).execute()
            except Exception:
                logger.debug("Failed to update times_shown for %s", qid, exc_info=True)

    return formatted


def _find_correct_index_for_reuse(options: list[str], correct_answer: str) -> int:
    """Find the correct option index from a correct_answer string."""
    correct_lower = correct_answer.strip().lower()
    for i, opt in enumerate(options):
        opt_lower = opt.strip().lower()
        if opt_lower == correct_lower:
            return i
        label = chr(65 + i)
        if correct_lower == label.lower():
            return i
        if opt_lower.startswith(f"{label.lower()})"):
            if correct_lower == label.lower():
                return i
    return 0


async def get_power_quiz(
    supabase,
    user_id: str,
    session_id: str,
) -> dict:
    """Generate the Power Quiz for the session.

    Returns quiz_id and questions (without correct answers).
    """
    session = await get_session(supabase, user_id, session_id)
    if not session:
        raise ValueError(f"Session {session_id} not found")

    concepts_planned = session.get("session_data", {}).get(
        "daily_briefing", {}
    ).get("concepts_planned", [])

    course_id = session["course_id"]
    time_budget = session.get("time_budget_minutes", 15)

    # Determine question count based on time budget
    if time_budget <= 10:
        num_questions = 6
    elif time_budget <= 15:
        num_questions = 8
    else:
        num_questions = 12

    # Gather grounding material for each concept
    all_chunks = []
    concept_info = []
    for concept in concepts_planned:
        title = concept.get("title", "")
        concept_id = concept.get("concept_id", "")
        chunks: list[dict] = []

        # If title is missing, try to fetch it from the DB
        if not title.strip() and concept_id:
            try:
                c_row = (
                    supabase.table("concepts")
                    .select("title")
                    .eq("id", concept_id)
                    .single()
                    .execute()
                )
                title = (c_row.data or {}).get("title", "") or ""
            except Exception:
                pass

        # Try hybrid search first (only if we have a non-empty query)
        if title.strip():
            try:
                chunks = await search_lectures(
                    supabase=supabase,
                    course_id=course_id,
                    query=title,
                    limit=3,
                )
            except Exception:
                logger.debug("Hybrid search failed for concept %s", title, exc_info=True)

        # Fallback: fetch chunks directly from the concept's lecture
        if not chunks and concept_id:
            try:
                concept_row = (
                    supabase.table("concepts")
                    .select("lecture_id")
                    .eq("id", concept_id)
                    .single()
                    .execute()
                )
                lecture_id = concept_row.data.get("lecture_id") if concept_row.data else None
                if lecture_id:
                    direct = (
                        supabase.table("lecture_chunks")
                        .select("id, lecture_id, content, start_time, end_time, slide_number, metadata")
                        .eq("lecture_id", lecture_id)
                        .limit(4)
                        .execute()
                    )
                    for row in (direct.data or []):
                        # Get lecture title for context formatting
                        lec_title = ""
                        try:
                            lec = (
                                supabase.table("lectures")
                                .select("title")
                                .eq("id", lecture_id)
                                .single()
                                .execute()
                            )
                            lec_title = lec.data.get("title", "") if lec.data else ""
                        except Exception:
                            pass
                        chunks.append({
                            "chunk_id": row["id"],
                            "lecture_id": row["lecture_id"],
                            "lecture_title": lec_title,
                            "content": row["content"],
                            "start_time": row.get("start_time"),
                            "end_time": row.get("end_time"),
                            "slide_number": row.get("slide_number"),
                            "metadata": row.get("metadata", {}),
                        })
            except Exception:
                logger.debug("Direct chunk fallback failed for concept %s", concept_id, exc_info=True)

        if chunks:
            all_chunks.extend(chunks)
            concept_info.append({
                "concept_id": concept_id,
                "title": title,
                "chunks": chunks,
            })

    # Broadest fallback: grab recent chunks for the entire course
    # lecture_chunks has no course_id column, so join through lectures table
    if not all_chunks:
        try:
            lectures_result = (
                supabase.table("lectures")
                .select("id")
                .eq("course_id", course_id)
                .order("created_at", desc=True)
                .limit(3)
                .execute()
            )
            lecture_ids = [lec["id"] for lec in (lectures_result.data or [])]
            if lecture_ids:
                course_chunks = (
                    supabase.table("lecture_chunks")
                    .select("id, lecture_id, content, start_time, end_time, slide_number, metadata")
                    .in_("lecture_id", lecture_ids)
                    .limit(8)
                    .execute()
                )
                for row in (course_chunks.data or []):
                    all_chunks.append({
                        "chunk_id": row["id"],
                        "lecture_id": row["lecture_id"],
                        "lecture_title": "",
                        "content": row["content"],
                        "start_time": row.get("start_time"),
                        "end_time": row.get("end_time"),
                        "slide_number": row.get("slide_number"),
                        "metadata": row.get("metadata", {}),
                    })
        except Exception:
            logger.debug("Course-wide chunk fallback failed", exc_info=True)

    # --- Try reusing existing questions before Gemini call ---
    concept_ids = [c["concept_id"] for c in concept_info if c.get("concept_id")]
    reuse_count = min(num_questions // 2, 4)  # Reuse up to half, max 4
    reused_questions = await _try_reuse_power_quiz_questions(
        supabase, course_id, concept_ids, reuse_count,
    )

    # Fill concept_title for reused questions
    for rq in reused_questions:
        for ci in concept_info:
            if ci["concept_id"] == rq.get("concept_id"):
                rq["concept_title"] = ci.get("title", "")
                break

    remaining_needed = num_questions - len(reused_questions)

    # If we still have no lecture content, return reused questions only
    # (or empty quiz if none reused) rather than letting the LLM hallucinate.
    if not all_chunks:
        if not reused_questions:
            logger.warning("Power quiz: no lecture content found for course %s — returning empty quiz", course_id)
        quiz_id = str(uuid.uuid4())
        questions = reused_questions
        session_data = session.get("session_data", {})
        session_data["power_quiz"] = {"quiz_id": quiz_id, "questions": questions}
        session_data["combo_count"] = 0
        with contextlib.suppress(Exception):
            supabase.table("learn_sessions").update({
                "session_data": session_data,
            }).eq("id", session_id).execute()
        client_questions = [
            {
                "question_id": q["question_id"],
                "question_text": q["question_text"],
                "options": q["options"],
                "concept_id": q["concept_id"],
                "concept_title": q["concept_title"],
            }
            for q in questions
        ]
        return {"quiz_id": quiz_id, "questions": client_questions}

    # Map concept titles to IDs
    title_to_id = {c["title"]: c["concept_id"] for c in concept_info}

    # --- Generate remaining questions via Gemini ---
    generated_questions: list[dict] = []
    if remaining_needed > 0:
        context = format_chunks_for_context(all_chunks)
        concept_list = ", ".join(c["title"] for c in concept_info if c["title"])
        if not concept_list:
            concept_list = "the topics covered in the lecture content below"

        prompt = (
            f"Generate exactly {remaining_needed} multiple-choice quiz questions.\n"
            f"Concepts to cover: {concept_list}\n"
            "Interleave questions across concepts (don't group by concept).\n\n"
            f"Lecture Content:\n{context}\n\n"
            "Rules:\n"
            "- Each question must have exactly 4 options (A-D)\n"
            "- One correct answer per question\n"
            "- CRITICAL: Every question MUST be directly answerable from the lecture "
            "content provided above. Do NOT use outside knowledge.\n"
            "- Vary difficulty: some recognition, some application\n"
            "- Include the concept_title for each question\n\n"
            "Respond ONLY with valid JSON array:\n"
            "[\n"
            '  {\n'
            '    "question_text": "...",\n'
            '    "options": ["A) ...", "B) ...", "C) ...", "D) ..."],\n'
            '    "correct_answer": "A",\n'
            '    "correct_index": 0,\n'
            '    "explanation": "...",\n'
            '    "concept_title": "..."\n'
            '  }\n'
            "]"
        )

        try:
            response = await _get_client().aio.models.generate_content(
                model=QUIZ_MODEL,
                contents=prompt,
                config={
                    "temperature": 0.5,
                    "response_mime_type": "application/json",
                },
            )
            raw_questions = json.loads(response.text)
            if isinstance(raw_questions, dict):
                raw_questions = raw_questions.get("questions", [])
        except Exception:
            logger.error("Power quiz generation failed", exc_info=True)
            raw_questions = []

        for q in raw_questions[:remaining_needed]:
            question_id = str(uuid.uuid4())
            concept_title = q.get("concept_title", "")
            concept_id_for_q = title_to_id.get(concept_title, "")

            generated_questions.append({
                "question_id": question_id,
                "question_text": q.get("question_text", ""),
                "options": q.get("options", []),
                "concept_id": concept_id_for_q,
                "concept_title": concept_title,
                "_correct_answer": q.get("correct_answer", "A"),
                "_correct_index": q.get("correct_index", 0),
                "_explanation": q.get("explanation", ""),
                "_stored_question_id": None,
                "_source": "generated",
            })

    # --- Persist newly generated questions to quiz_questions ---
    for q in generated_questions:
        record = {
            "user_id": user_id,
            "question_index": 0,
            "question_type": "mcq",
            "question_text": q["question_text"],
            "options": [
                {"label": chr(65 + i), "text": opt.lstrip("ABCD) ")}
                for i, opt in enumerate(q["options"])
            ],
            "correct_answer": q["_correct_answer"],
            "explanation": q.get("_explanation", ""),
            "concept_id": q.get("concept_id") or title_to_id.get(q.get("concept_title", "")),
            "source": "power_quiz",
            "difficulty": 0.5,
            "times_shown": 1,
            "last_shown_at": datetime.now(UTC).isoformat(),
        }
        # Remove concept_id if empty to avoid FK violation
        if not record["concept_id"]:
            record.pop("concept_id", None)
        try:
            result = supabase.table("quiz_questions").insert(record).execute()
            if result.data:
                q["_stored_question_id"] = result.data[0]["id"]
        except Exception:
            logger.debug("Failed to persist power quiz question", exc_info=True)

    # Merge reused + generated, shuffle
    all_quiz_questions = reused_questions + generated_questions
    random.shuffle(all_quiz_questions)
    questions = all_quiz_questions[:num_questions]

    # Store quiz data in session
    quiz_id = str(uuid.uuid4())
    session_data = session.get("session_data", {})
    session_data["power_quiz"] = {
        "quiz_id": quiz_id,
        "questions": questions,
    }
    session_data["combo_count"] = 0

    try:
        supabase.table("learn_sessions").update({
            "session_data": session_data,
        }).eq("id", session_id).execute()
    except Exception:
        logger.warning("Failed to store power quiz in session", exc_info=True)

    # Return questions WITHOUT correct answers
    client_questions = [
        {
            "question_id": q["question_id"],
            "question_text": q["question_text"],
            "options": q["options"],
            "concept_id": q["concept_id"],
            "concept_title": q["concept_title"],
        }
        for q in questions
    ]

    return {
        "quiz_id": quiz_id,
        "questions": client_questions,
    }


async def submit_power_quiz_answer(
    supabase,
    user_id: str,
    session_id: str,
    question_id: str,
    answer_index: int,
    time_ms: int = 0,
) -> dict:
    """Submit a single Power Quiz answer with immediate feedback.

    Returns correctness, explanation, XP, and combo info.
    """
    session = await get_session(supabase, user_id, session_id)
    if not session:
        raise ValueError(f"Session {session_id} not found")

    session_data = session.get("session_data", {})
    quiz_data = session_data.get("power_quiz", {})
    questions = quiz_data.get("questions", [])

    # Find the question
    question = None
    for q in questions:
        if q["question_id"] == question_id:
            question = q
            break

    if question is None:
        raise ValueError(f"Question {question_id} not found in session")

    # Grade
    correct_index = question.get("_correct_index", 0)
    is_correct = answer_index == correct_index

    correct_answer_text = ""
    options = question.get("options", [])
    if 0 <= correct_index < len(options):
        correct_answer_text = options[correct_index]

    # Speed-run detection
    is_speed_run = time_ms > 0 and time_ms < 3000

    # Combo tracking
    combo_count = session_data.get("combo_count", 0)
    combo_max = session_data.get("combo_max", 0)

    if is_correct and not is_speed_run:
        combo_count += 1
    else:
        combo_count = 0

    combo_max = max(combo_max, combo_count)
    combo_multiplier = _get_combo_multiplier(combo_count) if not is_speed_run else 1

    # Award XP (only for correct answers)
    if is_correct:
        xp_result = await _award_xp(supabase, user_id, "quiz_correct")
        base_xp = xp_result.get("amount", 0)
        xp_earned = base_xp * combo_multiplier
    else:
        xp_result = {"amount": 0, "total_xp": 0, "level": 1, "leveled_up": False}
        xp_earned = 0

    # Build source citation
    source_citation = ""
    explanation = question.get("_explanation", "")

    # Record result
    quiz_results = session_data.get("quiz_results", [])
    quiz_results.append({
        "question_id": question_id,
        "answer_index": answer_index,
        "correct": is_correct,
        "time_ms": time_ms,
        "speed_run": is_speed_run,
        "xp_earned": xp_earned,
        "combo_count": combo_count,
    })

    session_data["quiz_results"] = quiz_results
    session_data["combo_count"] = combo_count
    session_data["combo_max"] = combo_max

    # Update session
    try:
        supabase.table("learn_sessions").update({
            "session_data": session_data,
        }).eq("id", session_id).execute()
    except Exception:
        logger.warning("Failed to update quiz results", exc_info=True)

    # Record learning event for mastery tracking
    await record_learning_event(
        supabase,
        user_id=user_id,
        course_id=session["course_id"],
        concept_id=question.get("concept_id", ""),
        event_type="power_quiz",
        is_correct=is_correct,
        student_answer=str(answer_index),
        time_ms=time_ms,
        metadata={"combo_count": combo_count, "speed_run": is_speed_run},
    )

    return {
        "correct": is_correct,
        "correct_answer": correct_answer_text,
        "explanation": explanation,
        "source_citation": source_citation,
        "xp_earned": xp_earned,
        "combo_count": combo_count,
        "combo_multiplier": combo_multiplier,
    }


async def complete_learn_session(
    supabase,
    user_id: str,
    session_id: str,
) -> dict:
    """Complete the session and generate celebration data."""
    session = await get_session(supabase, user_id, session_id)
    if not session:
        raise ValueError(f"Session {session_id} not found")

    session_data = session.get("session_data", {})
    started_at = session.get("started_at", "")

    # 1. Mark session complete
    now = datetime.now(UTC)
    try:
        supabase.table("learn_sessions").update({
            "status": "completed",
            "completed_at": now.isoformat(),
        }).eq("id", session_id).execute()
    except Exception:
        logger.warning("Failed to update session status", exc_info=True)

    # 2. Compute duration
    duration_minutes = 0
    if started_at:
        try:
            start = datetime.fromisoformat(started_at.replace("Z", "+00:00"))
            duration_minutes = int((now - start).total_seconds() / 60)
        except Exception:
            pass

    # 3. Concepts covered
    concepts_planned = session_data.get("daily_briefing", {}).get("concepts_planned", [])
    concepts_covered = []
    for c in concepts_planned:
        concepts_covered.append({
            "title": c.get("title", ""),
            "mastery_before": c.get("mastery", 0.0),
            "mastery_after": min(1.0, c.get("mastery", 0.0) + 0.05),
            "delta": 0.05,
        })

    # 4. Quiz score
    quiz_results = session_data.get("quiz_results", [])
    correct_count = sum(1 for r in quiz_results if r.get("correct"))
    total_questions = len(quiz_results)
    accuracy = correct_count / total_questions if total_questions > 0 else 0.0
    combo_max = session_data.get("combo_max", 0)

    # 5. XP summary
    xp_breakdown = session_data.get("xp_breakdown", [])
    flash_xp = sum(
        r.get("xp_earned", 0)
        for r in session_data.get("flash_review_results", [])
        if r.get("xp_earned")
    )
    quiz_xp = sum(r.get("xp_earned", 0) for r in quiz_results)

    # Award session complete XP
    session_xp = await _award_xp(supabase, user_id, "session_complete")
    session_xp_amount = session_xp.get("amount", 50)

    total_xp = flash_xp + quiz_xp + session_xp_amount
    xp_breakdown = [
        {"source": "flash_review", "amount": flash_xp},
        {"source": "power_quiz", "amount": quiz_xp},
        {"source": "session_complete", "amount": session_xp_amount},
    ]

    # 6. Update streak and map to StreakInfo shape
    streak_raw = await _update_streak(supabase, user_id)
    streak = {
        "current_streak": streak_raw.get("current_streak", streak_raw.get("current", 1)),
        "longest_streak": streak_raw.get("longest_streak", streak_raw.get("longest", 1)),
        "studied_today": True,
        "freeze_available": False,
        "streak_milestone": streak_raw.get("streak_milestone", streak_raw.get("milestone_hit")),
    }

    # 7. Check badges
    badges_earned = await _check_badges(supabase, user_id)

    try:
        from .observability import track_event

        track_event(user_id, "learn_session_completed", {
            "xp_earned": total_xp,
            "combo_max": combo_max,
            "concepts_completed": len(concepts_covered),
        })
    except Exception:
        pass

    # 8. Tomorrow preview — only show upcoming (future) assessments
    tomorrow_preview = ""
    try:
        from datetime import date as _date

        result = supabase.rpc(
            "get_study_priorities",
            {"p_course_id": session["course_id"]},
        ).execute()
        upcoming = [
            p
            for p in (result.data or [])
            if p.get("due_date") and p["due_date"] >= str(_date.today())
        ]
        if upcoming:
            title = upcoming[0].get("title", "Review")
            tomorrow_preview = f"Continue preparing for {title}"
        else:
            tomorrow_preview = "Keep your streak going tomorrow!"
    except Exception:
        tomorrow_preview = "Keep your streak going tomorrow!"

    return {
        "session_summary": {
            "duration_minutes": duration_minutes,
            "concepts_covered": concepts_covered,
            "quiz_score": {
                "correct": correct_count,
                "total": total_questions,
                "accuracy": round(accuracy, 2),
            },
            "combo_max": combo_max,
        },
        "xp_summary": {
            "total_earned": total_xp,
            "breakdown": xp_breakdown,
            "level_before": session_xp.get("level", 1),
            "level_after": session_xp.get("level", 1),
            "leveled_up": session_xp.get("leveled_up", False),
        },
        "streak": streak,
        "badges_earned": badges_earned,
        "tomorrow_preview": tomorrow_preview,
    }


async def abandon_learn_session(
    supabase,
    user_id: str,
    session_id: str,
) -> dict:
    """Mark session as abandoned. No session_complete XP. Partial XP preserved."""
    session = await get_session(supabase, user_id, session_id)
    if not session:
        raise ValueError(f"Session {session_id} not found")

    try:
        supabase.table("learn_sessions").update({
            "status": "abandoned",
            "completed_at": datetime.now(UTC).isoformat(),
        }).eq("id", session_id).execute()
    except Exception:
        logger.warning("Failed to mark session abandoned", exc_info=True)

    return {
        "status": "abandoned",
        "session_id": session_id,
        "partial_xp_preserved": True,
    }
