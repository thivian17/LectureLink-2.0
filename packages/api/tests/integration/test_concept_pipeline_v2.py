"""Integration test: V2 concept pipeline with registry deduplication.

Verifies the end-to-end flow through the pipeline with:
- extract_concepts_v2 called with existing concepts context
- register_concepts used instead of direct store_concepts
- map_concepts_to_assessments called ONLY for newly inserted concepts
- Return dict includes concepts_merged, concepts_inserted, concepts_total
"""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

pytestmark = [pytest.mark.integration]

_MOD = "lecturelink_api.pipeline.lecture_processor"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

LECTURE_ID = str(uuid.uuid4())
COURSE_ID = str(uuid.uuid4())
USER_ID = str(uuid.uuid4())
FILE_URLS = ["https://storage.example.com/lecture.mp3"]


def _route_result():
    from lecturelink_api.models.lecture_models import RouteResult

    return RouteResult(
        processing_path="audio_only",
        audio_url="https://storage.example.com/lecture.mp3",
        slides_url=None,
    )


def _aligned_segments():
    return [
        {"start": 0.0, "end": 30.0, "text": "Welcome.", "speaker": "professor",
         "slide_number": None, "source": "transcript"},
        {"start": 30.0, "end": 90.0, "text": "Today: energy conservation.",
         "speaker": "professor", "slide_number": None, "source": "transcript"},
    ]


def _extracted_concepts():
    """5 flat concepts as returned by extract_concepts_v2."""
    return [
        {"title": "Energy Conservation", "description": "Energy is conserved.",
         "category": "theorem", "difficulty_estimate": 0.5, "related_concepts": [],
         "key_terms": ["conservation", "energy"]},
        {"title": "Kinetic Energy", "description": "Energy of motion.",
         "category": "definition", "difficulty_estimate": 0.3, "related_concepts": [],
         "key_terms": ["kinetic", "motion"]},
        {"title": "Potential Energy", "description": "Stored energy.",
         "category": "definition", "difficulty_estimate": 0.3, "related_concepts": [],
         "key_terms": ["potential", "stored"]},
        {"title": "Work-Energy Theorem", "description": "Net work equals change in KE.",
         "category": "theorem", "difficulty_estimate": 0.6, "related_concepts": [],
         "key_terms": ["work", "theorem"]},
        {"title": "Power", "description": "Rate of doing work.",
         "category": "definition", "difficulty_estimate": 0.2, "related_concepts": [],
         "key_terms": ["power", "rate"]},
    ]


def _chunks():
    return [
        {"chunk_index": 0, "content": "Welcome.", "start_time": 0.0,
         "end_time": 30.0, "slide_number": None, "metadata": {}},
        {"chunk_index": 1, "content": "Today: energy conservation.",
         "start_time": 30.0, "end_time": 90.0, "slide_number": None, "metadata": {}},
    ]


def _stored_chunks():
    return [
        {"id": "chunk-aaa", "chunk_index": 0},
        {"id": "chunk-bbb", "chunk_index": 1},
    ]


def _registry_result_mixed():
    """2 merged + 3 inserted."""
    return {
        "merged": [
            {"concept_id": "existing-c1", "matched_title": "Energy Conservation",
             "new_title": "Energy Conservation"},
            {"concept_id": "existing-c2", "matched_title": "Kinetic Energy",
             "new_title": "Kinetic Energy"},
        ],
        "inserted": [
            {"concept_id": "new-c1", "title": "Potential Energy"},
            {"concept_id": "new-c2", "title": "Work-Energy Theorem"},
            {"concept_id": "new-c3", "title": "Power"},
        ],
        "total_concepts_in_course": 10,
    }


