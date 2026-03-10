"""Tests for Google Calendar integration (router + service)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from lecturelink_api.models.google_calendar import (
    GoogleTokensRequest,
    SyncStatusResponse,
    ToggleSyncRequest,
)
from lecturelink_api.services.google_calendar import (
    build_calendar_event,
)

# ---------------------------------------------------------------------------
# Unit tests: Pydantic models
# ---------------------------------------------------------------------------


class TestModels:
    def test_google_tokens_request(self):
        req = GoogleTokensRequest(access_token="abc", refresh_token="xyz")
        assert req.access_token == "abc"
        assert req.refresh_token == "xyz"

    def test_google_tokens_request_no_refresh(self):
        req = GoogleTokensRequest(access_token="abc")
        assert req.refresh_token is None

    def test_toggle_sync_request(self):
        req = ToggleSyncRequest(enabled=True)
        assert req.enabled is True

    def test_sync_status_response(self):
        resp = SyncStatusResponse(
            connected=True, calendar_sync_enabled=False, has_refresh_token=True
        )
        assert resp.connected is True
        assert resp.calendar_sync_enabled is False


# ---------------------------------------------------------------------------
# Unit tests: build_calendar_event
# ---------------------------------------------------------------------------


class TestBuildCalendarEvent:
    def test_basic_event(self):
        assessment = {
            "title": "Midterm 1",
            "due_date": "2026-03-15T00:00:00",
            "type": "exam",
            "weight_percent": 30,
        }
        course = {"name": "CS 101", "code": "CS101"}

        event = build_calendar_event(assessment, course)

        assert event["summary"] == "Midterm 1 — CS101"
        assert event["start"]["date"] == "2026-03-15"
        assert event["end"]["date"] == "2026-03-15"
        assert "Weight: 30%" in event["description"]
        assert "Course: CS 101" in event["description"]

    def test_event_without_code(self):
        assessment = {
            "title": "Final",
            "due_date": "2026-04-20T00:00:00",
            "type": None,
            "weight_percent": None,
        }
        course = {"name": "Physics 201", "code": None}

        event = build_calendar_event(assessment, course)

        assert event["summary"] == "Final — Physics 201"
        assert "Weight" not in event["description"]

    def test_event_reminders(self):
        assessment = {
            "title": "Quiz",
            "due_date": "2026-02-01T00:00:00",
            "type": "quiz",
            "weight_percent": 5,
        }
        course = {"name": "Math", "code": "MATH100"}

        event = build_calendar_event(assessment, course)

        assert event["reminders"]["useDefault"] is False
        assert len(event["reminders"]["overrides"]) == 2


# ---------------------------------------------------------------------------
# Router tests (via TestClient)
# ---------------------------------------------------------------------------


@pytest.fixture
def _mock_settings():
    mock_settings = MagicMock()
    mock_settings.SUPABASE_URL = "https://test.supabase.co"
    mock_settings.SUPABASE_ANON_KEY = "test-anon-key"
    mock_settings.SUPABASE_SERVICE_KEY = "test-service-key"
    mock_settings.GOOGLE_OAUTH_CLIENT_ID = "test-client-id"
    mock_settings.GOOGLE_OAUTH_CLIENT_SECRET = "test-client-secret"
    return mock_settings


@pytest.fixture
def _mock_user():
    return {"id": "user-123", "email": "test@example.com", "token": "mock-jwt"}


@pytest.fixture
def client(_mock_settings, _mock_user):
    from lecturelink_api.auth import get_current_user
    from lecturelink_api.config import get_settings
    from lecturelink_api.main import app

    app.dependency_overrides[get_settings] = lambda: _mock_settings
    app.dependency_overrides[get_current_user] = lambda: _mock_user

    with patch(
        "lecturelink_api.routers.google_calendar.create_client"
    ) as mock_create:
        mock_sb = MagicMock()
        mock_create.return_value = mock_sb
        yield TestClient(app), mock_sb

    app.dependency_overrides.clear()


class TestStoreTokens:
    def test_store_tokens_success(self, client):
        tc, mock_sb = client
        mock_sb.table.return_value.upsert.return_value.execute.return_value = MagicMock(
            data=[{"user_id": "user-123"}]
        )

        resp = tc.post(
            "/api/google/tokens",
            json={"access_token": "goog-token", "refresh_token": "goog-refresh"},
        )

        assert resp.status_code == 204
        mock_sb.table.assert_called_with("user_google_tokens")


class TestSyncStatus:
    def test_not_connected(self, client):
        tc, mock_sb = client
        mock_sb.table.return_value.select.return_value.eq.return_value.maybe_single.return_value.execute.return_value = MagicMock(
            data=None
        )

        resp = tc.get("/api/google/sync/status")

        assert resp.status_code == 200
        data = resp.json()
        assert data["connected"] is False
        assert data["calendar_sync_enabled"] is False

    def test_connected(self, client):
        tc, mock_sb = client
        mock_sb.table.return_value.select.return_value.eq.return_value.maybe_single.return_value.execute.return_value = MagicMock(
            data={"calendar_sync_enabled": True, "refresh_token": "rt"}
        )

        resp = tc.get("/api/google/sync/status")

        assert resp.status_code == 200
        data = resp.json()
        assert data["connected"] is True
        assert data["calendar_sync_enabled"] is True
        assert data["has_refresh_token"] is True


class TestDisconnect:
    def test_disconnect(self, client):
        tc, mock_sb = client
        mock_sb.table.return_value.delete.return_value.eq.return_value.execute.return_value = MagicMock(
            data=[]
        )

        resp = tc.delete("/api/google/tokens")

        assert resp.status_code == 204


class TestToggleSync:
    def test_toggle_on(self, client):
        tc, mock_sb = client
        mock_sb.table.return_value.update.return_value.eq.return_value.execute.return_value = MagicMock(
            data=[{"calendar_sync_enabled": True}]
        )

        resp = tc.put(
            "/api/google/sync/toggle",
            json={"enabled": True},
        )

        assert resp.status_code == 204

    def test_toggle_not_connected(self, client):
        tc, mock_sb = client
        mock_sb.table.return_value.update.return_value.eq.return_value.execute.return_value = MagicMock(
            data=[]
        )

        resp = tc.put(
            "/api/google/sync/toggle",
            json={"enabled": True},
        )

        assert resp.status_code == 404
