"""Supabase JWT authentication dependency for FastAPI with Redis JWT cache."""

from __future__ import annotations

import hashlib
import logging

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from supabase import Client as SupabaseClient
from supabase import create_client

from lecturelink_api.config import Settings, get_settings

logger = logging.getLogger(__name__)

_bearer = HTTPBearer()


def _get_supabase(settings: Settings) -> SupabaseClient:
    return create_client(settings.SUPABASE_URL, settings.SUPABASE_ANON_KEY)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer),
    settings: Settings = Depends(get_settings),
) -> dict:
    """Validate a Supabase JWT and return the authenticated user.

    Uses Redis to cache validated JWTs for 60 seconds to avoid hitting
    the Supabase Auth API on every request.
    """
    token = credentials.credentials

    # Try Redis cache first
    cache_key = f"jwt:{hashlib.sha256(token.encode()).hexdigest()[:16]}"
    try:
        from lecturelink_api.services.redis_client import cache_get, cache_set

        cached = await cache_get(cache_key)
        if cached is not None:
            return {**cached, "token": token}
    except Exception:
        pass  # Redis unavailable — fall through to Supabase

    # Validate against Supabase Auth API
    supabase = _get_supabase(settings)
    try:
        resp = supabase.auth.get_user(token)
        if resp.user is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired token",
            )
        user_data = {"id": resp.user.id, "email": resp.user.email}

        # Cache the result
        try:
            from lecturelink_api.services.redis_client import cache_set

            await cache_set(cache_key, user_data, ttl=60)
        except Exception:
            pass

        return {**user_data, "token": token}
    except Exception as exc:
        if isinstance(exc, HTTPException):
            raise
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        ) from exc


def get_authenticated_supabase(user: dict, settings: Settings) -> SupabaseClient:
    """Create a Supabase client authenticated with the user's JWT.

    Shared helper to replace per-router ``_sb()`` functions.
    """
    client = create_client(settings.SUPABASE_URL, settings.SUPABASE_ANON_KEY)
    client.auth.set_session(user["token"], "")
    return client
