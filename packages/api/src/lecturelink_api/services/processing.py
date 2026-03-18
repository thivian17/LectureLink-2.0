"""Lecture processing status helpers — used by all pipeline stages."""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

# Progress constants for each pipeline stage
STAGE_PROGRESS: dict[str, float] = {
    "uploading": 0.05,
    "transcribing": 0.15,
    "analyzing_slides": 0.30,
    "aligning": 0.45,
    "extracting_concepts": 0.60,
    "generating_embeddings": 0.85,
    "completed": 1.0,
}


def update_processing_status(
    supabase,
    lecture_id: str,
    status: str,
    *,
    stage: str | None = None,
    progress: float | None = None,
    error: str | None = None,
) -> None:
    """Update lecture processing status in the database.

    Args:
        supabase: Supabase client instance.
        lecture_id: The lecture UUID.
        status: One of ``pending``, ``processing``, ``completed``, ``failed``.
        stage: Current pipeline stage name (optional).
        progress: 0.0–1.0 progress percentage (optional).
        error: Error message if status is ``failed`` (optional).
    """
    update_data: dict = {"processing_status": status}
    if stage is not None:
        update_data["processing_stage"] = stage
    if progress is not None:
        update_data["processing_progress"] = progress
    if error is not None:
        update_data["processing_error"] = error

    logger.info(
        "Updating lecture %s: status=%s stage=%s progress=%s",
        lecture_id,
        status,
        stage,
        progress,
    )

    supabase.table("lectures").update(update_data).eq("id", lecture_id).execute()
