"""Performance analytics — aggregates quiz attempts into concept mastery."""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


async def get_performance(
    supabase,
    course_id: str,
    user_id: str,
) -> dict:
    """Compute performance analytics for a student in a course.

    Results are cached in Redis for 60 seconds when available.

    Returns:
        {
            "overall": {total_questions_attempted, overall_accuracy, ...},
            "concepts": [{concept_id, title, mastery, trend, ...}],
            "quiz_history": [{quiz_id, title, best_score, ...}],
            "weak_concepts": [concept_ids with mastery < 0.5],
            "strong_concepts": [concept_ids with mastery >= 0.8],
        }
    """
    # Check Redis cache first
    cache_key = f"perf:{user_id}:{course_id}"
    try:
        from lecturelink_api.services.redis_client import cache_get

        cached = await cache_get(cache_key)
        if cached is not None:
            return cached
    except Exception:
        pass

    # 1. Concept mastery via SQL function
    try:
        mastery_result = supabase.rpc(
            "get_concept_mastery",
            {"p_course_id": course_id, "p_user_id": user_id},
        ).execute()
        mastery_data = mastery_result.data or []
    except Exception:
        logger.warning(
            "get_concept_mastery RPC failed (migration 003 not applied?)",
            exc_info=True,
        )
        mastery_data = []

    # 2. Quiz history via SQL function
    try:
        history_result = supabase.rpc(
            "get_quiz_history_summary",
            {"p_course_id": course_id, "p_user_id": user_id},
        ).execute()
        quiz_history = history_result.data or []
    except Exception:
        logger.warning(
            "get_quiz_history_summary RPC failed (migration 003 not applied?)",
            exc_info=True,
        )
        quiz_history = []

    # 3. Enrich concepts with assessment links (bulk)
    concept_ids = [m["concept_id"] for m in mastery_data if m.get("concept_id")]
    assessment_links: dict[str, list[dict]] = {}
    if concept_ids:
        try:
            links_result = (
                supabase.table("concept_assessment_links")
                .select("concept_id, assessment_id, relevance_score")
                .in_("concept_id", concept_ids)
                .execute()
            )
            assessment_ids = list(
                {lnk["assessment_id"] for lnk in (links_result.data or [])}
            )
            titles_map: dict[str, str] = {}
            if assessment_ids:
                titles_result = (
                    supabase.table("assessments")
                    .select("id, title")
                    .in_("id", assessment_ids)
                    .execute()
                )
                titles_map = {a["id"]: a["title"] for a in (titles_result.data or [])}

            for link in links_result.data or []:
                cid = link["concept_id"]
                assessment_links.setdefault(cid, []).append({
                    "assessment_id": link["assessment_id"],
                    "title": titles_map.get(link["assessment_id"], "Unknown"),
                    "relevance_score": link.get("relevance_score", 0),
                })
        except Exception:
            logger.warning("Failed to fetch assessment links", exc_info=True)

    # 4. Build concept entries with mastery scores
    concepts = []
    total_attempted = 0
    total_correct = 0
    category_scores: dict[str, list[float]] = {}

    for m in mastery_data:
        attempts = m.get("total_attempts", 0)
        accuracy = m.get("accuracy", 0.0)
        recent = m.get("recent_accuracy", 0.0)

        mastery = 0.0 if attempts == 0 else round(accuracy * 0.6 + recent * 0.4, 4)

        total_attempted += attempts
        total_correct += m.get("correct_attempts", 0)

        cat = m.get("concept_category") or "general"
        category_scores.setdefault(cat, []).append(mastery)

        concepts.append({
            "concept_id": m["concept_id"],
            "title": m["concept_title"],
            "description": m.get("concept_description"),
            "category": cat,
            "difficulty_estimate": m.get("difficulty_estimate", 0.5),
            "lecture_id": m.get("lecture_id"),
            "mastery": mastery,
            "total_attempts": attempts,
            "correct_attempts": m.get("correct_attempts", 0),
            "accuracy": accuracy,
            "avg_time_seconds": m.get("avg_time_seconds", 0.0),
            "recent_accuracy": recent,
            "trend": m.get("trend", "new"),
            "linked_assessments": assessment_links.get(m["concept_id"], []),
        })

    # 5. Overall metrics
    overall_accuracy = (total_correct / total_attempted) if total_attempted > 0 else 0.0
    scored_quizzes = [q for q in quiz_history if q.get("best_score") is not None]
    avg_score = (
        sum(q["best_score"] for q in scored_quizzes) / len(scored_quizzes)
        if scored_quizzes
        else None
    )

    def _cat_avg(cat: str) -> float:
        scores = category_scores[cat]
        return sum(scores) / len(scores)

    strongest = (
        max(category_scores, key=_cat_avg) if category_scores else None
    )
    weakest = (
        min(category_scores, key=_cat_avg) if category_scores else None
    )

    weak_ids = [
        c["concept_id"]
        for c in concepts
        if c["mastery"] < 0.5 and c["total_attempts"] > 0
    ]
    strong_ids = [c["concept_id"] for c in concepts if c["mastery"] >= 0.8]

    result = {
        "overall": {
            "total_questions_attempted": total_attempted,
            "overall_accuracy": round(overall_accuracy, 4),
            "quizzes_taken": len(scored_quizzes),
            "average_quiz_score": round(avg_score, 1) if avg_score is not None else None,
            "strongest_category": strongest,
            "weakest_category": weakest,
        },
        "concepts": concepts,
        "quiz_history": [
            {
                "quiz_id": q["quiz_id"],
                "title": q["quiz_title"],
                "difficulty": q["difficulty"],
                "best_score": q.get("best_score"),
                "attempt_count": q.get("attempt_count", 0),
                "question_count": q.get("question_count", 0),
                "created_at": str(q["created_at"]),
            }
            for q in quiz_history
        ],
        "weak_concepts": weak_ids,
        "strong_concepts": strong_ids,
    }

    # Cache the result for 60 seconds
    try:
        from lecturelink_api.services.redis_client import cache_set

        await cache_set(cache_key, result, ttl=60)
    except Exception:
        pass

    return result
