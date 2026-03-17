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
from ..agents.concept_extractor import (
    ConceptExtractionError,
    extract_concepts_v2,
    format_existing_concepts_for_prompt,
)
from ..services.concept_registry import register_concepts
from ..agents.concept_mapper import map_concepts_to_assessments
from ..agents.content_aligner import align_content
from ..agents.input_router import route_input
from ..agents.slide_analyzer import SlideAnalysisError, analyze_slides
from ..agents.title_generator import generate_title
from ..services.lecture_storage import cleanup_lecture_data, store_chunks
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
        Dict with lecture_id, chunks_stored, concepts_merged, concepts_inserted,
        concepts_total, concept_links_created, processing_path, and duration_seconds.
    """
    start_time = datetime.utcnow()

    # LangFuse trace — wraps the full pipeline
    lf = None
    trace = None
    try:
        from ..services.observability import get_langfuse

        lf = get_langfuse()
        if lf:
            trace = lf.trace(
                name="lecture_processing",
                user_id=user_id,
                metadata={
                    "lecture_id": lecture_id,
                    "course_id": course_id,
                    "is_reprocess": is_reprocess,
                },
            )
    except Exception:
        pass  # observability is always non-fatal

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
        _audio_span = None
        _slide_span = None
        try:
            if trace and processing_path in ("audio_only", "audio+slides"):
                _audio_span = trace.span(name="audio_transcription")
            if trace and processing_path in ("slides_only", "audio+slides"):
                _slide_span = trace.span(name="slide_analysis")
        except Exception:
            pass

        if processing_path == "audio+slides":
            transcript_segments, slide_analysis = await asyncio.gather(
                transcribe_audio(route_result.audio_url),
                analyze_slides(route_result.slides_url),
            )
        elif processing_path == "audio_only":
            transcript_segments = await transcribe_audio(route_result.audio_url)
        elif processing_path == "slides_only":
            slide_analysis = await analyze_slides(route_result.slides_url)

        try:
            if _audio_span and transcript_segments:
                _audio_span.end(output={"segments": len(transcript_segments)})
            if _slide_span and slide_analysis:
                _slide_span.end(output={"slides_analyzed": True})
        except Exception:
            pass

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

        # ── Stage 4: Concept Extraction (V2 — dedup-aware) + Title Generation ──
        update_processing_status(
            supabase, lecture_id, "processing",
            stage="extracting_concepts",
            progress=STAGE_PROGRESS["extracting_concepts"],
        )

        # Fetch existing course concepts for dedup awareness
        existing_concepts_data = []
        try:
            existing_result = (
                supabase.table("concepts")
                .select("title, description")
                .eq("course_id", course_id)
                .order("title")
                .execute()
            )
            existing_concepts_data = existing_result.data or []
        except Exception:
            logger.debug("Failed to fetch existing concepts for dedup context")

        existing_context = format_existing_concepts_for_prompt(existing_concepts_data)

        _concept_span = None
        try:
            if trace:
                _concept_span = trace.span(
                    name="concept_extraction",
                    input={"segment_count": len(aligned_segments)},
                )
        except Exception:
            pass

        concepts, generated_title = await asyncio.gather(
            extract_concepts_v2(aligned_segments, existing_context),
            generate_title(aligned_segments),
        )

        if generated_title:
            logger.info("Lecture %s: generated title %r", lecture_id, generated_title)
            (
                supabase.table("lectures")
                .update({"title": generated_title})
                .eq("id", lecture_id)
                .execute()
            )

        try:
            if _concept_span:
                _concept_span.end(output={"concepts_extracted": len(concepts)})
        except Exception:
            pass

        logger.info("Lecture %s: extracted %d concepts (V2)", lecture_id, len(concepts))

        # ── Stage 5: Chunking + Embedding ──
        update_processing_status(
            supabase, lecture_id, "processing",
            stage="generating_embeddings",
            progress=STAGE_PROGRESS["generating_embeddings"],
        )
        _embed_span = None
        try:
            if trace:
                _embed_span = trace.span(name="embedding_generation")
        except Exception:
            pass

        chunks = chunk_content(aligned_segments)
        chunks, concepts = await asyncio.gather(
            embed_chunks(chunks),
            embed_concepts(concepts),
        )

        try:
            if _embed_span:
                _embed_span.end(output={"chunks": len(chunks), "concepts": len(concepts)})
        except Exception:
            pass

        logger.info(
            "Lecture %s: embedded %d chunks, %d concepts",
            lecture_id, len(chunks), len(concepts),
        )

        # ── Stage 6: Concept-Chunk Linking + Storage ──
        stored_chunks = store_chunks(supabase, lecture_id, user_id, chunks)
        for chunk, stored in zip(chunks, stored_chunks, strict=False):
            chunk["id"] = stored["id"]

        concepts = link_concepts_to_chunks(concepts, chunks, top_k=5)

        # Register concepts via the course-level registry (merge or insert)
        registry_result = await register_concepts(
            supabase, course_id, lecture_id, user_id, concepts,
        )

        logger.info(
            "Lecture %s: %d concepts merged, %d new concepts inserted",
            lecture_id,
            len(registry_result["merged"]),
            len(registry_result["inserted"]),
        )

        # ── Stage 7: Concept Mapping (new concepts only) ──
        update_processing_status(
            supabase, lecture_id, "processing",
            stage="mapping_concepts",
            progress=STAGE_PROGRESS["mapping_concepts"],
        )

        concept_links = []
        if registry_result["inserted"]:
            new_concept_ids = [c["concept_id"] for c in registry_result["inserted"]]
            new_stored = (
                supabase.table("concepts")
                .select("*")
                .in_("id", new_concept_ids)
                .execute()
            ).data or []

            lec_meta = {}
            try:
                lecture_data = (
                    supabase.table("lectures")
                    .select("lecture_date, lecture_number")
                    .eq("id", lecture_id)
                    .execute()
                )
                lec_meta = lecture_data.data[0] if lecture_data.data else {}
            except Exception:
                pass

            concept_links = await map_concepts_to_assessments(
                supabase=supabase,
                lecture_id=lecture_id,
                course_id=course_id,
                user_id=user_id,
                concepts=new_stored,
                lecture_date=lec_meta.get("lecture_date"),
                lecture_number=lec_meta.get("lecture_number"),
            )

        logger.info(
            "Lecture %s: created %d concept-assessment links",
            lecture_id, len(concept_links),
        )

        # ── Quality gate: flag lectures with suspiciously low concept yield ──
        LOW_CONCEPT_THRESHOLD = 3
        concepts_this_lecture = (
            len(registry_result["merged"]) + len(registry_result["inserted"])
        )
        low_concept_yield = concepts_this_lecture < LOW_CONCEPT_THRESHOLD

        if low_concept_yield:
            logger.warning(
                "Lecture %s: low concept yield (%d concepts extracted — threshold: %d). "
                "Possible causes: short audio, poor quality, or abstract content.",
                lecture_id, concepts_this_lecture, LOW_CONCEPT_THRESHOLD,
            )

        # ── Update lecture record ──
        # Store structured JSONB array of segments (cap at 500 to avoid row bloat)
        transcript_json = [
            {
                "start": seg.get("start"),
                "end": seg.get("end"),
                "text": seg.get("text"),
                "speaker": seg.get("speaker"),
            }
            for seg in aligned_segments
            if seg.get("text")
        ][:500]

        update_data = {
            "processing_status": "completed",
            "processing_stage": "completed",
            "processing_progress": 1.0,
            "processing_error": None,
            "transcript": transcript_json,
            "low_concept_yield": low_concept_yield,
        }
        if generated_title:
            update_data["title"] = generated_title
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

        # Finalize LangFuse trace + PostHog event
        try:
            if trace:
                trace.update(output={
                    "chunks_stored": len(stored_chunks),
                    "concepts_merged": len(registry_result["merged"]),
                    "concepts_inserted": len(registry_result["inserted"]),
                    "processing_path": processing_path,
                    "duration_seconds": elapsed,
                })
                lf.flush()
        except Exception:
            pass

        try:
            from ..services.observability import track_event

            track_event(user_id, "lecture_processing_complete", {
                "lecture_id": lecture_id,
                "chunks_stored": len(stored_chunks),
                "concepts_merged": len(registry_result["merged"]),
                "concepts_inserted": len(registry_result["inserted"]),
                "duration_seconds": elapsed,
            })
        except Exception:
            pass

        return {
            "lecture_id": lecture_id,
            "chunks_stored": len(stored_chunks),
            "concepts_merged": len(registry_result["merged"]),
            "concepts_inserted": len(registry_result["inserted"]),
            "concepts_total": registry_result["total_concepts_in_course"],
            "concept_links_created": len(concept_links),
            "processing_path": route_result.processing_path,
            "duration_seconds": elapsed,
            "low_concept_yield": low_concept_yield,
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
        from ..services.observability import capture_exception

        capture_exception(
            Exception(f"Lecture processing failed at {stage}: {error}"),
            context={"lecture_id": lecture_id, "stage": stage},
        )
    except Exception:
        pass
    try:
        update_processing_status(
            supabase, lecture_id,
            status="failed",
            stage=stage,
            error=error[:1000],
        )
        (
            supabase.rpc("increment_lecture_retry_count", {"p_lecture_id": lecture_id})
            .execute()
        )
    except Exception as update_err:
        logger.error("Failed to update failure status: %s", update_err)
