"""Tests for the Concept-Chunk Linker."""

from __future__ import annotations

import numpy as np
import pytest

from lecturelink_api.agents.concept_chunk_linker import (
    DEFAULT_TOP_K,
    link_concepts_to_chunks,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_embedding(dim: int = 768, seed: int = 0) -> list[float]:
    rng = np.random.RandomState(seed)
    vec = rng.randn(dim)
    vec = vec / np.linalg.norm(vec)
    return vec.tolist()


def _make_chunk(index: int, seed: int | None = None) -> dict:
    return {
        "id": f"chunk-{index}",
        "chunk_index": index,
        "content": f"Chunk {index} content",
        "embedding": _make_embedding(seed=seed if seed is not None else index),
    }


def _make_concept(title: str, seed: int) -> dict:
    return {
        "title": title,
        "description": f"Description of {title}",
        "embedding": _make_embedding(seed=seed),
    }


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestLinkConceptsToChunks:
    def test_valid_embeddings_assigns_top_k_chunk_ids(self):
        chunks = [_make_chunk(i) for i in range(10)]
        concepts = [_make_concept("Concept A", seed=42)]

        result = link_concepts_to_chunks(concepts, chunks, top_k=3)

        assert len(result) == 1
        assert len(result[0]["source_chunk_ids"]) == 3
        # All IDs should be valid chunk IDs
        valid_ids = {c["id"] for c in chunks}
        for cid in result[0]["source_chunk_ids"]:
            assert cid in valid_ids

    def test_empty_concepts_returns_empty(self):
        chunks = [_make_chunk(0)]
        result = link_concepts_to_chunks([], chunks)
        assert result == []

    def test_empty_chunks_returns_concepts_unchanged(self):
        concepts = [_make_concept("A", seed=0)]
        result = link_concepts_to_chunks(concepts, [])
        assert result == concepts

    def test_concept_without_embedding_gets_empty_ids(self):
        chunks = [_make_chunk(0)]
        concepts = [{"title": "No Embedding", "embedding": None}]

        result = link_concepts_to_chunks(concepts, chunks)

        assert result[0]["source_chunk_ids"] == []

    def test_top_k_capped_at_chunk_count(self):
        chunks = [_make_chunk(i) for i in range(3)]
        concepts = [_make_concept("A", seed=99)]

        result = link_concepts_to_chunks(concepts, chunks, top_k=10)

        # Can't get more than 3 chunks
        assert len(result[0]["source_chunk_ids"]) == 3

    def test_cosine_similarity_identifies_most_relevant(self):
        # Create a concept with a known embedding
        known_vec = np.zeros(768)
        known_vec[0] = 1.0  # Unit vector along dimension 0

        # Create chunks: one very similar, rest random
        similar_chunk = {
            "id": "similar",
            "chunk_index": 0,
            "embedding": known_vec.tolist(),
        }
        random_chunks = [_make_chunk(i + 1, seed=i + 100) for i in range(9)]
        chunks = [similar_chunk] + random_chunks

        concept = {
            "title": "Test",
            "embedding": known_vec.tolist(),
        }

        result = link_concepts_to_chunks([concept], chunks, top_k=1)

        assert result[0]["source_chunk_ids"] == ["similar"]

    def test_uses_chunk_index_when_no_id(self):
        chunks = [
            {
                "chunk_index": 7,
                "content": "Chunk without ID",
                "embedding": _make_embedding(seed=0),
            },
        ]
        concepts = [_make_concept("A", seed=0)]

        result = link_concepts_to_chunks(concepts, chunks, top_k=1)

        assert result[0]["source_chunk_ids"] == ["7"]

    def test_zero_norm_embedding_gets_empty_ids(self):
        chunks = [_make_chunk(0)]
        concepts = [{"title": "Zero", "embedding": [0.0] * 768}]

        result = link_concepts_to_chunks(concepts, chunks)

        assert result[0]["source_chunk_ids"] == []

    def test_multiple_concepts_linked_independently(self):
        chunks = [_make_chunk(i) for i in range(5)]
        concepts = [
            _make_concept("A", seed=10),
            _make_concept("B", seed=20),
        ]

        result = link_concepts_to_chunks(concepts, chunks, top_k=2)

        assert len(result) == 2
        assert len(result[0]["source_chunk_ids"]) == 2
        assert len(result[1]["source_chunk_ids"]) == 2
