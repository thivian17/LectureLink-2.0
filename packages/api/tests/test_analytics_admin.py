"""Tests for Analytics and Admin router endpoints."""

from __future__ import annotations

import uuid
from unittest.mock import MagicMock, patch

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from lecturelink_api.main import app

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

FAKE_USER_ID = str(uuid.uuid4())
FAKE_EMAIL = "test@university.edu"
FAKE_TOKEN = "fake-jwt-token"


def _fake_user():
    return {"id": FAKE_USER_ID, "email": FAKE_EMAIL, "token": FAKE_TOKEN}


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def _override_auth():
    from lecturelink_api.auth import get_current_user

    app.dependency_overrides[get_current_user] = lambda: _fake_user()
    yield
    app.dependency_overrides.pop(get_current_user, None)


@pytest.fixture()
def _override_settings():
    from lecturelink_api.config import Settings, get_settings

    fake_settings = Settings(
        SUPABASE_URL="https://fake.supabase.co",
        SUPABASE_ANON_KEY="fake-anon-key",
    )
    app.dependency_overrides[get_settings] = lambda: fake_settings
    yield fake_settings
    app.dependency_overrides.pop(get_settings, None)


@pytest_asyncio.fixture()
async def client(_override_auth, _override_settings):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


# ---------------------------------------------------------------------------
# Analytics Ingest Tests
# ---------------------------------------------------------------------------


class TestAnalyticsIngest:
    @pytest.mark.asyncio
    async def test_ingest_events_returns_204(self, client):
        with patch("lecturelink_api.routers.analytics.create_client") as mock_create:
            sb = MagicMock()
            mock_create.return_value = sb
            sb.table.return_value.insert.return_value.execute.return_value = MagicMock(
                data=[]
            )

            resp = await client.post(
                "/api/analytics/events",
                json={
                    "events": [
                        {
                            "event_type": "page_view",
                            "event_category": "navigation",
                            "page_path": "/dashboard",
                        },
                        {
                            "event_type": "quiz_started",
                            "event_category": "engagement",
                        },
                    ],
                    "session_id": "sess-abc",
                },
            )

        assert resp.status_code == 204

    @pytest.mark.asyncio
    async def test_bug_report_returns_201(self, client):
        with patch("lecturelink_api.routers.analytics.create_client") as mock_create:
            sb = MagicMock()
            mock_create.return_value = sb
            sb.table.return_value.insert.return_value.execute.return_value = MagicMock(
                data=[{"id": "bug-1"}]
            )

            resp = await client.post(
                "/api/analytics/bug-report",
                json={
                    "title": "Button not working",
                    "description": "The submit button on the quiz page does not respond to clicks.",
                    "severity": "high",
                    "page_path": "/quiz/123",
                },
            )

        assert resp.status_code == 201
        assert resp.json()["id"] == "bug-1"

    @pytest.mark.asyncio
    async def test_feedback_returns_201(self, client):
        with patch("lecturelink_api.routers.analytics.create_client") as mock_create:
            sb = MagicMock()
            mock_create.return_value = sb
            sb.table.return_value.insert.return_value.execute.return_value = MagicMock(
                data=[{"id": "fb-1"}]
            )

            resp = await client.post(
                "/api/analytics/feedback",
                json={
                    "feedback_type": "nps",
                    "rating": 9,
                    "message": "Great app!",
                    "feature_tag": "tutor",
                },
            )

        assert resp.status_code == 201
        assert resp.json()["id"] == "fb-1"


# ---------------------------------------------------------------------------
# Admin Auth Tests
# ---------------------------------------------------------------------------


class TestAdminAuth:
    @pytest.mark.asyncio
    async def test_overview_requires_admin(self, client):
        """GET /api/admin/overview returns 403 when user is NOT an admin."""
        with patch("lecturelink_api.routers.admin.create_client") as mock_create:
            sb = MagicMock()
            mock_create.return_value = sb
            # admin_users query returns empty → not an admin
            sb.table.return_value.select.return_value.eq.return_value.execute.return_value = MagicMock(
                data=[]
            )

            resp = await client.get("/api/admin/overview")

        assert resp.status_code == 403
        assert "Admin access required" in resp.json()["detail"]
