"""Chunker + Embedding Indexer — splits aligned content into semantic chunks and embeds them.

Chunks respect segment boundaries (never split mid-sentence) and carry overlap
for context continuity. Embeddings are generated via gemini-embedding-001.
"""

from __future__ import annotations

import logging

from google import genai

logger = logging.getLogger(__name__)

# Chunking parameters
TARGET_CHUNK_TOKENS = 400
MAX_CHUNK_TOKENS = 500
MIN_CHUNK_TOKENS = 100
OVERLAP_SEGMENTS = 2
TOKEN_ESTIMATE_FACTOR = 1.5


def chunk_content(aligned_segments: list[dict]) -> list[dict]:
    """Split aligned content into semantic chunks with overlap.

    Args:
        aligned_segments: [{{start, end, text, speaker, slide_number, source}}, ...]

    Returns:
        List of chunks: [{{content, start_time, end_time, slide_number, metadata,
        chunk_index}}, ...]
    """
    if not aligned_segments:
        return []

    chunks: list[dict] = []
    current_segments: list[dict] = []
    current_tokens = 0

    for segment in aligned_segments:
        text = segment.get("text", "").strip()
        if not text:
            continue

        segment_tokens = estimate_tokens(text)

        # If adding this segment would exceed target, save current chunk
        if (
            current_tokens + segment_tokens > TARGET_CHUNK_TOKENS
            and current_segments
        ):
            chunk = build_chunk(current_segments)
            chunks.append(chunk)

            # Overlap: carry last N segments for context continuity
            if len(current_segments) >= OVERLAP_SEGMENTS:
                overlap = current_segments[-OVERLAP_SEGMENTS:]
            else:
                overlap = current_segments[-1:]
            current_segments = list(overlap)
            current_tokens = sum(
                estimate_tokens(s.get("text", "")) for s in current_segments
            )

        current_segments.append(segment)
        current_tokens += segment_tokens

    # Don't forget the last chunk
    if current_segments:
        chunk = build_chunk(current_segments)
        # If last chunk is too small, merge with previous
        if chunks and estimate_tokens(chunk["content"]) < MIN_CHUNK_TOKENS:
            prev = chunks[-1]
            prev["content"] += " " + chunk["content"]
            prev["end_time"] = chunk["end_time"]
        else:
            chunks.append(chunk)

    # Assign chunk indices
    for i, chunk in enumerate(chunks):
        chunk["chunk_index"] = i

    logger.info(
        "Chunking complete: %d chunks from %d segments",
        len(chunks),
        len(aligned_segments),
    )
    return chunks


def build_chunk(segments: list[dict]) -> dict:
    """Build a chunk dict from a list of segments."""
    texts = [s.get("text", "") for s in segments]

    # Determine source type
    sources = {s.get("source", "unknown") for s in segments}
    source = (
        "aligned"
        if "aligned" in sources
        else sources.pop() if sources else "unknown"
    )

    # Get slide number (most common in this chunk)
    slide_numbers = [
        s.get("slide_number")
        for s in segments
        if s.get("slide_number") is not None
    ]
    slide_number = (
        max(set(slide_numbers), key=slide_numbers.count)
        if slide_numbers
        else None
    )

    return {
        "content": " ".join(texts),
        "start_time": segments[0].get("start"),
        "end_time": segments[-1].get("end"),
        "slide_number": slide_number,
        "metadata": {"source": source},
    }


def estimate_tokens(text: str) -> int:
    """Estimate token count from text. Conservative estimate."""
    return int(len(text.split()) * TOKEN_ESTIMATE_FACTOR)


EMBED_BATCH_SIZE = 100


async def embed_chunks(chunks: list[dict]) -> list[dict]:
    """Batch embed all chunks using gemini-embedding-001.

    Args:
        chunks: List of chunk dicts with 'content' field.

    Returns:
        Same chunks with 'embedding' field added (768-dim vector).

    Raises:
        EmbeddingError: If embedding generation fails.
    """
    if not chunks:
        return []

    client = genai.Client()
    texts = [c["content"] for c in chunks]

    all_embeddings: list[list[float]] = []

    for i in range(0, len(texts), EMBED_BATCH_SIZE):
        batch_texts = texts[i : i + EMBED_BATCH_SIZE]

        try:
            response = await client.aio.models.embed_content(
                model="gemini-embedding-001",
                contents=batch_texts,
                config={"task_type": "RETRIEVAL_DOCUMENT"},
            )

            for emb in response.embeddings:
                all_embeddings.append(emb.values)

        except Exception as e:
            logger.error("Embedding batch %d failed: %s", i // EMBED_BATCH_SIZE, e)
            raise EmbeddingError(f"Embedding generation failed: {e}") from e

    for chunk, embedding in zip(chunks, all_embeddings, strict=False):
        chunk["embedding"] = embedding

    logger.info(
        "Embedding complete: %d chunks embedded with 768-dim vectors",
        len(chunks),
    )
    return chunks


async def embed_concepts(concepts: list[dict]) -> list[dict]:
    """Embed concept titles + descriptions for semantic matching.

    Args:
        concepts: List of concept dicts with 'title' and 'description' fields.

    Returns:
        Same concepts with 'embedding' field added (768-dim vector).

    Raises:
        EmbeddingError: If embedding generation fails.
    """
    if not concepts:
        return []

    client = genai.Client()
    texts = [f"{c['title']}: {c.get('description', '')}" for c in concepts]

    try:
        response = await client.aio.models.embed_content(
            model="gemini-embedding-001",
            contents=texts,
            config={"task_type": "RETRIEVAL_DOCUMENT"},
        )

        for concept, emb in zip(concepts, response.embeddings, strict=False):
            concept["embedding"] = emb.values

    except Exception as e:
        logger.error("Concept embedding failed: %s", e)
        raise EmbeddingError(f"Concept embedding failed: {e}") from e

    logger.info("Concept embedding complete: %d concepts", len(concepts))
    return concepts


class EmbeddingError(Exception):
    """Raised when embedding generation fails."""
