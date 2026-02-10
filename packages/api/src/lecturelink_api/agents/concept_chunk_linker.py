"""Concept-Chunk Linker — links concepts to their most relevant source chunks.

Uses cosine similarity between concept and chunk embeddings to find the top-k
most relevant chunks for each concept.
"""

from __future__ import annotations

import logging

import numpy as np

logger = logging.getLogger(__name__)

DEFAULT_TOP_K = 5


def link_concepts_to_chunks(
    concepts: list[dict],
    chunks: list[dict],
    top_k: int = DEFAULT_TOP_K,
) -> list[dict]:
    """Link each concept to its most relevant source chunks via embedding similarity.

    Args:
        concepts: List with 'embedding' field (768-dim).
        chunks: List with 'embedding' and 'id' or 'chunk_index' field.
        top_k: Number of source chunks to link per concept.

    Returns:
        Same concepts with 'source_chunk_ids' populated.
    """
    if not concepts or not chunks:
        return concepts

    # Build chunk embedding matrix
    chunk_embeddings = np.array([c["embedding"] for c in chunks])
    # Normalize for cosine similarity
    chunk_norms = np.linalg.norm(chunk_embeddings, axis=1, keepdims=True)
    chunk_norms = np.maximum(chunk_norms, 1e-10)
    chunk_embeddings_normalized = chunk_embeddings / chunk_norms

    for concept in concepts:
        if concept.get("embedding") is None:
            concept["source_chunk_ids"] = []
            continue

        concept_emb = np.array(concept["embedding"])
        concept_norm = np.linalg.norm(concept_emb)
        if concept_norm < 1e-10:
            concept["source_chunk_ids"] = []
            continue

        concept_emb_normalized = concept_emb / concept_norm

        # Cosine similarity
        similarities = chunk_embeddings_normalized @ concept_emb_normalized

        # Get top-k indices
        k = min(top_k, len(chunks))
        top_indices = np.argsort(similarities)[-k:][::-1]

        # Use chunk IDs if available, otherwise chunk_index
        concept["source_chunk_ids"] = [
            chunks[i].get("id", str(chunks[i].get("chunk_index", i)))
            for i in top_indices
        ]

    logger.info(
        "Concept-chunk linking complete: %d concepts linked to chunks",
        len(concepts),
    )
    return concepts
