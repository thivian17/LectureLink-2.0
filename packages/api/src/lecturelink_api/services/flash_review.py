"""Flash review card generation for Learn Mode sessions.

Generates recognition-based MCQ cards graded by the system (NOT self-rating).
Cards test whether the student can identify/recognize key facts about
previously studied concepts.
"""

from __future__ import annotations

import asyncio

from .mastery import compute_mastery
import json
import logging
import uuid

from .genai_client import get_genai_client as _get_client
from .search import search_lectures

logger = logging.getLogger(__name__)

FLASH_MODEL = "gemini-2.5-flash"


async def get_flash_review_cards(
    supabase,
    user_id: str,
    course_id: str,
    count: int = 5,
    session_concepts: list[dict] | None = None,
) -> list[dict]:
    """Get flash review cards for a Learn Mode session.

    Selection logic:
    1. Get concepts where user has some history (at least 1 quiz attempt)
    2. Prioritize by: lowest mastery first, then longest since last review
    3. For each concept, try to pull an existing quiz_question (MCQ/true_false)
    4. If no existing question, generate a quick recognition MCQ via Gemini
    5. Return up to ``count`` cards
    6. Fallback for new users: generate cards from session concepts or course concepts
    """
    # 1. Get concept mastery data for this user+course
    try:
        mastery_result = supabase.rpc(
            "get_concept_mastery",
            {"p_course_id": course_id, "p_user_id": user_id},
        ).execute()
        mastery_data = mastery_result.data or []
    except Exception:
        logger.warning("get_concept_mastery RPC failed", exc_info=True)
        mastery_data = []

    # Filter to concepts with at least 1 attempt
    reviewed_concepts = [
        m for m in mastery_data if m.get("total_attempts", 0) > 0
    ]

    # 2. Sort by mastery ascending (lowest first), then by total_attempts ascending
    def _priority_key(m):
        mastery = compute_mastery(
            m.get("accuracy", 0.0), m.get("recent_accuracy", 0.0), m.get("total_attempts", 0),
        )
        return (mastery, m.get("total_attempts", 0))

    # Determine which concepts to build cards from
    if reviewed_concepts:
        reviewed_concepts.sort(key=_priority_key)
        source_concepts = [
            {"concept_id": m["concept_id"], "concept_title": m.get("concept_title", "Unknown")}
            for m in reviewed_concepts
        ]
    elif session_concepts:
        source_concepts = [
            {"concept_id": c.get("concept_id", ""), "concept_title": c.get("concept_title", "Unknown")}
            for c in session_concepts
        ]
    else:
        # Last resort: query course concepts directly
        try:
            concepts_result = (
                supabase.table("concepts")
                .select("id, title")
                .eq("course_id", course_id)
                .limit(count)
                .execute()
            )
            source_concepts = [
                {"concept_id": c["id"], "concept_title": c.get("title", "Unknown")}
                for c in (concepts_result.data or [])
            ]
        except Exception:
            return []

    if not source_concepts:
        return []

    # 3. Build flash cards (parallel generation for speed)
    async def _build_card(concept_data: dict) -> dict | None:
        concept_id = concept_data["concept_id"]
        concept_title = concept_data.get("concept_title", "Unknown")
        try:
            card = await _try_existing_question(supabase, concept_id, concept_title)
            if card is None:
                card = await _generate_card_for_concept(
                    supabase, course_id, concept_id, concept_title
                )
            return card
        except Exception:
            logger.debug("Card generation failed for %s", concept_title, exc_info=True)
            return None

    results = await asyncio.gather(
        *[_build_card(c) for c in source_concepts[:count]]
    )
    cards = [c for c in results if c is not None]

    return cards


async def _try_existing_question(
    supabase,
    concept_id: str,
    concept_title: str,
) -> dict | None:
    """Try to pull an existing MCQ question for a concept from quiz_questions."""
    try:
        result = (
            supabase.table("quiz_questions")
            .select("id, question_text, options, correct_answer, question_type")
            .eq("concept_id", concept_id)
            .eq("question_type", "mcq")
            .limit(1)
            .execute()
        )
        questions = result.data or []
    except Exception:
        logger.debug("Failed to fetch existing questions for %s", concept_id)
        return None

    if not questions:
        return None

    q = questions[0]
    options = q.get("options", [])

    # Normalize options to list of strings
    option_texts = []
    for opt in options:
        if isinstance(opt, dict):
            option_texts.append(opt.get("text", str(opt)))
        else:
            option_texts.append(str(opt))

    # Find correct index from correct_answer
    correct_answer = q.get("correct_answer", "")
    correct_index = _find_correct_index(option_texts, correct_answer)

    # Limit to 2-3 options for flash review speed
    if len(option_texts) > 3:
        option_texts, correct_index = _trim_options(
            option_texts, correct_index, target=3
        )

    return {
        "card_id": str(uuid.uuid4()),
        "concept_id": concept_id,
        "concept_title": concept_title,
        "question_text": q["question_text"],
        "options": option_texts,
        "correct_index": correct_index,
        "source": "existing",
        "source_lecture_title": concept_title,
    }


