"""Material storage — persists extracted chunks and updates material records."""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


def store_material_chunks(
    supabase,
    material_id: str,
    course_id: str,
    user_id: str,
    chunks: list[dict],
) -> int:
    """Store extracted and embedded chunks for a material.

    Args:
        supabase: Supabase client.
        material_id: The material UUID.
        course_id: The course UUID.
        user_id: The owner user UUID.
        chunks: List of dicts with keys: chunk_index, content, page_number,
                section_title, embedding (list[float]), metadata.

    Returns:
        Number of chunks stored.
    """
    if not chunks:
        return 0

    rows = []
    for chunk in chunks:
        row = {
            "material_id": material_id,
            "course_id": course_id,
            "user_id": user_id,
            "chunk_index": chunk["chunk_index"],
            "content": chunk["content"],
            "page_number": chunk.get("page_number"),
            "section_title": chunk.get("section_title"),
            "metadata": chunk.get("metadata", {}),
        }
        if chunk.get("embedding"):
            row["embedding"] = chunk["embedding"]
        rows.append(row)

    result = supabase.table("material_chunks").insert(rows).execute()
    stored = len(result.data) if result.data else 0
    logger.info("Stored %d material chunks for material %s", stored, material_id)
    return stored


def update_material_status(
    supabase,
    material_id: str,
    status: str,
    *,
    stage: str | None = None,
    progress: float | None = None,
    error: str | None = None,
    concept_count: int | None = None,
    chunk_count: int | None = None,
    extracted_text_preview: str | None = None,
    page_count: int | None = None,
    title: str | None = None,
) -> None:
    """Update material processing status in the database."""
    update_data: dict = {
        "processing_status": status,
        "updated_at": "now()",
    }
    if stage is not None:
        update_data["processing_stage"] = stage
    if progress is not None:
        update_data["processing_progress"] = progress
    if error is not None:
        update_data["processing_error"] = error
    if concept_count is not None:
        update_data["concept_count"] = concept_count
    if chunk_count is not None:
        update_data["chunk_count"] = chunk_count
    if extracted_text_preview is not None:
        update_data["extracted_text_preview"] = extracted_text_preview
    if page_count is not None:
        update_data["page_count"] = page_count
    if title is not None:
        update_data["title"] = title

    logger.info(
        "Updating material %s: status=%s stage=%s progress=%s",
        material_id,
        status,
        stage,
        progress,
    )
    supabase.table("course_materials").update(update_data).eq(
        "id", material_id
    ).execute()


def cleanup_material_data(supabase, material_id: str) -> None:
    """Delete all processed data for a material (for reprocessing)."""
    supabase.table("material_chunks").delete().eq(
        "material_id", material_id
    ).execute()
    # Reset processing fields
    supabase.table("course_materials").update(
        {
            "processing_status": "pending",
            "processing_stage": None,
            "processing_progress": 0.0,
            "processing_error": None,
            "concept_count": 0,
            "chunk_count": 0,
            "extracted_text_preview": None,
        }
    ).eq("id", material_id).execute()
    logger.info("Cleaned up data for material %s", material_id)
