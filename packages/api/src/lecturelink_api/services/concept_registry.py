"""Concept Registry — course-level concept deduplication engine.

When new concepts are extracted from a lecture, this service matches them
against the existing concept pool for the course. Duplicates merge into
existing rows; genuinely new concepts are inserted.

Matching algorithm (two-pass):
1. Title normalization (exact match via _normalize_title)
2. Embedding cosine similarity (>0.85 threshold, with LLM confirmation
   for borderline 0.85-0.95 matches)
"""

from __future__ import annotations

import logging

import numpy as np
from google.genai import types

from ..agents.concept_extractor import _normalize_title
from ..services.genai_client import get_genai_client

logger = logging.getLogger(__name__)

SIMILARITY_THRESHOLD = 0.85
AUTO_MERGE_THRESHOLD = 0.95  # Above this, skip LLM confirmation

MERGE_CONFIRMATION_PROMPT = """Are these two concepts the same topic?

Concept A: "{title_a}"
Description: {desc_a}

Concept B: "{title_b}"
Description: {desc_b}

Answer with ONLY "yes" or "no"."""


async def register_concepts(
    supabase,
    course_id: str,
    lecture_id: str,
    user_id: str,
    new_concepts: list[dict],
) -> dict:
    """Register extracted concepts into the course-level registry.

    For each new concept:
    1. Check title normalization match against existing course concepts
    2. If no title match, check embedding similarity
    3. For similarity 0.85-0.95, confirm via LLM
    4. Merge matches into existing rows; insert genuinely new ones

    Args:
        supabase: Supabase client.
        course_id: Course UUID.
        lecture_id: Lecture UUID (source of these concepts).
        user_id: Owner user UUID.
        new_concepts: List of extracted concepts with embeddings and
            source_chunk_ids already populated.

    Returns:
        {
            "merged": [{"concept_id": str, "matched_title": str, "new_title": str}, ...],
            "inserted": [{"concept_id": str, "title": str}, ...],
            "total_concepts_in_course": int,
        }
    """
    if not new_concepts:
        return {"merged": [], "inserted": [], "total_concepts_in_course": 0}

    # Fetch existing concepts for this course
    existing_result = (
        supabase.table("concepts")
        .select("id, title, description, embedding")
        .eq("course_id", course_id)
        .execute()
    )
    existing = existing_result.data or []

    # Build lookup structures
    existing_by_norm_title: dict[str, dict] = {}
    for ec in existing:
        norm = _normalize_title(ec["title"])
        if norm:
            existing_by_norm_title[norm] = ec

    # Build embedding matrix for existing concepts (for cosine similarity)
    existing_with_embeddings = [ec for ec in existing if ec.get("embedding")]
    existing_emb_matrix = None
    if existing_with_embeddings:
        existing_emb_matrix = np.array(
            [ec["embedding"] for ec in existing_with_embeddings]
        )
        norms = np.linalg.norm(existing_emb_matrix, axis=1, keepdims=True)
        norms = np.maximum(norms, 1e-10)
        existing_emb_matrix = existing_emb_matrix / norms

    merged: list[dict] = []
    inserted: list[dict] = []

    for concept in new_concepts:
        title = concept.get("title", "")
        norm_title = _normalize_title(title)

        # --- Pass 1: Title normalization match ---
        if norm_title in existing_by_norm_title:
            match = existing_by_norm_title[norm_title]
            await _merge_concept(
                supabase, match["id"], concept, lecture_id, user_id,
            )
            merged.append({
                "concept_id": match["id"],
                "matched_title": match["title"],
                "new_title": title,
            })
            continue

        # --- Pass 2: Embedding similarity match ---
        best_match = None
        if (
            existing_emb_matrix is not None
            and concept.get("embedding") is not None
        ):
            concept_emb = np.array(concept["embedding"])
            concept_norm = np.linalg.norm(concept_emb)
            if concept_norm > 1e-10:
                concept_emb_normalized = concept_emb / concept_norm
                similarities = existing_emb_matrix @ concept_emb_normalized
                max_idx = int(np.argmax(similarities))
                max_sim = float(similarities[max_idx])

                if max_sim >= AUTO_MERGE_THRESHOLD:
                    best_match = existing_with_embeddings[max_idx]
                elif max_sim >= SIMILARITY_THRESHOLD:
                    # Borderline — confirm with LLM
                    candidate = existing_with_embeddings[max_idx]
                    confirmed = await _confirm_merge(concept, candidate)
                    if confirmed:
                        best_match = candidate

        if best_match:
            await _merge_concept(
                supabase, best_match["id"], concept, lecture_id, user_id,
            )
            merged.append({
                "concept_id": best_match["id"],
                "matched_title": best_match["title"],
                "new_title": title,
            })
            # Update lookup so subsequent concepts can title-match
            existing_by_norm_title[norm_title] = best_match
            continue

        # --- No match: Insert as new concept ---
        new_id = await _insert_concept(
            supabase, course_id, lecture_id, user_id, concept,
        )
        inserted.append({"concept_id": new_id, "title": title})

        # Update lookup structures for subsequent concepts in this batch
        new_entry = {
            "id": new_id,
            "title": title,
            "description": concept.get("description", ""),
            "embedding": concept.get("embedding"),
        }
        existing_by_norm_title[norm_title] = new_entry

        if concept.get("embedding") is not None:
            new_emb = np.array(concept["embedding"])
            new_emb_norm = np.linalg.norm(new_emb)
            if new_emb_norm > 1e-10:
                new_emb_normalized = (new_emb / new_emb_norm).reshape(1, -1)
                if existing_emb_matrix is not None:
                    existing_emb_matrix = np.vstack(
                        [existing_emb_matrix, new_emb_normalized]
                    )
                else:
                    existing_emb_matrix = new_emb_normalized
                existing_with_embeddings.append(new_entry)

    total = len(existing) + len(inserted)

    logger.info(
        "Concept registry: %d merged, %d inserted, %d total for course %s",
        len(merged), len(inserted), total, course_id,
    )

    return {
        "merged": merged,
        "inserted": inserted,
        "total_concepts_in_course": total,
    }


