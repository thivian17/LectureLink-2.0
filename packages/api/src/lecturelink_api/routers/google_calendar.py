"""Google Calendar integration routes."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from supabase import create_client

from lecturelink_api.auth import get_current_user
from lecturelink_api.config import Settings, get_settings
from lecturelink_api.models.google_calendar import (
    GoogleTokensRequest,
    SyncResultResponse,
    SyncStatusResponse,
    ToggleSyncRequest,
)
from lecturelink_api.services.google_calendar import sync_all_assessments

router = APIRouter(tags=["google-calendar"])


def _sb_service(settings: Settings):
    """Supabase client with service key (bypasses RLS for token storage)."""
    if not settings.SUPABASE_SERVICE_KEY:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Service key not configured",
        )
    return create_client(settings.SUPABASE_URL, settings.SUPABASE_SERVICE_KEY)


def _sb_user(user: dict, settings: Settings):
    """Supabase client authenticated as the user (respects RLS)."""
    client = create_client(settings.SUPABASE_URL, settings.SUPABASE_ANON_KEY)
    client.auth.set_session(user["token"], "")
    return client


@router.post("/api/google/tokens", status_code=status.HTTP_204_NO_CONTENT)
async def store_tokens(
    body: GoogleTokensRequest,
    user: dict = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
):
    """Store Google OAuth tokens from the frontend callback."""
    sb = _sb_service(settings)
    sb.table("user_google_tokens").upsert(
        {
            "user_id": user["id"],
            "access_token": body.access_token,
            "refresh_token": body.refresh_token,
            "scopes": ["https://www.googleapis.com/auth/calendar.events"],
            "updated_at": datetime.now(timezone.utc).isoformat(),
        },
        on_conflict="user_id",
    ).execute()


@router.delete("/api/google/tokens", status_code=status.HTTP_204_NO_CONTENT)
async def disconnect_google(
    user: dict = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
):
    """Remove stored Google tokens (disconnect Google account)."""
    sb = _sb_service(settings)
    sb.table("user_google_tokens").delete().eq("user_id", user["id"]).execute()


@router.get("/api/google/sync/status", response_model=SyncStatusResponse)
async def get_sync_status(
    user: dict = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
):
    """Check whether Google is connected and sync is enabled."""
    sb = _sb_service(settings)
    result = (
        sb.table("user_google_tokens")
        .select("calendar_sync_enabled, refresh_token")
        .eq("user_id", user["id"])
        .maybe_single()
        .execute()
    )
    if not result.data:
        return SyncStatusResponse(
            connected=False, calendar_sync_enabled=False, has_refresh_token=False
        )
    return SyncStatusResponse(
        connected=True,
        calendar_sync_enabled=result.data["calendar_sync_enabled"],
        has_refresh_token=bool(result.data.get("refresh_token")),
    )


@router.post("/api/google/sync", response_model=SyncResultResponse)
async def trigger_sync(
    user: dict = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
):
    """Manually trigger a full calendar sync for all assessments."""
    sb = _sb_service(settings)
    sb_u = _sb_user(user, settings)

    try:
        counts = await sync_all_assessments(
            sb_service=sb,
            sb_user=sb_u,
            user_id=user["id"],
            client_id=settings.GOOGLE_OAUTH_CLIENT_ID,
            client_secret=settings.GOOGLE_OAUTH_CLIENT_SECRET,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
        ) from exc

    return SyncResultResponse(**counts)


@router.put("/api/google/sync/toggle", status_code=status.HTTP_204_NO_CONTENT)
async def toggle_sync(
    body: ToggleSyncRequest,
    user: dict = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
):
    """Enable or disable automatic calendar sync."""
    sb = _sb_service(settings)
    result = (
        sb.table("user_google_tokens")
        .update(
            {
                "calendar_sync_enabled": body.enabled,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }
        )
        .eq("user_id", user["id"])
        .execute()
    )
    if not result.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Google account not connected",
        )
