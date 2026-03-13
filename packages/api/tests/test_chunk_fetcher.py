"""Tests for the deterministic chunk fetcher module."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


def _mock_execute(data):
    resp = MagicMock()
    resp.data = data
    resp.count = 0
    return resp


def _mock_chain(final_data):
    chain = MagicMock()
    chain.execute.return_value = _mock_execute(final_data)
    for method in ("select", "eq", "in_", "order", "limit", "single"):
        getattr(chain, method).return_value = chain
    return chain


SAMPLE_CHUNKS = [
    {"id": "ch1", "content": "Entropy explained", "lecture_id": "lec1", "start_time": 60.0, "end_time": 90.0, "slide_number": 3, "metadata": {}},
    {"id": "ch2", "content": "Second law details", "lecture_id": "lec1", "start_time": 90.0, "end_time": 120.0, "slide_number": 4, "metadata": {}},
]


class TestFetchConceptChunks:
    @pytest.mark.asyncio
    async def test_happy_path_deterministic(self):
        """Concept has source_chunk_ids → chunks fetched by ID, no search fallback."""
        from lecturelink_api.services.chunk_fetcher import fetch_concept_chunks

        sb = MagicMock()
        concept_chain = _mock_chain({"source_chunk_ids": ["ch1", "ch2"]})
        chunk_chain = _mock_chain(SAMPLE_CHUNKS)

        def table_side_effect(name):
            if name == "concepts":
                return concept_chain
            if name == "lecture_chunks":
                return chunk_chain
            return _mock_chain([])

        sb.table.side_effect = table_side_effect

        with patch(
            "lecturelink_api.services.chunk_fetcher.search_lectures",
            new_callable=AsyncMock,
        ) as mock_search:
            result = await fetch_concept_chunks(sb, concept_id="c1", course_id="course1")

        assert len(result) == 2
        assert result[0]["id"] == "ch1"
        mock_search.assert_not_called()

    @pytest.mark.asyncio
    async def test_empty_source_chunk_ids_falls_back_to_search(self):
        """Concept exists but source_chunk_ids is [] → falls back to search_lectures."""
        from lecturelink_api.services.chunk_fetcher import fetch_concept_chunks

        sb = MagicMock()
        sb.table.side_effect = lambda name: _mock_chain(
            {"source_chunk_ids": []} if name == "concepts" else []
        )

        search_results = [{"id": "sr1", "content": "Search result", "lecture_id": "lec1"}]

        with patch(
            "lecturelink_api.services.chunk_fetcher.search_lectures",
            new_callable=AsyncMock,
            return_value=search_results,
        ) as mock_search:
            result = await fetch_concept_chunks(
                sb, concept_id="c1", course_id="course1", concept_title="Entropy"
            )

        assert len(result) == 1
        assert result[0]["id"] == "sr1"
        mock_search.assert_called_once()

    @pytest.mark.asyncio
    async def test_concept_not_found_falls_back_to_search(self):
        """single() raises → falls back to search_lectures."""
        from lecturelink_api.services.chunk_fetcher import fetch_concept_chunks

        sb = MagicMock()
        concept_chain = MagicMock()
        concept_chain.select.return_value = concept_chain
        concept_chain.eq.return_value = concept_chain
        concept_chain.single.return_value = concept_chain
        concept_chain.execute.side_effect = Exception("Row not found")
        sb.table.side_effect = lambda name: concept_chain if name == "concepts" else _mock_chain([])

        search_results = [{"id": "sr1", "content": "Fallback", "lecture_id": "lec1"}]

        with patch(
            "lecturelink_api.services.chunk_fetcher.search_lectures",
            new_callable=AsyncMock,
            return_value=search_results,
        ) as mock_search:
            result = await fetch_concept_chunks(
                sb, concept_id="c1", course_id="course1", concept_title="Entropy"
            )

        assert len(result) == 1
        mock_search.assert_called_once()

    @pytest.mark.asyncio
    async def test_chunk_fetch_fails_falls_back_to_search(self):
        """source_chunk_ids exist but .in_() query fails → falls back to search."""
        from lecturelink_api.services.chunk_fetcher import fetch_concept_chunks

        sb = MagicMock()

        concept_chain = _mock_chain({"source_chunk_ids": ["ch1", "ch2"]})
        chunk_chain = MagicMock()
        chunk_chain.select.return_value = chunk_chain
        chunk_chain.in_.return_value = chunk_chain
        chunk_chain.execute.side_effect = Exception("DB error")

        def table_side_effect(name):
            if name == "concepts":
                return concept_chain
            if name == "lecture_chunks":
                return chunk_chain
            return _mock_chain([])

        sb.table.side_effect = table_side_effect

        search_results = [{"id": "sr1", "content": "Fallback", "lecture_id": "lec1"}]

        with patch(
            "lecturelink_api.services.chunk_fetcher.search_lectures",
            new_callable=AsyncMock,
            return_value=search_results,
        ) as mock_search:
            result = await fetch_concept_chunks(
                sb, concept_id="c1", course_id="course1", concept_title="Entropy"
            )

        assert len(result) == 1
        mock_search.assert_called_once()

    @pytest.mark.asyncio
    async def test_both_paths_fail_returns_empty(self):
        """source_chunk_ids empty AND search_lectures fails → returns []."""
        from lecturelink_api.services.chunk_fetcher import fetch_concept_chunks

        sb = MagicMock()
        sb.table.side_effect = lambda name: _mock_chain(
            {"source_chunk_ids": []} if name == "concepts" else []
        )

        with patch(
            "lecturelink_api.services.chunk_fetcher.search_lectures",
            new_callable=AsyncMock,
            side_effect=Exception("Search failed"),
        ):
            result = await fetch_concept_chunks(
                sb, concept_id="c1", course_id="course1", concept_title="Entropy"
            )

        assert result == []


class TestFetchChunksForConcepts:
    @pytest.mark.asyncio
    async def test_deduplicates_by_chunk_id(self):
        """Multiple concepts returning overlapping chunks → deduplicated."""
        from lecturelink_api.services.chunk_fetcher import fetch_chunks_for_concepts

        sb = MagicMock()
        concepts = [
            {"concept_id": "c1", "title": "Entropy"},
            {"concept_id": "c2", "title": "Thermodynamics"},
        ]

        # Both concepts return ch1; c2 also returns ch3
        call_count = 0

        async def mock_fetch(supabase, concept_id, course_id, *, limit=5, concept_title=""):
            nonlocal call_count
            call_count += 1
            if concept_id == "c1":
                return [
                    {"id": "ch1", "content": "Shared chunk", "lecture_id": "lec1"},
                    {"id": "ch2", "content": "Only c1", "lecture_id": "lec1"},
                ]
            return [
                {"id": "ch1", "content": "Shared chunk", "lecture_id": "lec1"},
                {"id": "ch3", "content": "Only c2", "lecture_id": "lec1"},
            ]

        with patch(
            "lecturelink_api.services.chunk_fetcher.fetch_concept_chunks",
            side_effect=mock_fetch,
        ):
            result = await fetch_chunks_for_concepts(sb, concepts, course_id="course1")

        assert len(result) == 3  # ch1, ch2, ch3 (ch1 deduplicated)
        ids = [c["id"] for c in result]
        assert ids == ["ch1", "ch2", "ch3"]

    @pytest.mark.asyncio
    async def test_mixed_resolution(self):
        """One concept has source_chunk_ids, another doesn't → mixed resolution works."""
        from lecturelink_api.services.chunk_fetcher import fetch_chunks_for_concepts

        sb = MagicMock()
        concepts = [
            {"concept_id": "c1", "title": "Entropy"},
            {"concept_id": "c2", "title": "Heat"},
        ]

        async def mock_fetch(supabase, concept_id, course_id, *, limit=5, concept_title=""):
            if concept_id == "c1":
                # Deterministic path
                return [{"id": "ch1", "content": "Deterministic", "lecture_id": "lec1"}]
            # Search fallback path
            return [{"id": "ch5", "content": "From search", "lecture_id": "lec2"}]

        with patch(
            "lecturelink_api.services.chunk_fetcher.fetch_concept_chunks",
            side_effect=mock_fetch,
        ):
            result = await fetch_chunks_for_concepts(sb, concepts, course_id="course1")

        assert len(result) == 2
        assert result[0]["id"] == "ch1"
        assert result[1]["id"] == "ch5"