async def _merge_concept(
    supabase,
    existing_id: str,
    new_concept: dict,
    lecture_id: str,
    user_id: str,
) -> None:
    """Merge a new concept into an existing concept row."""
    new_chunk_ids = new_concept.get("source_chunk_ids", [])

    # 1. Add concept_lectures junction entry
    supabase.table("concept_lectures").upsert(
        {
            "concept_id": existing_id,
            "lecture_id": lecture_id,
            "source_chunk_ids": new_chunk_ids,
        },
        on_conflict="concept_id,lecture_id",
    ).execute()

    # 2. Append raw title to merged_titles for audit trail
    new_title = new_concept.get("title", "")
    try:
        existing_row = (
            supabase.table("concepts")
            .select("merged_titles, description, source_chunk_ids")
            .eq("id", existing_id)
            .single()
            .execute()
        )
        current_titles = existing_row.data.get("merged_titles") or []
        if new_title not in current_titles:
            current_titles.append(new_title)

        # Union source_chunk_ids
        existing_chunks = existing_row.data.get("source_chunk_ids") or []
        merged_chunks = list(dict.fromkeys(existing_chunks + new_chunk_ids))

        # Use longer description if new one is more detailed
        update_data: dict = {
            "merged_titles": current_titles,
            "source_chunk_ids": merged_chunks,
        }
        new_desc = new_concept.get("description", "")
        existing_desc = existing_row.data.get("description", "")
        if len(new_desc) > len(existing_desc):
            update_data["description"] = new_desc

        supabase.table("concepts").update(update_data).eq(
            "id", existing_id
        ).execute()

    except Exception:
        logger.warning(
            "Failed to update merged_titles for concept %s", existing_id,
            exc_info=True,
        )


async def _insert_concept(
    supabase,
    course_id: str,
    lecture_id: str,
    user_id: str,
    concept: dict,
) -> str:
    """Insert a genuinely new concept and its junction entry."""
    # Ensure embedding is plain Python list[float] — numpy types break JSON serialization
    raw_emb = concept.get("embedding")
    embedding = [float(v) for v in raw_emb] if raw_emb is not None else None

    row = {
        "course_id": course_id,
        "lecture_id": lecture_id,
        "user_id": user_id,
        "title": concept["title"],
        "description": concept.get("description", ""),
        "category": concept.get("category", "concept"),
        "difficulty_estimate": concept.get("difficulty_estimate", 0.5),
        "source_chunk_ids": concept.get("source_chunk_ids", []),
        "embedding": embedding,
        "merged_titles": [concept["title"]],
        "subconcepts": [],
    }
    result = supabase.table("concepts").insert(row).execute()
    new_id = result.data[0]["id"]

    # Create junction entry
    supabase.table("concept_lectures").insert({
        "concept_id": new_id,
        "lecture_id": lecture_id,
        "source_chunk_ids": concept.get("source_chunk_ids", []),
    }).execute()

    return new_id


async def _confirm_merge(
    new_concept: dict,
    candidate: dict,
) -> bool:
    """Ask Gemini Flash to confirm whether two concepts are the same."""
    try:
        client = get_genai_client()
        prompt = MERGE_CONFIRMATION_PROMPT.format(
            title_a=new_concept.get("title", ""),
            desc_a=new_concept.get("description", "")[:200],
            title_b=candidate.get("title", ""),
            desc_b=candidate.get("description", "")[:200],
        )
        response = await client.aio.models.generate_content(
            model="gemini-2.5-flash",
            contents=[types.Content(role="user", parts=[types.Part(text=prompt)])],
            config=types.GenerateContentConfig(
                temperature=0.0,
                max_output_tokens=10,
            ),
        )
        answer = response.text.strip().lower()
        return answer.startswith("yes")
    except Exception:
        logger.warning("LLM merge confirmation failed, defaulting to no merge")
        return False
