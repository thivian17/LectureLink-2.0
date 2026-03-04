"""Pydantic models for Google Calendar integration."""

from __future__ import annotations

from pydantic import BaseModel


class GoogleTokensRequest(BaseModel):
    access_token: str
    refresh_token: str | None = None


class ToggleSyncRequest(BaseModel):
    enabled: bool


class SyncStatusResponse(BaseModel):
    connected: bool
    calendar_sync_enabled: bool
    has_refresh_token: bool


class SyncResultResponse(BaseModel):
    created: int
    updated: int
    deleted: int
    errors: int
