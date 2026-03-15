"""Tests for the lecture processing pipeline orchestrator.

Mocks all individual agents and services to test only the wiring logic:
- Correct stage ordering
- Parallel execution for audio+slides
- Processing path branching
- Status updates at each stage
- Error handling and failure marking
- Reprocessing cleanup
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from lecturelink_api.models.lecture_models import RouteResult
from lecturelink_api.pipeline.lecture_processor import (
    LectureProcessingError,
    _handle_failure,
    process_lecture,
)
from lecturelink_api.services.processing import STAGE_PROGRESS

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

LECTURE_ID = "lec-0001"
COURSE_ID = "course-0001"
USER_ID = "user-0001"
FILE_URLS = ["https://storage.example.com/lecture.mp3", "https://storage.example.com/slides.pdf"]


def _mock_route_result(path: str = "audio+slides") -> RouteResult:
    return RouteResult(
        processing_path=path,
        audio_url="https://storage.example.com/lecture.mp3" if "audio" in path else None,
        slides_url="https://storage.example.com/slides.pdf" if "slides" in path else None,
    )


def _transcript_segments() -> list[dict]:
    return [
        {"start": 0.0, "end": 15.5, "text": "Welcome to the lecture.", "speaker": "professor"},
        {"start": 15.5, "end": 45.0, "text": "Today we cover energy.", "speaker": "professor"},
        {"start": 45.0, "end": 120.0, "text": "Energy cannot be created.", "speaker": "professor"},
    ]


def _slide_analysis() -> list[dict]:
    return [
        {"slide_number": 1, "title": "Intro", "text_content": "Energy overview"},
        {"slide_number": 2, "title": "Laws", "text_content": "First law details"},
    ]


def _aligned_segments() -> list[dict]:
    return [
        {"start": 0.0, "end": 15.5, "text": "Welcome to the lecture.", "speaker": "professor", "slide_number": 1, "source": "aligned"},
        {"start": 15.5, "end": 45.0, "text": "Today we cover energy.", "speaker": "professor", "slide_number": 1, "source": "aligned"},
        {"start": 45.0, "end": 120.0, "text": "Energy cannot be created.", "speaker": "professor", "slide_number": 2, "source": "aligned"},
    ]


def _concepts() -> list[dict]:
    return [
        {"title": "Energy Conservation", "description": "Energy is conserved", "category": "theorem", "difficulty_estimate": 0.5, "related_concepts": []},
        {"title": "Heat Transfer", "description": "Heat moves between systems", "category": "process", "difficulty_estimate": 0.4, "related_concepts": []},
    ]


def _chunks() -> list[dict]:
    return [
        {"chunk_index": 0, "content": "Welcome to the lecture. Today we cover energy.", "start_time": 0.0, "end_time": 45.0, "slide_number": 1, "metadata": {"source": "aligned"}},
        {"chunk_index": 1, "content": "Energy cannot be created.", "start_time": 45.0, "end_time": 120.0, "slide_number": 2, "metadata": {"source": "aligned"}},
    ]


def _stored_chunks() -> list[dict]:
    return [
        {"id": "db-chunk-0", "chunk_index": 0, "content": "Welcome..."},
        {"id": "db-chunk-1", "chunk_index": 1, "content": "Energy..."},
    ]


def _stored_concepts() -> list[dict]:
    return [
        {"id": "db-concept-0", "title": "Energy Conservation"},
        {"id": "db-concept-1", "title": "Heat Transfer"},
    ]


def _registry_result() -> dict:
    return {
        "merged": [],
        "inserted": [
            {"concept_id": "db-concept-0", "title": "Energy Conservation"},
            {"concept_id": "db-concept-1", "title": "Heat Transfer"},
        ],
        "total_concepts_in_course": 2,
    }


def _build_mock_supabase() -> MagicMock:
    """Build a mock Supabase client that supports chained method calls."""
    sb = MagicMock()

    # update_processing_status chain: .table().update().eq().execute()
    sb.table.return_value.update.return_value.eq.return_value.execute.return_value = MagicMock(
        data=[]
    )

    # store_chunks chain: .table().insert().execute()
    sb.table.return_value.insert.return_value.execute.return_value = MagicMock(
        data=_stored_chunks()
    )

    # lecture metadata select chain: .table().select().eq().execute()
    sb.table.return_value.select.return_value.eq.return_value.execute.return_value = MagicMock(
        data=[{"lecture_date": "2026-01-12", "lecture_number": 1}]
    )

    # concept_assessment_links upsert chain
    sb.table.return_value.upsert.return_value.execute.return_value = MagicMock(
        data=[]
    )

    # rpc chain
    sb.rpc.return_value.execute.return_value = MagicMock(data=[])

    # cleanup chains
    sb.table.return_value.delete.return_value.eq.return_value.execute.return_value = MagicMock(
        data=[]
    )
    sb.table.return_value.delete.return_value.in_.return_value.execute.return_value = MagicMock(
        data=[]
    )
    sb.table.return_value.select.return_value.eq.return_value.eq.return_value.limit.return_value.execute.return_value = MagicMock(
        data=[]
    )

    return sb


# The module path prefix for all patches
_MOD = "lecturelink_api.pipeline.lecture_processor"


# ---------------------------------------------------------------------------
# Test: Full audio+slides path
# ---------------------------------------------------------------------------


class TestFullAudioSlidesPath:
    @pytest.mark.asyncio
    async def test_all_stages_called_in_order(self):
        sb = _build_mock_supabase()
        call_order = []

        async def mock_route(urls):
            call_order.append("route_input")
            return _mock_route_result("audio+slides")

        async def mock_transcribe(url):
            call_order.append("transcribe_audio")
            return _transcript_segments()

        async def mock_analyze(url):
            call_order.append("analyze_slides")
            return _slide_analysis()

        async def mock_align(t, s):
            call_order.append("align_content")
            return _aligned_segments()

        async def mock_extract(segs, existing_context=""):
            call_order.append("extract_concepts_v2")
            return _concepts()

        def mock_chunk(segs):
            call_order.append("chunk_content")
            return _chunks()

        async def mock_embed_chunks(c):
            call_order.append("embed_chunks")
            for chunk in c:
                chunk["embedding"] = [0.1] * 768
            return c

        async def mock_embed_concepts(c):
            call_order.append("embed_concepts")
            for concept in c:
                concept["embedding"] = [0.2] * 768
            return c

        def mock_link(concepts, chunks, top_k=5):
            call_order.append("link_concepts_to_chunks")
            for c in concepts:
                c["source_chunk_ids"] = ["db-chunk-0"]
            return concepts

        def mock_store_chunks(sb, lid, uid, chunks):
            call_order.append("store_chunks")
            return _stored_chunks()

        async def mock_register(sb, cid, lid, uid, concepts):
            call_order.append("register_concepts")
            return _registry_result()

        async def mock_map(*, supabase, lecture_id, course_id, user_id, concepts, lecture_date, lecture_number):
            call_order.append("map_concepts")
            return [{"concept_id": "db-concept-0", "assessment_id": "assess-1"}]

        def mock_status(sb, lid, status, *, stage=None, progress=None, error=None):
            call_order.append(f"status:{stage or status}")

        with (
            patch(f"{_MOD}.route_input", side_effect=mock_route),
            patch(f"{_MOD}.transcribe_audio", side_effect=mock_transcribe),
            patch(f"{_MOD}.analyze_slides", side_effect=mock_analyze),
            patch(f"{_MOD}.align_content", side_effect=mock_align),
            patch(f"{_MOD}.extract_concepts_v2", side_effect=mock_extract),
            patch(f"{_MOD}.format_existing_concepts_for_prompt", MagicMock(return_value="None yet")),
            patch(f"{_MOD}.chunk_content", side_effect=mock_chunk),
            patch(f"{_MOD}.embed_chunks", side_effect=mock_embed_chunks),
            patch(f"{_MOD}.embed_concepts", side_effect=mock_embed_concepts),
            patch(f"{_MOD}.link_concepts_to_chunks", side_effect=mock_link),
            patch(f"{_MOD}.store_chunks", side_effect=mock_store_chunks),
            patch(f"{_MOD}.register_concepts", side_effect=mock_register),
            patch(f"{_MOD}.map_concepts_to_assessments", side_effect=mock_map),
            patch(f"{_MOD}.update_processing_status", side_effect=mock_status),
            patch(f"{_MOD}.cleanup_lecture_data", MagicMock()),
        ):
            await process_lecture(sb, LECTURE_ID, COURSE_ID, USER_ID, FILE_URLS)

        # Verify correct order (transcribe + analyze may interleave due to gather)
        assert "route_input" in call_order
        assert "align_content" in call_order
        assert "extract_concepts_v2" in call_order
        assert "chunk_content" in call_order
        assert "embed_chunks" in call_order
        assert "embed_concepts" in call_order
        assert "link_concepts_to_chunks" in call_order
        assert "store_chunks" in call_order
        assert "register_concepts" in call_order
        assert "map_concepts" in call_order

        # Route happens before transcribe/analyze
        assert call_order.index("route_input") < call_order.index("transcribe_audio")
        assert call_order.index("route_input") < call_order.index("analyze_slides")

        # Align happens after both transcribe and analyze
        assert call_order.index("align_content") > call_order.index("transcribe_audio")
        assert call_order.index("align_content") > call_order.index("analyze_slides")

        # Extract happens after align
        assert call_order.index("extract_concepts_v2") > call_order.index("align_content")

        # Chunk/embed after extract
        assert call_order.index("chunk_content") > call_order.index("extract_concepts_v2")

        # Store before link
        assert call_order.index("store_chunks") > call_order.index("embed_chunks")
        assert call_order.index("link_concepts_to_chunks") > call_order.index("store_chunks")

        # Map after register_concepts
        assert call_order.index("map_concepts") > call_order.index("register_concepts")

    @pytest.mark.asyncio
    async def test_returns_correct_result(self):
        sb = _build_mock_supabase()

        with (
            patch(f"{_MOD}.route_input", AsyncMock(return_value=_mock_route_result("audio+slides"))),
            patch(f"{_MOD}.transcribe_audio", AsyncMock(return_value=_transcript_segments())),
            patch(f"{_MOD}.analyze_slides", AsyncMock(return_value=_slide_analysis())),
            patch(f"{_MOD}.align_content", AsyncMock(return_value=_aligned_segments())),
            patch(f"{_MOD}.extract_concepts_v2", AsyncMock(return_value=_concepts())),
            patch(f"{_MOD}.chunk_content", MagicMock(return_value=_chunks())),
            patch(f"{_MOD}.embed_chunks", AsyncMock(return_value=_chunks())),
            patch(f"{_MOD}.embed_concepts", AsyncMock(return_value=_concepts())),
            patch(f"{_MOD}.link_concepts_to_chunks", MagicMock(return_value=_concepts())),
            patch(f"{_MOD}.store_chunks", MagicMock(return_value=_stored_chunks())),
            patch(f"{_MOD}.register_concepts", AsyncMock(return_value=_registry_result())),
            patch(f"{_MOD}.format_existing_concepts_for_prompt", MagicMock(return_value="None yet")),
            patch(f"{_MOD}.map_concepts_to_assessments", AsyncMock(return_value=[{"id": "link-1"}])),
            patch(f"{_MOD}.update_processing_status", MagicMock()),
            patch(f"{_MOD}.cleanup_lecture_data", MagicMock()),
        ):
            result = await process_lecture(sb, LECTURE_ID, COURSE_ID, USER_ID, FILE_URLS)

        assert result["lecture_id"] == LECTURE_ID
        assert result["chunks_stored"] == 2
        assert result["concepts_merged"] == 0
        assert result["concepts_inserted"] == 2
        assert result["concepts_total"] == 2
        assert result["concept_links_created"] == 1
        assert result["processing_path"] == "audio+slides"
        assert result["duration_seconds"] >= 0

    @pytest.mark.asyncio
    async def test_parallel_execution_for_audio_slides(self):
        """Verify transcribe_audio and analyze_slides run concurrently."""
        sb = _build_mock_supabase()
        start_times = {}

        async def mock_transcribe(url):
            start_times["transcribe"] = asyncio.get_event_loop().time()
            await asyncio.sleep(0.05)
            return _transcript_segments()

        async def mock_analyze(url):
            start_times["analyze"] = asyncio.get_event_loop().time()
            await asyncio.sleep(0.05)
            return _slide_analysis()

        with (
            patch(f"{_MOD}.route_input", AsyncMock(return_value=_mock_route_result("audio+slides"))),
            patch(f"{_MOD}.transcribe_audio", side_effect=mock_transcribe),
            patch(f"{_MOD}.analyze_slides", side_effect=mock_analyze),
            patch(f"{_MOD}.align_content", AsyncMock(return_value=_aligned_segments())),
            patch(f"{_MOD}.extract_concepts_v2", AsyncMock(return_value=_concepts())),
            patch(f"{_MOD}.chunk_content", MagicMock(return_value=_chunks())),
            patch(f"{_MOD}.embed_chunks", AsyncMock(return_value=_chunks())),
            patch(f"{_MOD}.embed_concepts", AsyncMock(return_value=_concepts())),
            patch(f"{_MOD}.link_concepts_to_chunks", MagicMock(return_value=_concepts())),
            patch(f"{_MOD}.store_chunks", MagicMock(return_value=_stored_chunks())),
            patch(f"{_MOD}.register_concepts", AsyncMock(return_value=_registry_result())),
            patch(f"{_MOD}.format_existing_concepts_for_prompt", MagicMock(return_value="None yet")),
            patch(f"{_MOD}.map_concepts_to_assessments", AsyncMock(return_value=[])),
            patch(f"{_MOD}.update_processing_status", MagicMock()),
            patch(f"{_MOD}.cleanup_lecture_data", MagicMock()),
        ):
            await process_lecture(sb, LECTURE_ID, COURSE_ID, USER_ID, FILE_URLS)

        # Both should have started close together (within 10ms)
        assert abs(start_times["transcribe"] - start_times["analyze"]) < 0.01


# ---------------------------------------------------------------------------
# Test: Audio-only path
# ---------------------------------------------------------------------------


class TestAudioOnlyPath:
    @pytest.mark.asyncio
    async def test_slide_analyzer_not_called(self):
        sb = _build_mock_supabase()
        mock_analyze = AsyncMock()

        with (
            patch(f"{_MOD}.route_input", AsyncMock(return_value=_mock_route_result("audio_only"))),
            patch(f"{_MOD}.transcribe_audio", AsyncMock(return_value=_transcript_segments())),
            patch(f"{_MOD}.analyze_slides", mock_analyze),
            patch(f"{_MOD}.align_content", AsyncMock(return_value=_aligned_segments())),
            patch(f"{_MOD}.extract_concepts_v2", AsyncMock(return_value=_concepts())),
            patch(f"{_MOD}.chunk_content", MagicMock(return_value=_chunks())),
            patch(f"{_MOD}.embed_chunks", AsyncMock(return_value=_chunks())),
            patch(f"{_MOD}.embed_concepts", AsyncMock(return_value=_concepts())),
            patch(f"{_MOD}.link_concepts_to_chunks", MagicMock(return_value=_concepts())),
            patch(f"{_MOD}.store_chunks", MagicMock(return_value=_stored_chunks())),
            patch(f"{_MOD}.register_concepts", AsyncMock(return_value=_registry_result())),
            patch(f"{_MOD}.format_existing_concepts_for_prompt", MagicMock(return_value="None yet")),
            patch(f"{_MOD}.map_concepts_to_assessments", AsyncMock(return_value=[])),
            patch(f"{_MOD}.update_processing_status", MagicMock()),
            patch(f"{_MOD}.cleanup_lecture_data", MagicMock()),
        ):
            result = await process_lecture(
                sb, LECTURE_ID, COURSE_ID, USER_ID,
                ["https://storage.example.com/lecture.mp3"],
            )

        mock_analyze.assert_not_called()
        assert result["processing_path"] == "audio_only"


# ---------------------------------------------------------------------------
# Test: Slides-only path
# ---------------------------------------------------------------------------


class TestSlidesOnlyPath:
    @pytest.mark.asyncio
    async def test_transcriber_not_called(self):
        sb = _build_mock_supabase()
        mock_transcribe = AsyncMock()

        with (
            patch(f"{_MOD}.route_input", AsyncMock(return_value=_mock_route_result("slides_only"))),
            patch(f"{_MOD}.transcribe_audio", mock_transcribe),
            patch(f"{_MOD}.analyze_slides", AsyncMock(return_value=_slide_analysis())),
            patch(f"{_MOD}.align_content", AsyncMock(return_value=_aligned_segments())),
            patch(f"{_MOD}.extract_concepts_v2", AsyncMock(return_value=_concepts())),
            patch(f"{_MOD}.chunk_content", MagicMock(return_value=_chunks())),
            patch(f"{_MOD}.embed_chunks", AsyncMock(return_value=_chunks())),
            patch(f"{_MOD}.embed_concepts", AsyncMock(return_value=_concepts())),
            patch(f"{_MOD}.link_concepts_to_chunks", MagicMock(return_value=_concepts())),
            patch(f"{_MOD}.store_chunks", MagicMock(return_value=_stored_chunks())),
            patch(f"{_MOD}.register_concepts", AsyncMock(return_value=_registry_result())),
            patch(f"{_MOD}.format_existing_concepts_for_prompt", MagicMock(return_value="None yet")),
            patch(f"{_MOD}.map_concepts_to_assessments", AsyncMock(return_value=[])),
            patch(f"{_MOD}.update_processing_status", MagicMock()),
            patch(f"{_MOD}.cleanup_lecture_data", MagicMock()),
        ):
            result = await process_lecture(
                sb, LECTURE_ID, COURSE_ID, USER_ID,
                ["https://storage.example.com/slides.pdf"],
            )

        mock_transcribe.assert_not_called()
        assert result["processing_path"] == "slides_only"

    @pytest.mark.asyncio
    async def test_duration_is_none_without_transcript(self):
        """When no transcript, duration_seconds should not be in the update."""
        sb = _build_mock_supabase()

        with (
            patch(f"{_MOD}.route_input", AsyncMock(return_value=_mock_route_result("slides_only"))),
            patch(f"{_MOD}.transcribe_audio", AsyncMock()),
            patch(f"{_MOD}.analyze_slides", AsyncMock(return_value=_slide_analysis())),
            patch(f"{_MOD}.align_content", AsyncMock(return_value=_aligned_segments())),
            patch(f"{_MOD}.extract_concepts_v2", AsyncMock(return_value=_concepts())),
            patch(f"{_MOD}.chunk_content", MagicMock(return_value=_chunks())),
            patch(f"{_MOD}.embed_chunks", AsyncMock(return_value=_chunks())),
            patch(f"{_MOD}.embed_concepts", AsyncMock(return_value=_concepts())),
            patch(f"{_MOD}.link_concepts_to_chunks", MagicMock(return_value=_concepts())),
            patch(f"{_MOD}.store_chunks", MagicMock(return_value=_stored_chunks())),
            patch(f"{_MOD}.register_concepts", AsyncMock(return_value=_registry_result())),
            patch(f"{_MOD}.format_existing_concepts_for_prompt", MagicMock(return_value="None yet")),
            patch(f"{_MOD}.map_concepts_to_assessments", AsyncMock(return_value=[])),
            patch(f"{_MOD}.update_processing_status", MagicMock()),
            patch(f"{_MOD}.cleanup_lecture_data", MagicMock()),
        ):
            await process_lecture(
                sb, LECTURE_ID, COURSE_ID, USER_ID,
                ["https://storage.example.com/slides.pdf"],
            )

        # Check the final update call doesn't include duration_seconds
        update_calls = sb.table.return_value.update.call_args_list
        # Last update call should be the completion update
        if update_calls:
            last_update_data = update_calls[-1][0][0]
            assert "duration_seconds" not in last_update_data


# ---------------------------------------------------------------------------
# Test: Reprocessing
# ---------------------------------------------------------------------------


class TestReprocessing:
    @pytest.mark.asyncio
    async def test_cleanup_called_on_reprocess(self):
        sb = _build_mock_supabase()
        mock_cleanup = MagicMock()

        with (
            patch(f"{_MOD}.route_input", AsyncMock(return_value=_mock_route_result("audio+slides"))),
            patch(f"{_MOD}.transcribe_audio", AsyncMock(return_value=_transcript_segments())),
            patch(f"{_MOD}.analyze_slides", AsyncMock(return_value=_slide_analysis())),
            patch(f"{_MOD}.align_content", AsyncMock(return_value=_aligned_segments())),
            patch(f"{_MOD}.extract_concepts_v2", AsyncMock(return_value=_concepts())),
            patch(f"{_MOD}.chunk_content", MagicMock(return_value=_chunks())),
            patch(f"{_MOD}.embed_chunks", AsyncMock(return_value=_chunks())),
            patch(f"{_MOD}.embed_concepts", AsyncMock(return_value=_concepts())),
            patch(f"{_MOD}.link_concepts_to_chunks", MagicMock(return_value=_concepts())),
            patch(f"{_MOD}.store_chunks", MagicMock(return_value=_stored_chunks())),
            patch(f"{_MOD}.register_concepts", AsyncMock(return_value=_registry_result())),
            patch(f"{_MOD}.format_existing_concepts_for_prompt", MagicMock(return_value="None yet")),
            patch(f"{_MOD}.map_concepts_to_assessments", AsyncMock(return_value=[])),
            patch(f"{_MOD}.update_processing_status", MagicMock()),
            patch(f"{_MOD}.cleanup_lecture_data", mock_cleanup),
        ):
            await process_lecture(
                sb, LECTURE_ID, COURSE_ID, USER_ID, FILE_URLS, is_reprocess=True,
            )

        mock_cleanup.assert_called_once_with(sb, LECTURE_ID)

    @pytest.mark.asyncio
    async def test_no_cleanup_on_first_process(self):
        sb = _build_mock_supabase()
        mock_cleanup = MagicMock()

        with (
            patch(f"{_MOD}.route_input", AsyncMock(return_value=_mock_route_result("audio+slides"))),
            patch(f"{_MOD}.transcribe_audio", AsyncMock(return_value=_transcript_segments())),
            patch(f"{_MOD}.analyze_slides", AsyncMock(return_value=_slide_analysis())),
            patch(f"{_MOD}.align_content", AsyncMock(return_value=_aligned_segments())),
            patch(f"{_MOD}.extract_concepts_v2", AsyncMock(return_value=_concepts())),
            patch(f"{_MOD}.chunk_content", MagicMock(return_value=_chunks())),
            patch(f"{_MOD}.embed_chunks", AsyncMock(return_value=_chunks())),
            patch(f"{_MOD}.embed_concepts", AsyncMock(return_value=_concepts())),
            patch(f"{_MOD}.link_concepts_to_chunks", MagicMock(return_value=_concepts())),
            patch(f"{_MOD}.store_chunks", MagicMock(return_value=_stored_chunks())),
            patch(f"{_MOD}.register_concepts", AsyncMock(return_value=_registry_result())),
            patch(f"{_MOD}.format_existing_concepts_for_prompt", MagicMock(return_value="None yet")),
            patch(f"{_MOD}.map_concepts_to_assessments", AsyncMock(return_value=[])),
            patch(f"{_MOD}.update_processing_status", MagicMock()),
            patch(f"{_MOD}.cleanup_lecture_data", mock_cleanup),
        ):
            await process_lecture(
                sb, LECTURE_ID, COURSE_ID, USER_ID, FILE_URLS, is_reprocess=False,
            )

        mock_cleanup.assert_not_called()


# ---------------------------------------------------------------------------
# Test: Failure handling
# ---------------------------------------------------------------------------


class TestFailureHandling:
    @pytest.mark.asyncio
    async def test_transcription_failure(self):
        from lecturelink_api.agents.audio_transcriber import TranscriptionError

        sb = _build_mock_supabase()

        with (
            patch(f"{_MOD}.route_input", AsyncMock(return_value=_mock_route_result("audio_only"))),
            patch(f"{_MOD}.transcribe_audio", AsyncMock(side_effect=TranscriptionError("Gemini timeout"))),
            patch(f"{_MOD}.update_processing_status", MagicMock()),
            patch(f"{_MOD}.cleanup_lecture_data", MagicMock()),
        ):
            with pytest.raises(LectureProcessingError) as exc_info:
                await process_lecture(sb, LECTURE_ID, COURSE_ID, USER_ID, ["audio.mp3"])

        assert exc_info.value.stage == "content_processing"
        assert "Gemini timeout" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_slide_analysis_failure(self):
        from lecturelink_api.agents.slide_analyzer import SlideAnalysisError

        sb = _build_mock_supabase()

        with (
            patch(f"{_MOD}.route_input", AsyncMock(return_value=_mock_route_result("slides_only"))),
            patch(f"{_MOD}.analyze_slides", AsyncMock(side_effect=SlideAnalysisError("PDF corrupt"))),
            patch(f"{_MOD}.update_processing_status", MagicMock()),
            patch(f"{_MOD}.cleanup_lecture_data", MagicMock()),
        ):
            with pytest.raises(LectureProcessingError) as exc_info:
                await process_lecture(sb, LECTURE_ID, COURSE_ID, USER_ID, ["slides.pdf"])

        assert exc_info.value.stage == "content_processing"

    @pytest.mark.asyncio
    async def test_concept_extraction_failure(self):
        from lecturelink_api.agents.concept_extractor import ConceptExtractionError

        sb = _build_mock_supabase()

        with (
            patch(f"{_MOD}.route_input", AsyncMock(return_value=_mock_route_result("audio_only"))),
            patch(f"{_MOD}.transcribe_audio", AsyncMock(return_value=_transcript_segments())),
            patch(f"{_MOD}.align_content", AsyncMock(return_value=_aligned_segments())),
            patch(f"{_MOD}.extract_concepts_v2", AsyncMock(side_effect=ConceptExtractionError("JSON parse fail"))),
            patch(f"{_MOD}.format_existing_concepts_for_prompt", MagicMock(return_value="None yet")),
            patch(f"{_MOD}.update_processing_status", MagicMock()),
            patch(f"{_MOD}.cleanup_lecture_data", MagicMock()),
        ):
            with pytest.raises(LectureProcessingError) as exc_info:
                await process_lecture(sb, LECTURE_ID, COURSE_ID, USER_ID, ["audio.mp3"])

        assert exc_info.value.stage == "extracting_concepts"

    @pytest.mark.asyncio
    async def test_embedding_failure(self):
        from lecturelink_api.agents.chunker import EmbeddingError

        sb = _build_mock_supabase()

        with (
            patch(f"{_MOD}.route_input", AsyncMock(return_value=_mock_route_result("audio_only"))),
            patch(f"{_MOD}.transcribe_audio", AsyncMock(return_value=_transcript_segments())),
            patch(f"{_MOD}.align_content", AsyncMock(return_value=_aligned_segments())),
            patch(f"{_MOD}.extract_concepts_v2", AsyncMock(return_value=_concepts())),
            patch(f"{_MOD}.format_existing_concepts_for_prompt", MagicMock(return_value="None yet")),
            patch(f"{_MOD}.chunk_content", MagicMock(return_value=_chunks())),
            patch(f"{_MOD}.embed_chunks", AsyncMock(side_effect=EmbeddingError("Rate limited"))),
            patch(f"{_MOD}.update_processing_status", MagicMock()),
            patch(f"{_MOD}.cleanup_lecture_data", MagicMock()),
        ):
            with pytest.raises(LectureProcessingError) as exc_info:
                await process_lecture(sb, LECTURE_ID, COURSE_ID, USER_ID, ["audio.mp3"])

        assert exc_info.value.stage == "generating_embeddings"

    @pytest.mark.asyncio
    async def test_unknown_failure(self):
        sb = _build_mock_supabase()

        with (
            patch(f"{_MOD}.route_input", AsyncMock(side_effect=RuntimeError("something unexpected"))),
            patch(f"{_MOD}.update_processing_status", MagicMock()),
            patch(f"{_MOD}.cleanup_lecture_data", MagicMock()),
        ):
            with pytest.raises(LectureProcessingError) as exc_info:
                await process_lecture(sb, LECTURE_ID, COURSE_ID, USER_ID, FILE_URLS)

        assert exc_info.value.stage == "unknown"


# ---------------------------------------------------------------------------
# Test: Processing status updates
# ---------------------------------------------------------------------------


class TestStatusUpdates:
    @pytest.mark.asyncio
    async def test_correct_stages_and_progress(self):
        sb = _build_mock_supabase()
        status_calls = []

        def mock_status(sb, lid, status, *, stage=None, progress=None, error=None):
            status_calls.append({"stage": stage, "progress": progress})

        with (
            patch(f"{_MOD}.route_input", AsyncMock(return_value=_mock_route_result("audio+slides"))),
            patch(f"{_MOD}.transcribe_audio", AsyncMock(return_value=_transcript_segments())),
            patch(f"{_MOD}.analyze_slides", AsyncMock(return_value=_slide_analysis())),
            patch(f"{_MOD}.align_content", AsyncMock(return_value=_aligned_segments())),
            patch(f"{_MOD}.extract_concepts_v2", AsyncMock(return_value=_concepts())),
            patch(f"{_MOD}.chunk_content", MagicMock(return_value=_chunks())),
            patch(f"{_MOD}.embed_chunks", AsyncMock(return_value=_chunks())),
            patch(f"{_MOD}.embed_concepts", AsyncMock(return_value=_concepts())),
            patch(f"{_MOD}.link_concepts_to_chunks", MagicMock(return_value=_concepts())),
            patch(f"{_MOD}.store_chunks", MagicMock(return_value=_stored_chunks())),
            patch(f"{_MOD}.register_concepts", AsyncMock(return_value=_registry_result())),
            patch(f"{_MOD}.format_existing_concepts_for_prompt", MagicMock(return_value="None yet")),
            patch(f"{_MOD}.map_concepts_to_assessments", AsyncMock(return_value=[])),
            patch(f"{_MOD}.update_processing_status", side_effect=mock_status),
            patch(f"{_MOD}.cleanup_lecture_data", MagicMock()),
        ):
            await process_lecture(sb, LECTURE_ID, COURSE_ID, USER_ID, FILE_URLS)

        stages = [c["stage"] for c in status_calls]

        # All expected stages present (audio+slides path)
        assert "uploading" in stages
        assert "transcribing" in stages
        assert "analyzing_slides" in stages
        assert "aligning" in stages
        assert "extracting_concepts" in stages
        assert "generating_embeddings" in stages
        assert "mapping_concepts" in stages

        # Verify progress values match STAGE_PROGRESS
        for sc in status_calls:
            if sc["stage"] and sc["stage"] in STAGE_PROGRESS:
                assert sc["progress"] == STAGE_PROGRESS[sc["stage"]]


# ---------------------------------------------------------------------------
# Test: Duration calculation
# ---------------------------------------------------------------------------


class TestDurationCalculation:
    @pytest.mark.asyncio
    async def test_duration_from_transcript_timestamps(self):
        sb = _build_mock_supabase()

        with (
            patch(f"{_MOD}.route_input", AsyncMock(return_value=_mock_route_result("audio_only"))),
            patch(f"{_MOD}.transcribe_audio", AsyncMock(return_value=_transcript_segments())),
            patch(f"{_MOD}.align_content", AsyncMock(return_value=_aligned_segments())),
            patch(f"{_MOD}.extract_concepts_v2", AsyncMock(return_value=_concepts())),
            patch(f"{_MOD}.chunk_content", MagicMock(return_value=_chunks())),
            patch(f"{_MOD}.embed_chunks", AsyncMock(return_value=_chunks())),
            patch(f"{_MOD}.embed_concepts", AsyncMock(return_value=_concepts())),
            patch(f"{_MOD}.link_concepts_to_chunks", MagicMock(return_value=_concepts())),
            patch(f"{_MOD}.store_chunks", MagicMock(return_value=_stored_chunks())),
            patch(f"{_MOD}.register_concepts", AsyncMock(return_value=_registry_result())),
            patch(f"{_MOD}.format_existing_concepts_for_prompt", MagicMock(return_value="None yet")),
            patch(f"{_MOD}.map_concepts_to_assessments", AsyncMock(return_value=[])),
            patch(f"{_MOD}.update_processing_status", MagicMock()),
            patch(f"{_MOD}.cleanup_lecture_data", MagicMock()),
        ):
            await process_lecture(
                sb, LECTURE_ID, COURSE_ID, USER_ID,
                ["https://storage.example.com/lecture.mp3"],
            )

        # The update call should include duration_seconds = 120 (max end time)
        update_calls = sb.table.return_value.update.call_args_list
        if update_calls:
            last_data = update_calls[-1][0][0]
            assert last_data.get("duration_seconds") == 120


# ---------------------------------------------------------------------------
# Test: _handle_failure
# ---------------------------------------------------------------------------


class TestHandleFailure:
    def test_marks_lecture_as_failed(self):
        mock_status = MagicMock()
        sb = _build_mock_supabase()

        with patch(f"{_MOD}.update_processing_status", mock_status):
            _handle_failure(sb, LECTURE_ID, "some error", "content_processing")

        mock_status.assert_called_once_with(
            sb, LECTURE_ID,
            status="failed",
            stage="content_processing",
            error="some error",
        )

    def test_truncates_long_error_messages(self):
        mock_status = MagicMock()
        sb = _build_mock_supabase()
        long_error = "x" * 2000

        with patch(f"{_MOD}.update_processing_status", mock_status):
            _handle_failure(sb, LECTURE_ID, long_error, "unknown")

        call_kwargs = mock_status.call_args[1]
        assert len(call_kwargs["error"]) == 1000

    def test_status_update_failure_doesnt_raise(self):
        """If updating failure status itself fails, it should not raise."""
        sb = _build_mock_supabase()

        with patch(f"{_MOD}.update_processing_status", MagicMock(side_effect=Exception("DB down"))):
            # Should not raise
            _handle_failure(sb, LECTURE_ID, "original error", "unknown")
