"""Supabase JWT authentication dependency for FastAPI."""

from __future__ import annotations

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from supabase import Client as SupabaseClient
from supabase import create_client

from lecturelink_api.config import Settings, get_settings

_bearer = HTTPBearer()


def _get_supabase(settings: Settings) -> SupabaseClient:
    return create_client(settings.SUPABASE_URL, settings.SUPABASE_ANON_KEY)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer),
    settings: Settings = Depends(get_settings),
) -> dict:
    """Validate a Supabase JWT and return the authenticated user."""
    token = credentials.credentials
    supabase = _get_supabase(settings)
    try:
        resp = supabase.auth.get_user(token)
        if resp.user is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired token",
            )
        return {"id": resp.user.id, "email": resp.user.email, "token": token}
    except Exception as exc:
        if isinstance(exc, HTTPException):
            raise
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        ) from exc