def _find_correct_index(options: list[str], correct_answer: str) -> int:
    """Find the index of the correct answer in the options list."""
    correct_lower = correct_answer.strip().lower()
    for i, opt in enumerate(options):
        opt_lower = opt.strip().lower()
        if opt_lower == correct_lower:
            return i
        # Check label match (A, B, C, D)
        label = chr(65 + i)  # A=65
        if correct_lower == label.lower():
            return i
    return 0


def _trim_options(
    options: list[str], correct_index: int, target: int = 3
) -> tuple[list[str], int]:
    """Trim options to target count while preserving the correct answer."""
    if len(options) <= target:
        return options, correct_index

    # Always keep the correct option, pick (target-1) distractors
    correct_text = options[correct_index]
    distractors = [opt for i, opt in enumerate(options) if i != correct_index]
    kept_distractors = distractors[: target - 1]

    new_options = [correct_text] + kept_distractors
    # Deterministic shuffle: correct answer goes to index 0
    # For flash review, this is acceptable
    return new_options, 0


async def _generate_card_for_concept(
    supabase,
    course_id: str,
    concept_id: str,
    concept_title: str,
) -> dict | None:
    """Generate a flash card for a concept using Gemini."""
    # Get source chunks for grounding
    try:
        chunks = await search_lectures(
            supabase=supabase,
            course_id=course_id,
            query=concept_title,
            limit=2,
        )
    except Exception:
        logger.debug("Failed to get chunks for flash card: %s", concept_title)
        chunks = []

    return await generate_flash_card(
        {"concept_id": concept_id, "concept_title": concept_title},
        chunks,
    )


async def generate_flash_card(
    concept: dict,
    source_chunks: list[dict],
) -> dict | None:
    """Generate a single recognition-based flash card for a concept.

    Uses Gemini Flash with structured JSON output.
    """
    title = concept.get("concept_title", "Unknown")
    source_lecture_title = ""
    chunk_texts = []
    for c in source_chunks:
        chunk_texts.append(c.get("content", ""))
        if not source_lecture_title:
            source_lecture_title = c.get("lecture_title", "")

    chunk_context = "\n---\n".join(chunk_texts) if chunk_texts else "No lecture content available."

    prompt = (
        f"Create a quick recognition question for the concept '{title}'.\n"
        "The question should test whether the student can identify/recognize key facts, "
        "not generate them. Use 2-3 short answer options. One must be correct.\n"
        f"Ground the question in this lecture content:\n{chunk_context}\n\n"
        "Respond ONLY with valid JSON:\n"
        '{\n'
        '  "question_text": "short question",\n'
        '  "options": ["option A", "option B", "option C"],\n'
        '  "correct_index": 0\n'
        '}'
    )

    try:
        response = await _get_client().aio.models.generate_content(
            model=FLASH_MODEL,
            contents=prompt,
            config={
                "temperature": 0.3,
                "response_mime_type": "application/json",
            },
        )
        result = json.loads(response.text)

        options = result.get("options", [])
        if not options or not result.get("question_text"):
            return None

        correct_index = result.get("correct_index", 0)
        if correct_index < 0 or correct_index >= len(options):
            correct_index = 0

        return {
            "card_id": str(uuid.uuid4()),
            "concept_id": concept.get("concept_id", ""),
            "concept_title": title,
            "question_text": result["question_text"],
            "options": options,
            "correct_index": correct_index,
            "source": "generated",
            "source_lecture_title": source_lecture_title or title,
        }
    except Exception:
        logger.warning("Flash card generation failed for %s", title, exc_info=True)
        return None


def grade_flash_review(card: dict, student_answer_index: int) -> dict:
    """Grade a flash review answer. Pure function, no LLM needed.

    Returns:
        {correct: bool, correct_answer: str, xp_earned: int}
    """
    correct_index = card.get("correct_index", 0)
    options = card.get("options", [])
    is_correct = student_answer_index == correct_index

    correct_answer = (
        options[correct_index] if 0 <= correct_index < len(options) else ""
    )

    return {
        "correct": is_correct,
        "correct_answer": correct_answer,
        "xp_earned": 5 if is_correct else 2,
    }
