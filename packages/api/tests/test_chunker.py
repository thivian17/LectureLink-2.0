"""Tests for the Chunker + Embedding Indexer agent."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import numpy as np
import pytest

from lecturelink_api.agents.chunker import (
    EmbeddingError,
    build_chunk,
    chunk_content,
    embed_chunks,
    embed_concepts,
    estimate_tokens,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _seg(text: str, start: float = 0, end: float = 10, slide: int | None = None) -> dict:
    return {
        "start": start,
        "end": end,
        "text": text,
        "speaker": "professor",
        "slide_number": slide,
        "source": "aligned",
    }


def _long_text(words: int = 300) -> str:
    """Generate text with a given number of words."""
    return " ".join(f"word{i}" for i in range(words))


# ---------------------------------------------------------------------------
# chunk_content
# ---------------------------------------------------------------------------


class TestChunkContent:
    def test_empty_list_returns_empty(self):
        assert chunk_content([]) == []

    def test_short_content_single_chunk(self):
        segments = [_seg("A short sentence.", 0, 5)]
        result = chunk_content(segments)
        assert len(result) == 1
        assert result[0]["chunk_index"] == 0
        assert "A short sentence." in result[0]["content"]

    def test_long_content_multiple_chunks_with_overlap(self):
        # Create enough segments to trigger multiple chunks
        # Each segment ~50 words ≈ 75 tokens; need >400 tokens per chunk
        segments = []
        for i in range(20):
            segments.append(
                _seg(
                    _long_text(50),
                    start=i * 30.0,
                    end=(i + 1) * 30.0,
                    slide=i // 5 + 1,
                )
            )
        result = chunk_content(segments)
        assert len(result) > 1

        # Check chunk indices are sequential
        for i, chunk in enumerate(result):
            assert chunk["chunk_index"] == i

        # Check that chunks have content
        for chunk in result:
            assert len(chunk["content"]) > 0

    def test_last_tiny_chunk_merges_with_previous(self):
        # 25 segments of 20 words (~30 tokens each).
        # After 2 full chunks are flushed, the remaining 3 overlap segments
        # total ~90 tokens < MIN_CHUNK_TOKENS (100), triggering a merge.
        segments = [
            _seg(_long_text(20), i * 5.0, (i + 1) * 5.0, slide=1)
            for i in range(25)
        ]
        result = chunk_content(segments)
        # Without merge this would be 3 chunks; with merge it's 2
        assert len(result) == 2
        # Merged chunk's end_time includes the last segment
        assert result[-1]["end_time"] == 125.0

    def test_empty_text_segments_skipped(self):
        segments = [
            _seg("", 0, 5),
            _seg("   ", 5, 10),
            _seg("Valid text here.", 10, 15),
        ]
        result = chunk_content(segments)
        assert len(result) == 1
        assert "Valid text here." in result[0]["content"]

    def test_chunk_has_correct_timing(self):
        segments = [
            _seg("First segment.", 0.0, 15.0, slide=1),
            _seg("Second segment.", 15.0, 30.0, slide=1),
        ]
        result = chunk_content(segments)
        assert len(result) == 1
        assert result[0]["start_time"] == 0.0
        assert result[0]["end_time"] == 30.0


# ---------------------------------------------------------------------------
# build_chunk
# ---------------------------------------------------------------------------


class TestBuildChunk:
    def test_assigns_correct_metadata(self):
        segments = [
            _seg("Text A.", 0, 10, slide=1),
            _seg("Text B.", 10, 20, slide=1),
        ]
        chunk = build_chunk(segments)
        assert chunk["content"] == "Text A. Text B."
        assert chunk["start_time"] == 0
        assert chunk["end_time"] == 20
        assert chunk["metadata"]["source"] == "aligned"

    def test_most_common_slide_number(self):
        segments = [
            _seg("A.", 0, 5, slide=1),
            _seg("B.", 5, 10, slide=2),
            _seg("C.", 10, 15, slide=2),
        ]
        chunk = build_chunk(segments)
        assert chunk["slide_number"] == 2  # Most common

    def test_no_slide_numbers_returns_none(self):
        segments = [
            _seg("A.", 0, 5, slide=None),
            _seg("B.", 5, 10, slide=None),
        ]
        chunk = build_chunk(segments)
        assert chunk["slide_number"] is None

    def test_mixed_sources_prefers_aligned(self):
        segments = [
            {"text": "A", "start": 0, "end": 5, "source": "audio", "slide_number": None},
            {"text": "B", "start": 5, "end": 10, "source": "aligned", "slide_number": 1},
        ]
        chunk = build_chunk(segments)
        assert chunk["metadata"]["source"] == "aligned"


# ---------------------------------------------------------------------------
# estimate_tokens
# ---------------------------------------------------------------------------


class TestEstimateTokens:
    def test_reasonable_estimates(self):
        text = "This is a ten word sentence for the test."
        tokens = estimate_tokens(text)
        # 9 words × 1.5 = 13.5 → int(13)
        assert tokens == 13

    def test_empty_string(self):
        assert estimate_tokens("") == 0

    def test_single_word(self):
        assert estimate_tokens("hello") == 1  # 1 × 1.5 = 1 (int)


# ---------------------------------------------------------------------------
# embed_chunks (mocked)
# ---------------------------------------------------------------------------


class TestEmbedChunks:
    @pytest.mark.asyncio
    async def test_chunks_get_768_dim_embeddings(self):
        mock_emb = MagicMock()
        mock_emb.values = np.random.randn(768).tolist()

        mock_response = MagicMock()
        mock_response.embeddings = [mock_emb, mock_emb]

        mock_client = MagicMock()
        mock_client.aio.models.embed_content = AsyncMock(
            return_value=mock_response
        )

        chunks = [
            {"content": "Chunk one text.", "chunk_index": 0},
            {"content": "Chunk two text.", "chunk_index": 1},
        ]

        with patch(
            "lecturelink_api.agents.chunker.genai.Client",
            return_value=mock_client,
        ):
            result = await embed_chunks(chunks)

        assert len(result) == 2
        for chunk in result:
            assert "embedding" in chunk
            assert len(chunk["embedding"]) == 768

    @pytest.mark.asyncio
    async def test_empty_chunks_returns_empty(self):
        result = await embed_chunks([])
        assert result == []

    @pytest.mark.asyncio
    async def test_api_failure_raises_embedding_error(self):
        mock_client = MagicMock()
        mock_client.aio.models.embed_content = AsyncMock(
            side_effect=RuntimeError("API down")
        )

        chunks = [{"content": "Some text.", "chunk_index": 0}]

        with patch(
            "lecturelink_api.agents.chunker.genai.Client",
            return_value=mock_client,
        ):
            with pytest.raises(EmbeddingError, match="Embedding generation failed"):
                await embed_chunks(chunks)


# ---------------------------------------------------------------------------
# embed_concepts (mocked)
# ---------------------------------------------------------------------------


class TestEmbedConcepts:
    @pytest.mark.asyncio
    async def test_concepts_get_768_dim_embeddings(self):
        mock_emb = MagicMock()
        mock_emb.values = np.random.randn(768).tolist()

        mock_response = MagicMock()
        mock_response.embeddings = [mock_emb]

        mock_client = MagicMock()
        mock_client.aio.models.embed_content = AsyncMock(
            return_value=mock_response
        )

        concepts = [{"title": "Entropy", "description": "Measure of disorder"}]

        with patch(
            "lecturelink_api.agents.chunker.genai.Client",
            return_value=mock_client,
        ):
            result = await embed_concepts(concepts)

        assert len(result) == 1
        assert "embedding" in result[0]
        assert len(result[0]["embedding"]) == 768

    @pytest.mark.asyncio
    async def test_empty_concepts_returns_empty(self):
        result = await embed_concepts([])
        assert result == []

    @pytest.mark.asyncio
    async def test_api_failure_raises_embedding_error(self):
        mock_client = MagicMock()
        mock_client.aio.models.embed_content = AsyncMock(
            side_effect=RuntimeError("API down")
        )

        concepts = [{"title": "X", "description": "Y"}]

        with patch(
            "lecturelink_api.agents.chunker.genai.Client",
            return_value=mock_client,
        ):
            with pytest.raises(EmbeddingError, match="Concept embedding failed"):
                await embed_concepts(concepts)
