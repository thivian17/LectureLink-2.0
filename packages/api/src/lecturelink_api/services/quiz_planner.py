"""Quiz planner — selects concepts and retrieves grounding chunks."""

from __future__ import annotations

import logging

from .search import search_lectures

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
        difficulty: easy / medium / hard

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
        links = (
            supabase.table("concept_assessment_links")
            .select("concept_id, relevance_score")
            .eq("assessment_id", target_assessment_id)
            .order("relevance_score", desc=True)
            .limit(num_questions * 2)
            .execute()
        )

        if links.data:
            concept_ids = [link["concept_id"] for link in links.data]
            concepts_result = (
                supabase.table("concepts")
                .select(
                    "id, title, description, category,"
                    " difficulty_estimate, lecture_id"
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
                " difficulty_estimate, lecture_id"
            )
            .eq("course_id", course_id)
        )
        if lecture_ids:
            query = query.in_("lecture_id", lecture_ids)
        concepts_result = query.execute()
        concepts = concepts_result.data

    if not concepts:
        raise ValueError(f"No concepts found for course {course_id}")

    # 2. Filter by difficulty band
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

    # 3. For each concept, retrieve grounding chunks
    quiz_plan: list[dict] = []
    for concept in selected:
        query = f"{concept['title']}: {concept.get('description', '')}"
        # Prefer the concept's own lecture, but fall back to lecture_ids filter
        search_lecture_ids = (
            [concept["lecture_id"]] if concept.get("lecture_id")
            else lecture_ids
        )
        chunks = await search_lectures(
            supabase=supabase,
            course_id=course_id,
            query=query,
            lecture_ids=search_lecture_ids,
            limit=3,
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

    return {
        "concepts": quiz_plan,
        "difficulty": difficulty,
        "num_questions": len(quiz_plan),
        "target_assessment_id": target_assessment_id,
    }
