"""Spaced repetition service — BKT-driven priority concept selection.

Provides the intelligence layer: BKT mastery drives study recommendations
for ALL concepts, independent of assessments.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime

from .mastery import DEFAULT_P_MASTERY

logger = logging.getLogger(__name__)

# Mastery threshold for "mastered" concepts
MASTERY_THRESHOLD = 0.85
# Days before mastered concepts re-enter the queue
MASTERY_REFRESH_DAYS = 14


async def get_priority_concepts(
    supabase,
    user_id: str,
    course_id: str,
    limit: int = 10,
) -> list[dict]:
    """Get priority concepts for study based on BKT mastery and recency.

    Priority formula: (1 - p_mastery) * 0.6 + days_decay * 0.4
    Excludes mastered concepts (p_mastery >= 0.85) unless not reviewed in 14+ days.

    Returns concepts sorted by priority descending:
        [{concept_id, concept_title, mastery_score, total_attempts,
          priority_score, days_since_review}]
    """
    # 1. Get all concepts for the course
    try:
        concepts_result = (
            supabase.table("concepts")
            .select("id, title")
            .eq("course_id", course_id)
            .execute()
        )
        all_concepts = concepts_result.data or []
    except Exception:
        logger.warning("Failed to fetch concepts for spaced repetition", exc_info=True)
        return []

    if not all_concepts:
        return []

    concept_ids = [c["id"] for c in all_concepts]
    title_map = {c["id"]: c.get("title", "") for c in all_concepts}

    # 2. Get BKT states
    bkt_map: dict[str, dict] = {}
    try:
        bkt_result = (
            supabase.table("concept_bkt_state")
            .select("concept_id, p_mastery, total_attempts, last_updated")
            .eq("user_id", user_id)
            .in_("concept_id", concept_ids)
            .execute()
        )
        for row in bkt_result.data or []:
            bkt_map[row["concept_id"]] = row
    except Exception:
        logger.warning("Failed to fetch BKT states for spaced rep", exc_info=True)

    # 3. Compute priority for each concept
    now = datetime.now(UTC)
    entries: list[dict] = []

    for cid in concept_ids:
        bkt = bkt_map.get(cid)
        if bkt:
            p_mastery = bkt["p_mastery"]
            total_attempts = bkt["total_attempts"]
            last_updated = bkt.get("last_updated")

            # Compute days since last review
            days_since = 0
            if last_updated:
                try:
                    dt = datetime.fromisoformat(str(last_updated))
                    if dt.tzinfo is None:
                        dt = dt.replace(tzinfo=UTC)
                    days_since = max(0, (now - dt).days)
                except (ValueError, TypeError):
                    days_since = 0

            # Skip mastered concepts unless stale
            if p_mastery >= MASTERY_THRESHOLD and days_since < MASTERY_REFRESH_DAYS:
                continue
        else:
            # Never studied — high priority
            p_mastery = DEFAULT_P_MASTERY
            total_attempts = 0
            days_since = 999  # never reviewed

        # Priority: (1 - mastery) * 0.6 + days_decay * 0.4
        # days_decay: 0 days → 0.0, 7+ days → 1.0
        days_decay = min(1.0, days_since / 7.0)
        priority = (1.0 - p_mastery) * 0.6 + days_decay * 0.4

        entries.append({
            "concept_id": cid,
            "concept_title": title_map.get(cid, ""),
            "mastery_score": round(p_mastery, 4),
            "total_attempts": total_attempts,
            "priority_score": round(priority, 4),
            "days_since_review": days_since,
        })

    # Sort by priority descending
    entries.sort(key=lambda e: e["priority_score"], reverse=True)
    return entries[:limit]
