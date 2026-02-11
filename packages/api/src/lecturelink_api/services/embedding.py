"""Query and batch embedding via Gemini embedding model."""

from __future__ import annotations

import logging

from google import genai

logger = logging.getLogger(__name__)

EMBEDDING_MODEL = "gemini-embedding-001"
EMBEDDING_DIMENSIONS = 2000

_client = None


def _get_client():
    """Lazy singleton for the Gemini client (avoids import-time failure)."""
    global _client
    if _client is None:
        _client = genai.Client()
    return _client


async def embed_query(query: str) -> list[float]:
    """Generate embedding for a search query.

    Uses RETRIEVAL_QUERY task type — this is different from the
    RETRIEVAL_DOCUMENT task type used when indexing chunks.
    The model optimizes the embedding based on the task type.

    Returns:
        2000-dimensional embedding vector
    """
    try:
        result = await _get_client().aio.models.embed_content(
            model=EMBEDDING_MODEL,
            contents=query,
            config={
                "task_type": "RETRIEVAL_QUERY",
                "output_dimensionality": EMBEDDING_DIMENSIONS,
            },
        )
        return result.embeddings[0].values
    except Exception as e:
        logger.error(f"Query embedding failed: {e}")
        raise


async def embed_texts(
    texts: list[str], task_type: str = "RETRIEVAL_DOCUMENT"
) -> list[list[float]]:
    """Batch embed multiple texts. Used by A4 chunker and concept extractor.

    Args:
        texts: list of strings to embed
        task_type: RETRIEVAL_DOCUMENT for indexing, RETRIEVAL_QUERY for search,
                   SEMANTIC_SIMILARITY for comparison

    Returns:
        list of 2000-dimensional embedding vectors
    """
    if not texts:
        return []

    embeddings: list[list[float]] = []
    batch_size = 100  # API limit

    for i in range(0, len(texts), batch_size):
        batch = texts[i : i + batch_size]
        try:
            result = await _get_client().aio.models.embed_content(
                model=EMBEDDING_MODEL,
                contents=batch,
                config={
                    "task_type": task_type,
                    "output_dimensionality": EMBEDDING_DIMENSIONS,
                },
            )
            embeddings.extend([e.values for e in result.embeddings])
        except Exception as e:
            logger.error(f"Batch embedding failed for batch {i // batch_size}: {e}")
            raise

    return embeddings
