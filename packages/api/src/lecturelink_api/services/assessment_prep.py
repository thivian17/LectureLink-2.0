"""Assessment prep service — intelligent concept identification for exams.

Uses a two-pass approach for exam-type assessments:
  Pass 1: Schedule filter — lectures within the assessment's coverage window
  Pass 2: Embedding reranking — cosine similarity against assessment text

All relevant concepts are returned (no hard limit), ordered by relevance.
"""

from __future__ import annotations

import logging

from ..models.readiness_v2 import EXAM_TYPES
from .embedding import embed_query
from .mastery import DEFAULT_P_MASTERY

logger = logging.getLogger(__name__)


async def get_assessment_concepts(
    supabase,
    assessment_id: str,
    course_id: str,
    user_id: str,
) -> list[dict]:
    """Identify ALL relevant concepts for an assessment using schedule + embedding.

    For exam-type assessments (exam, midterm, quiz, test, final):
      1. Determine coverage window (previous exam due_date → this assessment's due_date)
      2. Fetch ALL concepts from lectures in that window
      3. Embed assessment text, compute cosine similarity against each concept
      4. Return ALL concepts sorted by similarity DESC, then p_mastery ASC

    For non-exam types, returns empty list.

    Returns:
        [{concept_id, concept_title, lecture_id, p_mastery, total_attempts,
          similarity, priority_score}]
    """
    # 1. Fetch assessment metadata
    try:
        assessment_result = (
            supabase.table("assessments")
            .select("id, title, type, due_date, topics")
            .eq("id", assessment_id)
            .single()
            .execute()
        )
        assessment = assessment_result.data
    except Exception:
        logger.warning("Failed to fetch assessment %s", assessment_id, exc_info=True)
        return []

    if not assessment:
        return []

    a_type = (assessment.get("type") or "").lower()
    if a_type not in EXAM_TYPES:
        return []

    due_date = assessment.get("due_date")
    title = assessment.get("title", "")
    topics = assessment.get("topics") or []

    # 2. Determine coverage window
    coverage_start = await _find_previous_exam_due_date(supabase, course_id, due_date)

    # 3. Fetch lectures in coverage window
    try:
        query = (
            supabase.table("lectures")
            .select("id")
            .eq("course_id", course_id)
            .eq("processing_status", "completed")
        )
        if due_date:
            query = query.lte("lecture_date", due_date)
        if coverage_start:
            query = query.gt("lecture_date", coverage_start)

        lectures_result = query.execute()
        lecture_ids = [lec["id"] for lec in (lectures_result.data or [])]
    except Exception:
        logger.warning("Failed to fetch lectures for assessment prep", exc_info=True)
        lecture_ids = []

    if not lecture_ids:
        # Fallback: use ALL lectures for the course
        try:
            all_lectures = (
                supabase.table("lectures")
                .select("id")
                .eq("course_id", course_id)
                .eq("processing_status", "completed")
                .execute()
            )
            lecture_ids = [lec["id"] for lec in (all_lectures.data or [])]
        except Exception:
            logger.warning("Failed to fetch fallback lectures", exc_info=True)
            return []

    # 4. Fetch ALL concepts from covered lectures
    try:
        concepts_result = (
            supabase.table("concepts")
            .select("id, title, lecture_id, embedding")
            .in_("lecture_id", lecture_ids)
            .execute()
        )
        concepts = concepts_result.data or []
    except Exception:
        logger.warning("Failed to fetch concepts for assessment prep", exc_info=True)
        return []

    if not concepts:
        return []

    concept_ids = [c["id"] for c in concepts]

    # 5. Fetch BKT states
    bkt_map: dict[str, dict] = {}
    try:
        bkt_result = (
            supabase.table("concept_bkt_state")
            .select("concept_id, p_mastery, total_attempts")
            .eq("user_id", user_id)
            .in_("concept_id", concept_ids)
            .execute()
        )
        for row in bkt_result.data or []:
            bkt_map[row["concept_id"]] = row
    except Exception:
        logger.warning("Failed to fetch BKT states for assessment prep", exc_info=True)

    # 6. Compute similarity via embedding
    assessment_text = f"{title} {' '.join(topics)}"
    similarities: dict[str, float] = {}

    try:
        query_embedding = await embed_query(assessment_text)
        for c in concepts:
            c_embedding = c.get("embedding")
            if c_embedding and query_embedding:
                sim = _cosine_similarity(query_embedding, c_embedding)
                similarities[c["id"]] = sim
    except Exception:
        logger.warning("Embedding reranking failed, using uniform similarity", exc_info=True)

    # 7. Build result list
    results: list[dict] = []
    for c in concepts:
        bkt = bkt_map.get(c["id"])
        p_mastery = bkt["p_mastery"] if bkt else DEFAULT_P_MASTERY
        total_attempts = bkt["total_attempts"] if bkt else 0
        sim = similarities.get(c["id"], 0.5)

        results.append({
            "concept_id": c["id"],
            "concept_title": c.get("title", ""),
            "lecture_id": c.get("lecture_id"),
            "p_mastery": round(p_mastery, 4),
            "total_attempts": total_attempts,
            "similarity": round(sim, 4),
            "priority_score": round(sim * 0.6 + (1.0 - p_mastery) * 0.4, 4),
        })

    # Sort by similarity DESC, then p_mastery ASC
    results.sort(key=lambda r: (-r["similarity"], r["p_mastery"]))

    return results


