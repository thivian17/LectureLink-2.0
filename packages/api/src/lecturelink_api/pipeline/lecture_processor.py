"""Lecture Processing Pipeline — wires all stages into an end-to-end orchestrator.

Stages:
1. Input Router — classify files, determine processing path
2. Content Processing — transcribe audio + analyze slides (parallel)
3. Content Alignment — align transcript to slides
4. Concept Extraction — extract key concepts (Gemini Pro)
5. Chunking + Embedding — chunk content, generate embeddings
6. Concept-Chunk Linking — link concepts to source chunks
7. Concept Mapping — bridge lecture concepts to syllabus assessments
"""

from __future__ import annotations

import asyncio
import logging
import traceback
from datetime import datetime

from ..agents.audio_transcriber import TranscriptionError, transcribe_audio
from ..agents.chunker import EmbeddingError, chunk_content, embed_chunks, embed_concepts
from ..agents.concept_chunk_linker import link_concepts_to_chunks
from ..agents.concept_extractor import ConceptExtractionError, extract_concepts
from ..agents.concept_mapper import map_concepts_to_assessments
from ..agents.content_aligner import align_content
from ..agents.input_router import route_input
from ..agents.slide_analyzer import SlideAnalysisError, analyze_slides
from ..services.lecture_storage import cleanup_lecture_data, store_chunks, store_concepts
from ..services.processing import STAGE_PROGRESS, update_processing_status

logger = logging.getLogger(__name__)


class LectureProcessingError(Exception):
    """Raised when the lecture processing pipeline fails."""

    def __init__(self, message: str, stage: str):
        self.stage = stage
        super().__init__(f"[{stage}] {message}")


