"""Lecture mastery service — per-lecture mastery stats and concept selection.

Provides the base layer of the study system: every concept is reachable
through its lecture, and students can study lecture-by-lecture with
weakest-first concept ordering.
"""

from __future__ import annotations

import logging

from .mastery import DEFAULT_P_MASTERY

logger = logging.getLogger(__name__)


async def get_lecture_mastery(
    supabase,
    user_id: str,
    course_id: str,
) -> list[dict]:
    """Per-lecture mastery summary for a course.

    Joins lectures → concepts → LEFT JOIN concept_bkt_state to produce
    per-lecture stats: concept_count, mastered/developing/unstarted counts,
    and average mastery.

    Returns list sorted by lecture_number ascending:
        [{lecture_id, title, lecture_number, lecture_date,
          concept_count, mastered, developing, unstarted, avg_mastery}]
    """
    # 1. Get all completed lectures for this course
    try:
        lectures_result = (
            supabase.table("lectures")
            .select("id, title, lecture_number, lecture_date")
            .eq("course_id", course_id)
            .eq("processing_status", "completed")
            .order("lecture_number")
            .execute()
        )
        lectures = lectures_result.data or []
    except Exception:
        logger.warning("Failed to fetch lectures for mastery", exc_info=True)
        return []

    if not lectures:
        return []

    lecture_ids = [lec["id"] for lec in lectures]

    # 2. Get all concepts grouped by lecture
    try:
        concepts_result = (
            supabase.table("concepts")
            .select("id, lecture_id")
            .in_("lecture_id", lecture_ids)
            .execute()
        )
        all_concepts = concepts_result.data or []
    except Exception:
        logger.warning("Failed to fetch concepts for lecture mastery", exc_info=True)
        return []

    concepts_by_lecture: dict[str, list[str]] = {}
    concept_ids: list[str] = []
    for c in all_concepts:
        lid = c.get("lecture_id")
        if lid:
            concepts_by_lecture.setdefault(lid, []).append(c["id"])
            concept_ids.append(c["id"])

    # 3. Get BKT state for all concepts
    bkt_map: dict[str, float] = {}
    if concept_ids:
        try:
            bkt_result = (
                supabase.table("concept_bkt_state")
                .select("concept_id, p_mastery")
                .eq("user_id", user_id)
                .in_("concept_id", concept_ids)
                .execute()
            )
            for row in bkt_result.data or []:
                bkt_map[row["concept_id"]] = row["p_mastery"]
        except Exception:
            logger.warning("Failed to fetch BKT states for lecture mastery", exc_info=True)

    # 4. Compute per-lecture stats
    results: list[dict] = []
    for lec in lectures:
        lec_concepts = concepts_by_lecture.get(lec["id"], [])
        concept_count = len(lec_concepts)
        if concept_count == 0:
            continue

        mastered = 0
        developing = 0
        unstarted = 0
        total_mastery = 0.0

        for cid in lec_concepts:
            p = bkt_map.get(cid)
            if p is None:
                unstarted += 1
                total_mastery += DEFAULT_P_MASTERY
            elif p >= 0.85:
                mastered += 1
                total_mastery += p
            else:
                developing += 1
                total_mastery += p

        results.append({
            "lecture_id": lec["id"],
            "title": lec.get("title", ""),
            "lecture_number": lec.get("lecture_number"),
            "lecture_date": lec.get("lecture_date"),
            "concept_count": concept_count,
            "mastered": mastered,
            "developing": developing,
            "unstarted": unstarted,
            "avg_mastery": round(total_mastery / concept_count, 4),
        })

    return results


async def get_lecture_concepts_for_study(
    supabase,
    user_id: str,
    lecture_id: str,
    limit: int = 5,
) -> list[dict]:
    """Fetch concepts from a lecture sorted by lowest p_mastery first.

    Returns enriched concept entries compatible with _enrich_concept pattern
    in learn_session.py:
        [{concept_id, concept_title, mastery_score, total_attempts, priority_score}]
    """
    # 1. Get concepts for this lecture
    try:
        concepts_result = (
            supabase.table("concepts")
            .select("id, title, course_id")
            .eq("lecture_id", lecture_id)
            .execute()
        )
        concepts = concepts_result.data or []
    except Exception:
        logger.warning("Failed to fetch concepts for lecture %s", lecture_id, exc_info=True)
        return []

    if not concepts:
        return []

    concept_ids = [c["id"] for c in concepts]

    # 2. Get BKT states
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
        logger.warning("Failed to fetch BKT states for lecture concepts", exc_info=True)

    # 3. Build enriched entries, sorted by weakest first
    entries: list[dict] = []
    for c in concepts:
        bkt = bkt_map.get(c["id"])
        p_mastery = bkt["p_mastery"] if bkt else DEFAULT_P_MASTERY
        total_attempts = bkt["total_attempts"] if bkt else 0
        entries.append({
            "concept_id": c["id"],
            "concept_title": c.get("title", ""),
            "mastery_score": round(p_mastery, 4),
            "total_attempts": total_attempts,
            "priority_score": round(1.0 - p_mastery, 4),
        })

    # Sort by weakest first (lowest mastery)
    entries.sort(key=lambda e: e["mastery_score"])

    return entries[:limit]