async def get_assessment_readiness(
    supabase,
    assessment_id: str,
    course_id: str,
    user_id: str,
) -> dict:
    """Compute readiness for an assessment using the new concept identification.

    Returns:
        {readiness, concept_count, mastered_count, weak_concepts, ...}
    """
    concepts = await get_assessment_concepts(supabase, assessment_id, course_id, user_id)

    if not concepts:
        return {
            "readiness": 0.0,
            "concept_count": 0,
            "mastered_count": 0,
            "weak_concepts": [],
        }

    total = len(concepts)
    mastered = sum(1 for c in concepts if c["p_mastery"] >= 0.85)
    avg_mastery = sum(c["p_mastery"] for c in concepts) / total
    # Weak concepts: bottom 5 by priority_score (highest priority = most need)
    weak = sorted(concepts, key=lambda c: c["p_mastery"])[:5]

    return {
        "readiness": round(avg_mastery, 4),
        "concept_count": total,
        "mastered_count": mastered,
        "weak_concepts": [
            {
                "concept_id": c["concept_id"],
                "title": c["concept_title"],
                "p_mastery": c["p_mastery"],
                "similarity": c["similarity"],
            }
            for c in weak
        ],
    }


async def _find_previous_exam_due_date(
    supabase,
    course_id: str,
    current_due_date: str | None,
) -> str | None:
    """Find the due_date of the most recent exam-type assessment before this one."""
    if not current_due_date:
        return None

    try:
        result = (
            supabase.table("assessments")
            .select("due_date, type")
            .eq("course_id", course_id)
            .lt("due_date", current_due_date)
            .order("due_date", desc=True)
            .execute()
        )
        for row in result.data or []:
            a_type = (row.get("type") or "").lower()
            if a_type in EXAM_TYPES:
                return row["due_date"]
    except Exception:
        logger.warning("Failed to find previous exam due date", exc_info=True)

    return None


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    """Compute cosine similarity between two vectors."""
    if len(a) != len(b) or not a:
        return 0.0

    dot = sum(x * y for x, y in zip(a, b))
    norm_a = sum(x * x for x in a) ** 0.5
    norm_b = sum(x * x for x in b) ** 0.5

    if norm_a < 1e-10 or norm_b < 1e-10:
        return 0.0

    return dot / (norm_a * norm_b)
