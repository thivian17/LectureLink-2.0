"""Quiz planner — selects concepts and retrieves grounding chunks."""

from __future__ import annotations

import logging

from .assessment_prep import get_assessment_concepts
from .chunk_fetcher import fetch_concept_chunks

logger = logging.getLogger(__name__)


async def plan_quiz(
    supabase,
    course_id: str,
    user_id: str,
    target_assessment_id: str | None = None,
    lecture_ids: list[str] | None = None,
    num_questions: int = 10,
    difficulty: str = "medium",
) -> dict:
    """Plan a quiz by selecting concepts and retrieving grounding material.

    Uses priority scoring to select the most important concepts.
    For each concept, retrieves the top grounding chunks that the
    question generator will use as source material.

    Args:
        supabase: Supabase client
        course_id: Course to quiz on
        user_id: Student (for priority personalization in Phase 3)
        target_assessment_id: Optional — quiz targets a specific assessment
        lecture_ids: Optional — restrict to specific lectures
        num_questions: How many questions to generate (default 10)
        difficulty: easy / medium / hard / adaptive

    Returns:
        {
            "concepts": [{concept, grounding_chunks}],
            "difficulty": str,
            "num_questions": int,
            "target_assessment_id": str | None,
        }
    """
    # 1. Get concepts for this course, prioritized
    if target_assessment_id:
        assessment_concepts = await get_assessment_concepts(
            supabase, target_assessment_id, course_id, user_id,
        )

        if assessment_concepts:
            concept_ids = [ac["concept_id"] for ac in assessment_concepts[:num_questions * 2]]
            concepts_result = (
                supabase.table("concepts")
                .select(
                    "id, title, description, category,"
                    " difficulty_estimate, lecture_id, subconcepts"
                )
                .in_("id", concept_ids)
                .execute()
            )
            concepts = concepts_result.data
        else:
            concepts = []
    else:
        query = (
            supabase.table("concepts")
            .select(
                "id, title, description, category,"
                " difficulty_estimate, lecture_id, subconcepts"
            )
            .eq("course_id", course_id)
        )
        if lecture_ids:
            query = query.in_("lecture_id", lecture_ids)
        concepts_result = query.execute()
        concepts = concepts_result.data

    if not concepts:
        raise ValueError(f"No concepts found for course {course_id}")

    # 2. Concept selection: adaptive or difficulty-band
    adaptive_difficulties: dict[str, float] | None = None

    if difficulty == "adaptive" and user_id:
        # Adaptive: prioritize weak concepts using student mastery data
        mastery_result = supabase.rpc(
            "get_concept_mastery",
            {"p_course_id": course_id, "p_user_id": user_id},
        ).execute()
        mastery_map = {
            m["concept_id"]: m for m in (mastery_result.data or [])
        }

        def _adaptive_score(concept):
            m = mastery_map.get(concept["id"])
            if m is None or m["total_attempts"] == 0:
                return 0.5  # new concepts get medium priority
            mastery = m["accuracy"] * 0.6 + m["recent_accuracy"] * 0.4
            return 1.0 - mastery  # low mastery = high priority

        concepts.sort(key=_adaptive_score, reverse=True)

        # Compute per-concept adaptive difficulty
        adaptive_difficulties = {}
        for c in concepts:
            m = mastery_map.get(c["id"])
            if m is None or m["total_attempts"] == 0:
                adaptive_difficulties[c["id"]] = c.get("difficulty_estimate", 0.5)
            else:
                student_mastery = m["accuracy"] * 0.6 + m["recent_accuracy"] * 0.4
                adaptive_difficulties[c["id"]] = min(
                    1.0,
                    max(
                        0.1,
                        c.get("difficulty_estimate", 0.5)
                        + (student_mastery - 0.5) * 0.4,
                    ),
                )

        selected = concepts[:num_questions]
    else:
        # Original difficulty band filtering
        difficulty_ranges = {
            "easy": (0.0, 0.4),
            "medium": (0.2, 0.7),
            "hard": (0.5, 1.0),
        }
        low, high = difficulty_ranges.get(difficulty, (0.2, 0.7))

        in_range = [
            c for c in concepts
            if low <= c.get("difficulty_estimate", 0.5) <= high
        ]
        out_of_range = [c for c in concepts if c not in in_range]
        prioritized = in_range + out_of_range

        selected = prioritized[:num_questions]

    # 3. For each concept, retrieve grounding chunks (deterministic via chunk_fetcher)
    quiz_plan: list[dict] = []
    for concept in selected:
        chunks = await fetch_concept_chunks(
            supabase,
            concept_id=concept["id"],
            course_id=course_id,
            limit=3,
            concept_title=concept.get("title", ""),
        )

        quiz_plan.append({
            "concept": concept,
            "grounding_chunks": chunks,
        })

    # Remove concepts with no grounding chunks
    quiz_plan = [qp for qp in quiz_plan if qp["grounding_chunks"]]

    if not quiz_plan:
        raise ValueError("Could not find grounding chunks for any concepts")

    logger.info(
        "Quiz plan: %d concepts with grounding, difficulty=%s",
        len(quiz_plan), difficulty,
    )

    result = {
        "concepts": quiz_plan,
        "difficulty": difficulty,
        "num_questions": len(quiz_plan),
        "target_assessment_id": target_assessment_id,
    }
    if adaptive_difficulties:
        result["adaptive_difficulties"] = adaptive_difficulties

    return result