async def process_lecture(
    supabase,
    lecture_id: str,
    course_id: str,
    user_id: str,
    file_urls: list[str],
    is_reprocess: bool = False,
) -> dict:
    """Run the full lecture processing pipeline.

    Args:
        supabase: Supabase client.
        lecture_id: The lecture UUID.
        course_id: The course UUID.
        user_id: The owner user UUID.
        file_urls: List of uploaded file URLs (Supabase Storage).
        is_reprocess: If True, clean up existing data first.

    Returns:
        Dict with lecture_id, chunks_stored, concepts_stored, concept_links_created,
        processing_path, and duration_seconds.
    """
    start_time = datetime.utcnow()

    try:
        # If reprocessing, clean up old data first
        if is_reprocess:
            cleanup_lecture_data(supabase, lecture_id)

        # ── Stage 1: Input Router ──
        update_processing_status(
            supabase, lecture_id, "processing",
            stage="uploading", progress=STAGE_PROGRESS["uploading"],
        )
        route_result = await route_input(file_urls)
        processing_path = route_result.processing_path
        logger.info("Lecture %s: routing -> %s", lecture_id, processing_path)

        # ── Stage 2: Content Processing (Parallel) ──
        transcript_segments = None
        slide_analysis = None

        if processing_path in ("audio_only", "audio+slides"):
            update_processing_status(
                supabase, lecture_id, "processing",
                stage="transcribing", progress=STAGE_PROGRESS["transcribing"],
            )

        if processing_path in ("slides_only", "audio+slides"):
            update_processing_status(
                supabase, lecture_id, "processing",
                stage="analyzing_slides",
                progress=STAGE_PROGRESS["analyzing_slides"],
            )

        # Run audio + slides in parallel when both exist
        if processing_path == "audio+slides":
            transcript_segments, slide_analysis = await asyncio.gather(
                transcribe_audio(route_result.audio_url),
                analyze_slides(route_result.slides_url),
            )
        elif processing_path == "audio_only":
            transcript_segments = await transcribe_audio(route_result.audio_url)
        elif processing_path == "slides_only":
            slide_analysis = await analyze_slides(route_result.slides_url)

        # ── Stage 3: Content Alignment ──
        update_processing_status(
            supabase, lecture_id, "processing",
            stage="aligning", progress=STAGE_PROGRESS["aligning"],
        )
        aligned_segments = await align_content(transcript_segments, slide_analysis)
        logger.info("Lecture %s: aligned %d segments", lecture_id, len(aligned_segments))

        # Calculate duration from transcript timestamps
        duration_seconds = None
        if transcript_segments:
            duration_seconds = max(
                (seg.get("end", 0) for seg in transcript_segments), default=None
            )

        # ── Stage 4: Concept Extraction ──
        update_processing_status(
            supabase, lecture_id, "processing",
            stage="extracting_concepts",
            progress=STAGE_PROGRESS["extracting_concepts"],
        )
        concepts = await extract_concepts(aligned_segments)
        logger.info("Lecture %s: extracted %d concepts", lecture_id, len(concepts))

        # ── Stage 5: Chunking + Embedding ──
        update_processing_status(
            supabase, lecture_id, "processing",
            stage="generating_embeddings",
            progress=STAGE_PROGRESS["generating_embeddings"],
        )
        chunks = chunk_content(aligned_segments)
        chunks = await embed_chunks(chunks)
        concepts = await embed_concepts(concepts)
        logger.info(
            "Lecture %s: embedded %d chunks, %d concepts",
            lecture_id, len(chunks), len(concepts),
        )

        # ── Stage 6: Concept-Chunk Linking + Storage ──
        # Store chunks first to get database IDs
        stored_chunks = store_chunks(supabase, lecture_id, user_id, chunks)

        # Update chunk IDs from database response
        for chunk, stored in zip(chunks, stored_chunks, strict=False):
            chunk["id"] = stored["id"]

        # Link concepts to stored chunks using real IDs
        concepts = link_concepts_to_chunks(concepts, chunks, top_k=5)

        # Store concepts
        stored_concepts = store_concepts(
            supabase, lecture_id, course_id, user_id, concepts,
        )

        # ── Stage 7: Concept Mapping (bridge to syllabus) ──
        update_processing_status(
            supabase, lecture_id, "processing",
            stage="mapping_concepts",
            progress=STAGE_PROGRESS["mapping_concepts"],
        )

        # Get lecture metadata for mapping context
        lecture_data = (
            supabase.table("lectures")
            .select("lecture_date, lecture_number")
            .eq("id", lecture_id)
            .execute()
        )

        lec_meta = lecture_data.data[0] if lecture_data.data else {}
        concept_links = await map_concepts_to_assessments(
            supabase=supabase,
            lecture_id=lecture_id,
            course_id=course_id,
            user_id=user_id,
            concepts=stored_concepts,
            lecture_date=lec_meta.get("lecture_date"),
            lecture_number=lec_meta.get("lecture_number"),
        )
        logger.info(
            "Lecture %s: created %d concept-assessment links",
            lecture_id, len(concept_links),
        )

        # ── Update lecture record ──
        full_transcript = "\n".join(
            seg["text"] for seg in aligned_segments if seg.get("text")
        )

        update_data = {
            "processing_status": "completed",
            "processing_stage": "completed",
            "processing_progress": 1.0,
            "processing_error": None,
            "transcript": full_transcript[:50000],
        }
        if duration_seconds:
            update_data["duration_seconds"] = int(duration_seconds)

        (
            supabase.table("lectures")
            .update(update_data)
            .eq("id", lecture_id)
            .execute()
        )

        elapsed = (datetime.utcnow() - start_time).total_seconds()
        logger.info("Lecture %s: processing complete in %.1fs", lecture_id, elapsed)

        return {
            "lecture_id": lecture_id,
            "chunks_stored": len(stored_chunks),
            "concepts_stored": len(stored_concepts),
            "concept_links_created": len(concept_links),
            "processing_path": processing_path,
            "duration_seconds": elapsed,
        }

    except (TranscriptionError, SlideAnalysisError) as e:
        _handle_failure(supabase, lecture_id, str(e), "content_processing")
        raise LectureProcessingError(str(e), "content_processing") from e

    except ConceptExtractionError as e:
        _handle_failure(
            supabase, lecture_id, str(e), "extracting_concepts",
        )
        raise LectureProcessingError(str(e), "extracting_concepts") from e

    except EmbeddingError as e:
        _handle_failure(
            supabase, lecture_id, str(e), "generating_embeddings",
        )
        raise LectureProcessingError(str(e), "generating_embeddings") from e

    except LectureProcessingError:
        raise

    except Exception as e:
        logger.error("FULL TRACEBACK:\n%s", traceback.format_exc())
        _handle_failure(supabase, lecture_id, str(e), "unknown")
        raise LectureProcessingError(str(e), "unknown") from e


def _handle_failure(
    supabase, lecture_id: str, error: str, stage: str,
) -> None:
    """Mark lecture as failed and log the error."""
    logger.error("Lecture %s failed at %s: %s", lecture_id, stage, error)
    try:
        update_processing_status(
            supabase, lecture_id,
            status="failed",
            stage=stage,
            error=error[:1000],
        )
        (
            supabase.rpc("increment_retry_count", {"p_lecture_id": lecture_id})
            .execute()
        )
    except Exception as update_err:
        logger.error("Failed to update failure status: %s", update_err)
