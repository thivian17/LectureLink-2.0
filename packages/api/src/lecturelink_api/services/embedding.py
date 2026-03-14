"""Query and batch embedding via Gemini embedding model."""

from __future__ import annotations

import asyncio
import logging

from .genai_client import get_genai_client as _get_client
from .genai_client import reset_genai_client

logger = logging.getLogger(__name__)

EMBEDDING_MODEL = "gemini-embedding-001"
EMBEDDING_DIMENSIONS = 2000
_EMBED_MAX_RETRIES = 3
_EMBED_BASE_DELAY = 2


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
    except RuntimeError as e:
        if "Event loop is closed" in str(e):
            logger.warning("Stale embedding client detected, recreating")
            reset_genai_client()
            result = await _get_client().aio.models.embed_content(
                model=EMBEDDING_MODEL,
                contents=query,
                config={
                    "task_type": "RETRIEVAL_QUERY",
                    "output_dimensionality": EMBEDDING_DIMENSIONS,
                },
            )
            return result.embeddings[0].values
        raise
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
        batch_num = i // batch_size

        for attempt in range(_EMBED_MAX_RETRIES):
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
                break
            except RuntimeError as e:
                if "Event loop is closed" in str(e):
                    logger.warning("Stale embedding client detected, recreating")
                    reset_genai_client()
                    continue
                raise
            except Exception as e:
                if attempt < _EMBED_MAX_RETRIES - 1:
                    delay = _EMBED_BASE_DELAY * (2 ** attempt)
                    logger.warning(
                        "Batch %d embedding failed (attempt %d/%d), retrying in %ds: %s",
                        batch_num, attempt + 1, _EMBED_MAX_RETRIES, delay, e,
                    )
                    await asyncio.sleep(delay)
                else:
                    logger.error("Batch %d embedding failed after %d attempts: %s", batch_num, _EMBED_MAX_RETRIES, e)
                    raise

    return embeddings
