"""Deterministic chunk fetcher for Learn Mode.

Fetches lecture chunks using pre-computed source_chunk_ids from the concepts
table (created during lecture processing). Falls back to hybrid_search only
when source_chunk_ids is empty or the concept row can't be found.

This replaces ad-hoc search_lectures() calls throughout Learn Mode services,
ensuring content is grounded in the same chunks that were semantically linked
during the lecture processing pipeline.
"""

from __future__ import annotations

import logging

from .search import search_lectures

logger = logging.getLogger(__name__)


async def fetch_concept_chunks(
    supabase,
    concept_id: str,
    course_id: str,
    *,
    limit: int = 5,
    concept_title: str = "",
) -> list[dict]:
    """Fetch lecture chunks for a concept, preferring pre-linked source_chunk_ids.

    Resolution order:
    1. Read source_chunk_ids from concept_lectures junction (multi-lecture)
    2. Fall back to concepts.source_chunk_ids (single-lecture, backward compat)
    3. Fall back to hybrid_search (non-deterministic)

    Args:
        supabase: Supabase client.
        concept_id: UUID of the concept.
        course_id: UUID of the course (needed for search fallback).
        limit: Max chunks to return (default 5, matching pipeline top_k).
        concept_title: Concept title string, used only for search fallback.

    Returns:
        List of chunk dicts with at minimum: id, content, lecture_id.
        May also include: start_time, end_time, slide_number, metadata.
    """
    # --- Path 1a: Junction table (cross-lecture chunks) ---
    all_chunk_ids: list[str] = []
    try:
        cl_result = (
            supabase.table("concept_lectures")
            .select("source_chunk_ids")
            .eq("concept_id", concept_id)
            .execute()
        )
        for row in (cl_result.data or []):
            all_chunk_ids.extend(row.get("source_chunk_ids") or [])
    except Exception:
        logger.debug(
            "concept_lectures query failed for concept %s, "
            "falling back to concepts table",
            concept_id,
        )

    # Deduplicate while preserving order
    if all_chunk_ids:
        unique_ids = list(dict.fromkeys(all_chunk_ids))[:limit]
        try:
            chunk_result = (
                supabase.table("lecture_chunks")
                .select("id, content, lecture_id, start_time, end_time, slide_number, metadata, lectures(title)")
                .in_("id", unique_ids)
                .execute()
            )
            chunks = chunk_result.data or []
            for chunk in chunks:
                lecture_rel = chunk.pop("lectures", None)
                if lecture_rel and isinstance(lecture_rel, dict):
                    chunk["lecture_title"] = lecture_rel.get("title", "")
            if chunks:
                logger.debug(
                    "Fetched %d cross-lecture chunks for concept %s",
                    len(chunks), concept_id,
                )
                return chunks
        except Exception:
            logger.warning(
                "Failed to fetch chunks from junction for concept %s",
                concept_id, exc_info=True,
            )

    # --- Path 1b: concepts.source_chunk_ids (backward compat) ---
    source_chunk_ids: list[str] = []
    try:
        concept_row = (
            supabase.table("concepts")
            .select("source_chunk_ids")
            .eq("id", concept_id)
            .single()
            .execute()
        )
        source_chunk_ids = (concept_row.data or {}).get("source_chunk_ids") or []
    except Exception:
        logger.debug("Failed to fetch source_chunk_ids for concept %s", concept_id)

    if source_chunk_ids:
        try:
            chunk_result = (
                supabase.table("lecture_chunks")
                .select("id, content, lecture_id, start_time, end_time, slide_number, metadata, lectures(title)")
                .in_("id", source_chunk_ids[:limit])
                .execute()
            )
            chunks = chunk_result.data or []
            # Flatten the joined lecture title into each chunk
            for chunk in chunks:
                lecture_rel = chunk.pop("lectures", None)
                if lecture_rel and isinstance(lecture_rel, dict):
                    chunk["lecture_title"] = lecture_rel.get("title", "")
            if chunks:
                logger.debug(
                    "Fetched %d/%d pre-linked chunks for concept %s",
                    len(chunks), len(source_chunk_ids), concept_id,
                )
                return chunks
        except Exception:
            logger.warning(
                "Failed to fetch chunks by ID for concept %s, falling back to search",
                concept_id,
                exc_info=True,
            )

    # --- Path 2: Fallback (hybrid search) ---
    query = concept_title or concept_id
    if not query.strip():
        logger.warning("No concept_title or concept_id for search fallback")
        return []

    try:
        return await search_lectures(
            supabase=supabase,
            course_id=course_id,
            query=query,
            limit=limit,
        )
    except Exception:
        logger.warning("Search fallback also failed for concept %s", concept_id, exc_info=True)
        return []


async def fetch_chunks_for_concepts(
    supabase,
    concepts: list[dict],
    course_id: str,
    *,
    per_concept_limit: int = 3,
) -> list[dict]:
    """Fetch and aggregate chunks for multiple concepts.

    Useful for power quiz generation where you need grounding material
    across all session concepts.

    Args:
        supabase: Supabase client.
        concepts: List of dicts with 'concept_id' and optionally 'title'.
        course_id: UUID of the course.
        per_concept_limit: Max chunks per concept.

    Returns:
        Deduplicated list of chunk dicts.
    """
    seen_ids: set[str] = set()
    all_chunks: list[dict] = []

    for concept in concepts:
        cid = concept.get("concept_id", "")
        title = concept.get("title", "") or concept.get("concept_title", "")
        if not cid and not title:
            continue

        chunks = await fetch_concept_chunks(
            supabase,
            concept_id=cid,
            course_id=course_id,
            limit=per_concept_limit,
            concept_title=title,
        )
        for chunk in chunks:
            chunk_id = chunk.get("id", "")
            if chunk_id and chunk_id not in seen_ids:
                seen_ids.add(chunk_id)
                all_chunks.append(chunk)
            elif not chunk_id:
                all_chunks.append(chunk)

    return all_chunks
