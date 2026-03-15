"""Lecture storage — persist processed chunks and concepts to the database."""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


def store_chunks(
    supabase,
    lecture_id: str,
    user_id: str,
    chunks: list[dict],
) -> list[dict]:
    """Store lecture chunks in the database.

    Args:
        supabase: Supabase client.
        lecture_id: Parent lecture UUID.
        user_id: Owner user UUID.
        chunks: List of processed chunks with embeddings.

    Returns:
        List of stored chunks with database-assigned IDs.

    IMPORTANT: The 'fts' column is a GENERATED column — do NOT include it.
    """
    if not chunks:
        return []

    rows = []
    for chunk in chunks:
        row = {
            "lecture_id": lecture_id,
            "user_id": user_id,
            "chunk_index": chunk["chunk_index"],
            "content": chunk["content"],
            "start_time": chunk.get("start_time"),
            "end_time": chunk.get("end_time"),
            "slide_number": chunk.get("slide_number"),
            "embedding": chunk.get("embedding"),
            "metadata": chunk.get("metadata", {}),
            # Do NOT include 'fts' — it's a GENERATED column
        }
        rows.append(row)

    result = supabase.table("lecture_chunks").insert(rows).execute()

    logger.info("Stored %d chunks for lecture %s", len(result.data), lecture_id)
    return result.data


def store_concepts(
    supabase,
    lecture_id: str,
    course_id: str,
    user_id: str,
    concepts: list[dict],
) -> list[dict]:
    """Store extracted concepts in the database.

    Args:
        supabase: Supabase client.
        lecture_id: Parent lecture UUID.
        course_id: Parent course UUID.
        user_id: Owner user UUID.
        concepts: List of extracted concepts with embeddings and source_chunk_ids.

    Returns:
        List of stored concepts with database-assigned IDs.
    """
    if not concepts:
        return []

    rows = []
    for concept in concepts:
        row = {
            "lecture_id": lecture_id,
            "course_id": course_id,
            "user_id": user_id,
            "title": concept["title"],
            "description": concept.get("description", ""),
            "category": concept.get("category", "concept"),
            "difficulty_estimate": concept.get("difficulty_estimate", 0.5),
            "source_chunk_ids": concept.get("source_chunk_ids", []),
            "embedding": concept.get("embedding"),
            "subconcepts": concept.get("subconcepts", []),
        }
        rows.append(row)

    result = supabase.table("concepts").insert(rows).execute()

    logger.info(
        "Stored %d concepts for lecture %s", len(result.data), lecture_id
    )
    return result.data


def cleanup_lecture_data(supabase, lecture_id: str) -> None:
    """Delete lecture-specific data for reprocessing.

    With the concept registry, concepts may be shared across lectures.
    Only delete concepts that are exclusively linked to this lecture (orphans).
    Shared concepts retain their rows — only the junction entry is removed.

    Deletion order (FK constraints):
    1. concept_lectures entries for this lecture
    2. concept_assessment_links for orphan concepts
    3. orphan concept rows
    4. lecture_chunks
    """
    # 1. Find orphan concepts BEFORE removing junction entries
    orphan_ids = []
    try:
        orphan_result = supabase.rpc(
            "get_orphan_concepts_for_lecture",
            {"p_lecture_id": lecture_id},
        ).execute()
        orphan_ids = [c["id"] for c in (orphan_result.data or [])]
    except Exception:
        # Fallback: if the RPC doesn't exist yet (pre-migration),
        # use the legacy behavior of deleting all concepts for the lecture
        logger.warning(
            "get_orphan_concepts_for_lecture RPC unavailable, "
            "falling back to legacy cleanup for lecture %s",
            lecture_id,
        )
        _legacy_cleanup(supabase, lecture_id)
        return

    # 2. Remove concept_lectures entries for this lecture
    try:
        supabase.table("concept_lectures").delete().eq(
            "lecture_id", lecture_id
        ).execute()
    except Exception:
        logger.warning(
            "concept_lectures cleanup failed for lecture %s",
            lecture_id, exc_info=True,
        )

    # 3. Delete orphan concepts (and their assessment links)
    if orphan_ids:
        (
            supabase.table("concept_assessment_links")
            .delete()
            .in_("concept_id", orphan_ids)
            .execute()
        )
        (
            supabase.table("concepts")
            .delete()
            .in_("id", orphan_ids)
            .execute()
        )

    # 4. Delete chunks (always lecture-specific)
    (
        supabase.table("lecture_chunks")
        .delete()
        .eq("lecture_id", lecture_id)
        .execute()
    )

    logger.info(
        "Cleaned up lecture %s: %d orphan concepts deleted, "
        "shared concepts preserved",
        lecture_id, len(orphan_ids),
    )


def _legacy_cleanup(supabase, lecture_id: str) -> None:
    """Pre-migration cleanup path — deletes all concepts for a lecture."""
    concepts = (
        supabase.table("concepts")
        .select("id")
        .eq("lecture_id", lecture_id)
        .execute()
    )
    concept_ids = [c["id"] for c in concepts.data]

    if concept_ids:
        (
            supabase.table("concept_assessment_links")
            .delete()
            .in_("concept_id", concept_ids)
            .execute()
        )

    supabase.table("concepts").delete().eq("lecture_id", lecture_id).execute()
    supabase.table("lecture_chunks").delete().eq("lecture_id", lecture_id).execute()

    logger.info("Legacy cleanup for lecture %s: %d concepts deleted", lecture_id, len(concept_ids))
