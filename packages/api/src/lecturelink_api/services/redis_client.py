"""Async Redis connection pool, cache helpers, and FastAPI dependency."""

from __future__ import annotations

import json
import logging
from typing import Any

from redis.asyncio import Redis

logger = logging.getLogger(__name__)

_pool: Redis | None = None


async def get_redis_pool(redis_url: str) -> Redis:
    """Create and return the global async Redis connection pool."""
    global _pool
    if _pool is None:
        r = Redis.from_url(
            redis_url,
            decode_responses=True,
            max_connections=20,
            socket_connect_timeout=3,
            socket_timeout=3,
        )
        # Verify connectivity before storing
        await r.ping()
        _pool = r
        logger.info("Redis pool created: %s", redis_url)
    return _pool


async def close_redis_pool() -> None:
    """Close the global Redis connection pool."""
    global _pool
    if _pool is not None:
        await _pool.aclose()
        _pool = None
        logger.info("Redis pool closed")


def get_redis() -> Redis | None:
    """FastAPI dependency returning the current Redis pool (or None if unavailable)."""
    return _pool


# ---------------------------------------------------------------------------
# Cache helpers
# ---------------------------------------------------------------------------


async def cache_get(key: str) -> Any | None:
    """Get a JSON-deserialized value from the cache."""
    if _pool is None:
        return None
    raw = await _pool.get(key)
    if raw is None:
        return None
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return raw


async def cache_set(key: str, value: Any, ttl: int = 60) -> None:
    """Set a JSON-serialized value in the cache with a TTL (seconds)."""
    if _pool is None:
        return
    await _pool.set(key, json.dumps(value, default=str), ex=ttl)


async def cache_delete(key: str) -> None:
    """Delete a cache key."""
    if _pool is None:
        return
    await _pool.delete(key)