def _build_sb():
    sb = MagicMock()
    sb.table.return_value.update.return_value.eq.return_value.execute.return_value = MagicMock(data=[])
    sb.table.return_value.insert.return_value.execute.return_value = MagicMock(data=_stored_chunks())
    sb.table.return_value.select.return_value.eq.return_value.execute.return_value = MagicMock(data=[])
    sb.table.return_value.select.return_value.eq.return_value.order.return_value.execute.return_value = MagicMock(data=[])
    sb.table.return_value.select.return_value.in_.return_value.execute.return_value = MagicMock(
        data=[
            {"id": "new-c1", "title": "Potential Energy", "description": "Stored energy.", "category": "definition"},
            {"id": "new-c2", "title": "Work-Energy Theorem", "description": "Net work = delta KE.", "category": "theorem"},
            {"id": "new-c3", "title": "Power", "description": "Rate of doing work.", "category": "definition"},
        ]
    )
    sb.table.return_value.upsert.return_value.execute.return_value = MagicMock(data=[])
    sb.table.return_value.delete.return_value.eq.return_value.execute.return_value = MagicMock(data=[])
    sb.table.return_value.delete.return_value.in_.return_value.execute.return_value = MagicMock(data=[])
    sb.rpc.return_value.execute.return_value = MagicMock(data=[])
    return sb


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestConceptPipelineV2:
    @pytest.mark.asyncio
    async def test_extract_v2_called_with_existing_context(self):
        """extract_concepts_v2 receives the formatted existing concepts string."""
        sb = _build_sb()
        mock_extract_v2 = AsyncMock(return_value=_extracted_concepts())
        mock_format = MagicMock(return_value="- Energy Conservation: Energy is conserved.")

        with (
            patch(f"{_MOD}.route_input", AsyncMock(return_value=_route_result())),
            patch(f"{_MOD}.transcribe_audio", AsyncMock(return_value=_aligned_segments())),
            patch(f"{_MOD}.align_content", AsyncMock(return_value=_aligned_segments())),
            patch(f"{_MOD}.extract_concepts_v2", mock_extract_v2),
            patch(f"{_MOD}.format_existing_concepts_for_prompt", mock_format),
            patch(f"{_MOD}.chunk_content", MagicMock(return_value=_chunks())),
            patch(f"{_MOD}.embed_chunks", AsyncMock(return_value=_chunks())),
            patch(f"{_MOD}.embed_concepts", AsyncMock(return_value=_extracted_concepts())),
            patch(f"{_MOD}.link_concepts_to_chunks", MagicMock(return_value=_extracted_concepts())),
            patch(f"{_MOD}.store_chunks", MagicMock(return_value=_stored_chunks())),
            patch(f"{_MOD}.register_concepts", AsyncMock(return_value=_registry_result_mixed())),
            patch(f"{_MOD}.map_concepts_to_assessments", AsyncMock(return_value=[])),
            patch(f"{_MOD}.update_processing_status", MagicMock()),
            patch(f"{_MOD}.cleanup_lecture_data", MagicMock()),
        ):
            await _run_pipeline(sb)

        # format_existing_concepts_for_prompt was called with whatever sb returned
        mock_format.assert_called_once()

        # extract_concepts_v2 was called with aligned segments and the formatted context
        mock_extract_v2.assert_called_once()
        call_args = mock_extract_v2.call_args
        assert call_args[0][0] == _aligned_segments()  # segments
        assert call_args[0][1] == "- Energy Conservation: Energy is conserved."

    @pytest.mark.asyncio
    async def test_register_concepts_called_with_extracted(self):
        """register_concepts receives the extracted (post-linking) concepts."""
        sb = _build_sb()
        mock_register = AsyncMock(return_value=_registry_result_mixed())

        with (
            patch(f"{_MOD}.route_input", AsyncMock(return_value=_route_result())),
            patch(f"{_MOD}.transcribe_audio", AsyncMock(return_value=_aligned_segments())),
            patch(f"{_MOD}.align_content", AsyncMock(return_value=_aligned_segments())),
            patch(f"{_MOD}.extract_concepts_v2", AsyncMock(return_value=_extracted_concepts())),
            patch(f"{_MOD}.format_existing_concepts_for_prompt", MagicMock(return_value="None yet")),
            patch(f"{_MOD}.chunk_content", MagicMock(return_value=_chunks())),
            patch(f"{_MOD}.embed_chunks", AsyncMock(return_value=_chunks())),
            patch(f"{_MOD}.embed_concepts", AsyncMock(return_value=_extracted_concepts())),
            patch(f"{_MOD}.link_concepts_to_chunks", MagicMock(return_value=_extracted_concepts())),
            patch(f"{_MOD}.store_chunks", MagicMock(return_value=_stored_chunks())),
            patch(f"{_MOD}.register_concepts", mock_register),
            patch(f"{_MOD}.map_concepts_to_assessments", AsyncMock(return_value=[])),
            patch(f"{_MOD}.update_processing_status", MagicMock()),
            patch(f"{_MOD}.cleanup_lecture_data", MagicMock()),
        ):
            await _run_pipeline(sb)

        mock_register.assert_called_once()
        args = mock_register.call_args
        assert args[0][0] is sb  # supabase
        assert args[0][1] == COURSE_ID
        assert args[0][2] == LECTURE_ID
        assert args[0][3] == USER_ID
        assert len(args[0][4]) == 5  # 5 concepts

    @pytest.mark.asyncio
    async def test_map_only_inserted_concepts(self):
        """map_concepts_to_assessments is called only for inserted (not merged) concepts."""
        sb = _build_sb()
        mock_map = AsyncMock(return_value=[{"concept_id": "new-c1", "assessment_id": "a-1"}])

        with (
            patch(f"{_MOD}.route_input", AsyncMock(return_value=_route_result())),
            patch(f"{_MOD}.transcribe_audio", AsyncMock(return_value=_aligned_segments())),
            patch(f"{_MOD}.align_content", AsyncMock(return_value=_aligned_segments())),
            patch(f"{_MOD}.extract_concepts_v2", AsyncMock(return_value=_extracted_concepts())),
            patch(f"{_MOD}.format_existing_concepts_for_prompt", MagicMock(return_value="None yet")),
            patch(f"{_MOD}.chunk_content", MagicMock(return_value=_chunks())),
            patch(f"{_MOD}.embed_chunks", AsyncMock(return_value=_chunks())),
            patch(f"{_MOD}.embed_concepts", AsyncMock(return_value=_extracted_concepts())),
            patch(f"{_MOD}.link_concepts_to_chunks", MagicMock(return_value=_extracted_concepts())),
            patch(f"{_MOD}.store_chunks", MagicMock(return_value=_stored_chunks())),
            patch(f"{_MOD}.register_concepts", AsyncMock(return_value=_registry_result_mixed())),
            patch(f"{_MOD}.map_concepts_to_assessments", mock_map),
            patch(f"{_MOD}.update_processing_status", MagicMock()),
            patch(f"{_MOD}.cleanup_lecture_data", MagicMock()),
        ):
            await _run_pipeline(sb)

        mock_map.assert_called_once()
        mapped_concepts = mock_map.call_args[1]["concepts"]
        # Should be the 3 newly inserted concepts fetched from DB
        assert len(mapped_concepts) == 3
        mapped_ids = {c["id"] for c in mapped_concepts}
        assert mapped_ids == {"new-c1", "new-c2", "new-c3"}

    @pytest.mark.asyncio
    async def test_no_mapping_when_all_merged(self):
        """If all concepts are merged, map_concepts_to_assessments is NOT called."""
        sb = _build_sb()
        mock_map = AsyncMock(return_value=[])
        all_merged_result = {
            "merged": [
                {"concept_id": "existing-c1", "matched_title": "Energy Conservation",
                 "new_title": "Energy Conservation"},
            ],
            "inserted": [],
            "total_concepts_in_course": 5,
        }

        with (
            patch(f"{_MOD}.route_input", AsyncMock(return_value=_route_result())),
            patch(f"{_MOD}.transcribe_audio", AsyncMock(return_value=_aligned_segments())),
            patch(f"{_MOD}.align_content", AsyncMock(return_value=_aligned_segments())),
            patch(f"{_MOD}.extract_concepts_v2", AsyncMock(return_value=_extracted_concepts())),
            patch(f"{_MOD}.format_existing_concepts_for_prompt", MagicMock(return_value="None yet")),
            patch(f"{_MOD}.chunk_content", MagicMock(return_value=_chunks())),
            patch(f"{_MOD}.embed_chunks", AsyncMock(return_value=_chunks())),
            patch(f"{_MOD}.embed_concepts", AsyncMock(return_value=_extracted_concepts())),
            patch(f"{_MOD}.link_concepts_to_chunks", MagicMock(return_value=_extracted_concepts())),
            patch(f"{_MOD}.store_chunks", MagicMock(return_value=_stored_chunks())),
            patch(f"{_MOD}.register_concepts", AsyncMock(return_value=all_merged_result)),
            patch(f"{_MOD}.map_concepts_to_assessments", mock_map),
            patch(f"{_MOD}.update_processing_status", MagicMock()),
            patch(f"{_MOD}.cleanup_lecture_data", MagicMock()),
        ):
            result = await _run_pipeline(sb)

        mock_map.assert_not_called()
        assert result["concepts_merged"] == 1
        assert result["concepts_inserted"] == 0
        assert result["concept_links_created"] == 0

    @pytest.mark.asyncio
    async def test_return_dict_includes_registry_stats(self):
        """Pipeline return dict has concepts_merged, concepts_inserted, concepts_total."""
        sb = _build_sb()

        with (
            patch(f"{_MOD}.route_input", AsyncMock(return_value=_route_result())),
            patch(f"{_MOD}.transcribe_audio", AsyncMock(return_value=_aligned_segments())),
            patch(f"{_MOD}.align_content", AsyncMock(return_value=_aligned_segments())),
            patch(f"{_MOD}.extract_concepts_v2", AsyncMock(return_value=_extracted_concepts())),
            patch(f"{_MOD}.format_existing_concepts_for_prompt", MagicMock(return_value="None yet")),
            patch(f"{_MOD}.chunk_content", MagicMock(return_value=_chunks())),
            patch(f"{_MOD}.embed_chunks", AsyncMock(return_value=_chunks())),
            patch(f"{_MOD}.embed_concepts", AsyncMock(return_value=_extracted_concepts())),
            patch(f"{_MOD}.link_concepts_to_chunks", MagicMock(return_value=_extracted_concepts())),
            patch(f"{_MOD}.store_chunks", MagicMock(return_value=_stored_chunks())),
            patch(f"{_MOD}.register_concepts", AsyncMock(return_value=_registry_result_mixed())),
            patch(f"{_MOD}.map_concepts_to_assessments", AsyncMock(return_value=[{"id": "link-1"}])),
            patch(f"{_MOD}.update_processing_status", MagicMock()),
            patch(f"{_MOD}.cleanup_lecture_data", MagicMock()),
        ):
            result = await _run_pipeline(sb)

        assert result["lecture_id"] == LECTURE_ID
        assert result["chunks_stored"] == 2
        assert result["concepts_merged"] == 2
        assert result["concepts_inserted"] == 3
        assert result["concepts_total"] == 10
        assert result["concept_links_created"] == 1
        assert result["processing_path"] == "audio_only"
        assert result["duration_seconds"] >= 0


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

async def _run_pipeline(sb):
    from lecturelink_api.pipeline.lecture_processor import process_lecture

    return await process_lecture(sb, LECTURE_ID, COURSE_ID, USER_ID, FILE_URLS)
