"""Rate limiting — Redis-based sliding window with DB fallback."""

import logging
from datetime import datetime, timedelta

from fastapi import HTTPException

logger = logging.getLogger(__name__)

RATE_LIMITS = {
    'quiz_generate': {'max_count': 10, 'window_hours': 24},
    'qa_question': {'max_count': 50, 'window_hours': 1},
    'lecture_upload': {'max_count': 30, 'window_hours': 24},
    'material_upload': {'max_count': 30, 'window_hours': 24},
    'study_coach': {'max_count': 30, 'window_hours': 1},
}


async def check_rate_limit_redis(redis, user_id: str, action: str) -> bool:
    """Check rate limit using Redis INCR + EXPIRE (sliding window).

    Returns True if within limit, raises HTTPException(429) if exceeded.
    """
    limits = RATE_LIMITS.get(action)
    if not limits:
        return True

    window_seconds = limits['window_hours'] * 3600
    key = f"rate:{user_id}:{action}"

    pipe = redis.pipeline()
    pipe.incr(key)
    pipe.ttl(key)
    count, ttl = await pipe.execute()

    # Set expiry on first request in window
    if ttl == -1:
        await redis.expire(key, window_seconds)

    if count > limits['max_count']:
        raise HTTPException(
            status_code=429,
            detail=(
                f"Rate limit exceeded for {action}."
                f" Max {limits['max_count']} per {limits['window_hours']}h."
            ),
            headers={"Retry-After": str(window_seconds)},
        )

    return True


def check_rate_limit(supabase, user_id: str, action: str) -> bool:
    """Check and record rate limit via Supabase DB (sync fallback).

    Raises HTTPException(429) if exceeded.
    """
    limits = RATE_LIMITS.get(action)
    if not limits:
        return True

    since = datetime.utcnow() - timedelta(hours=limits['window_hours'])
    result = (
        supabase.table('rate_limit_events')
        .select('id', count='exact')
        .eq('user_id', user_id)
        .eq('action', action)
        .gte('created_at', since.isoformat())
        .execute()
    )

    if (result.count or 0) >= limits['max_count']:
        retry_after = limits['window_hours'] * 3600  # seconds
        raise HTTPException(
            status_code=429,
            detail=(
                f"Rate limit exceeded for {action}."
                f" Max {limits['max_count']} per {limits['window_hours']}h."
            ),
            headers={"Retry-After": str(retry_after)},
        )

    # Record this event
    supabase.table('rate_limit_events').insert({
        'user_id': user_id,
        'action': action,
    }).execute()

    return True


def get_rate_limit_status(supabase, user_id: str, action: str) -> dict:
    """Get current usage for a rate limit."""
    limits = RATE_LIMITS.get(action, {'max_count': 0, 'window_hours': 24})
    since = datetime.utcnow() - timedelta(hours=limits['window_hours'])
    result = (
        supabase.table('rate_limit_events')
        .select('id', count='exact')
        .eq('user_id', user_id)
        .eq('action', action)
        .gte('created_at', since.isoformat())
        .execute()
    )
    return {
        'used': result.count or 0,
        'limit': limits['max_count'],
        'remaining': max(0, limits['max_count'] - (result.count or 0)),
        'resets_in_seconds': limits['window_hours'] * 3600,
    }
