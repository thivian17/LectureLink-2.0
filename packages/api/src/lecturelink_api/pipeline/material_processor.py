"""Material Processing Pipeline — 4-stage processor for course materials.

Stages:
1. File Validation — validate file type, determine extraction method
2. Text Extraction — extract text via Gemini vision or direct parsing
3. Chunking + Embedding — chunk text, generate 2000-dim embeddings
4. Storage — persist chunks and update material record
"""

from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path

from ..agents.chunker import chunk_content, embed_chunks
from ..agents.material_extractor import MaterialExtractionError, extract_material_text
from ..models.material_models import ALLOWED_MATERIAL_EXTENSIONS
from ..services.material_storage import (
    cleanup_material_data,
    store_material_chunks,
    update_material_status,
)

logger = logging.getLogger(__name__)

STAGE_PROGRESS: dict[str, float] = {
    "validating": 0.05,
    "extracting_text": 0.20,
    "chunking": 0.50,
    "embedding": 0.75,
    "storing": 0.90,
    "completed": 1.0,
}


class MaterialProcessingError(Exception):
    """Raised when material processing fails."""

    def __init__(self, message: str, stage: str):
        self.stage = stage
        super().__init__(f"[{stage}] {message}")


def _text_to_segments(text: str, section_title: str | None = None) -> list[dict]:
    """Convert plain text into aligned_segments format for chunk_content().

    chunk_content() expects list[dict] with keys: text, start, end, speaker,
    slide_number, source. We create fake segments by splitting on paragraphs.
    """
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    if not paragraphs:
        paragraphs = [p.strip() for p in text.split("\n") if p.strip()]
    if not paragraphs and text.strip():
        paragraphs = [text.strip()]

    segments = []
    for para in paragraphs:
        segments.append({
            "text": para,
            "start": None,
            "end": None,
            "speaker": "document",
            "slide_number": None,
            "source": "material",
        })
    return segments


async def process_material(
    supabase,
    material_id: str,
    course_id: str,
    user_id: str,
    file_url: str,
    file_name: str,
    material_type: str,
    title: str | None = None,
    is_reprocess: bool = False,
) -> dict:
    """Run the material processing pipeline.

    Args:
        supabase: Supabase client.
        material_id: The material UUID.
        course_id: The course UUID.
        user_id: The owner user UUID.
        file_url: Supabase storage URL for the uploaded file.
        file_name: Original file name.
        material_type: Type of material (reading, homework, etc.).
        title: Optional title (auto-generated if None).
        is_reprocess: If True, clean up existing data first.

    Returns:
        Dict with material_id, chunks_stored, duration_seconds.
    """
    start_time = datetime.utcnow()

    try:
        if is_reprocess:
            cleanup_material_data(supabase, material_id)

        # ── Stage 1: File Validation ──
        update_material_status(
            supabase,
            material_id,
            "processing",
            stage="validating",
            progress=STAGE_PROGRESS["validating"],
        )
        file_ext = Path(file_name).suffix.lower()
        if file_ext not in ALLOWED_MATERIAL_EXTENSIONS:
            raise MaterialProcessingError(
                f"Unsupported file type: {file_ext}", "validating"
            )

        # ── Stage 2: Text Extraction ──
        update_material_status(
            supabase,
            material_id,
            "processing",
            stage="extracting_text",
            progress=STAGE_PROGRESS["extracting_text"],
        )
        extraction = await extract_material_text(file_url, file_ext)

        full_text = extraction.get("full_text", "")
        if not full_text or len(full_text.strip()) < 50:
            raise MaterialProcessingError(
                "Extracted text is too short or empty", "extracting_text"
            )

        # Auto-generate title if not provided
        auto_title = title or extraction.get("title") or f"Material — {file_name}"
        preview = full_text[:500]
        page_count = extraction.get("page_count")

        update_material_status(
            supabase,
            material_id,
            "processing",
            stage="extracting_text",
            progress=0.30,
            extracted_text_preview=preview,
            page_count=page_count,
            title=auto_title,
        )

        # ── Stage 3: Chunking ──
        update_material_status(
            supabase,
            material_id,
            "processing",
            stage="chunking",
            progress=STAGE_PROGRESS["chunking"],
        )

        # Build chunks — use extracted sections if available for better context
        sections = extraction.get("sections", [])
        all_chunks: list[dict] = []
        idx = 0

        if sections:
            for section in sections:
                content = section.get("content", "")
                if not content.strip():
                    continue
                segments = _text_to_segments(content, section.get("title"))
                section_chunks = chunk_content(segments)
                for chunk in section_chunks:
                    chunk["chunk_index"] = idx
                    chunk["page_number"] = section.get("page_number")
                    chunk["section_title"] = section.get("title")
                    all_chunks.append(chunk)
                    idx += 1
        else:
            segments = _text_to_segments(full_text)
            all_chunks = chunk_content(segments)
            for i, chunk in enumerate(all_chunks):
                chunk["chunk_index"] = i

        if not all_chunks:
            raise MaterialProcessingError(
                "No chunks produced from extracted text", "chunking"
            )

        # ── Stage 3b: Embedding ──
        update_material_status(
            supabase,
            material_id,
            "processing",
            stage="embedding",
            progress=STAGE_PROGRESS["embedding"],
        )
        embedded_chunks = await embed_chunks(all_chunks)

        # ── Stage 4: Storage ──
        update_material_status(
            supabase,
            material_id,
            "processing",
            stage="storing",
            progress=STAGE_PROGRESS["storing"],
        )
        chunks_stored = store_material_chunks(
            supabase,
            material_id,
            course_id,
            user_id,
            embedded_chunks,
        )

        # ── Complete ──
        duration = (datetime.utcnow() - start_time).total_seconds()
        update_material_status(
            supabase,
            material_id,
            "completed",
            stage="completed",
            progress=STAGE_PROGRESS["completed"],
            chunk_count=chunks_stored,
        )

        logger.info(
            "Material %s processed: %d chunks in %.1fs",
            material_id,
            chunks_stored,
            duration,
        )
        return {
            "material_id": material_id,
            "chunks_stored": chunks_stored,
            "duration_seconds": round(duration, 1),
        }

    except MaterialProcessingError:
        raise
    except MaterialExtractionError as e:
        raise MaterialProcessingError(str(e), "extracting_text") from e
    except Exception as e:
        raise MaterialProcessingError(str(e), "unknown") from e
