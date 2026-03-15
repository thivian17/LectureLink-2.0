"""Tests for the Dashboard V2 router endpoints."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from lecturelink_api.auth import get_current_user
from lecturelink_api.config import Settings, get_settings
from lecturelink_api.main import app
from lecturelink_api.models.readiness_v2 import (
    AssessmentReadinessV2,
    CourseIntelligenceV2,
    DashboardActionsResponse,
    DashboardCoursesResponse,
    DashboardTimelineResponse,
    ReadinessBreakdown,
    StatsRow,
    SuggestedAction,
)

FAKE_USER = {"id": "user-123", "email": "test@test.edu", "token": "fake.jwt.token"}
FAKE_SETTINGS = Settings(
    SUPABASE_URL="https://fake.supabase.co",
    SUPABASE_ANON_KEY="fake-key",
)

_MOCK_SB = "lecturelink_api.routers.dashboard_v2.create_client"


@pytest.fixture(autouse=True)
def _override_deps():
    app.dependency_overrides[get_current_user] = lambda: FAKE_USER
    app.dependency_overrides[get_settings] = lambda: FAKE_SETTINGS
    yield
    app.dependency_overrides.clear()


@pytest.fixture(autouse=True)
def _mock_supabase():
    """Prevent real Supabase client creation in all tests."""
    mock_client = MagicMock()
    with patch(_MOCK_SB, return_value=mock_client):
        yield mock_client


@pytest_asyncio.fixture()
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest_asyncio.fixture()
async def unauth_client():
    """Client without auth override."""
    app.dependency_overrides.pop(get_current_user, None)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


# ---------------------------------------------------------------------------
# Timeline
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_timeline_returns_items(client):
    mock_resp = DashboardTimelineResponse(items=[], today="2026-03-14")
    with patch(
        "lecturelink_api.routers.dashboard_v2.get_academic_timeline",
        new_callable=AsyncMock,
        return_value=mock_resp,
    ):
        resp = await client.get("/api/dashboard/timeline")
    assert resp.status_code == 200
    body = resp.json()
    assert "items" in body
    assert body["today"] == "2026-03-14"


@pytest.mark.asyncio
async def test_timeline_respects_days_param(client):
    mock_resp = DashboardTimelineResponse(items=[], today="2026-03-14")
    with patch(
        "lecturelink_api.routers.dashboard_v2.get_academic_timeline",
        new_callable=AsyncMock,
        return_value=mock_resp,
    ) as mock_fn:
        resp = await client.get("/api/dashboard/timeline?days=7")
    assert resp.status_code == 200
    mock_fn.assert_called_once()
    # days=7 is the third positional arg (sb, user_id, days)
    assert mock_fn.call_args.args[2] == 7


@pytest.mark.asyncio
async def test_timeline_validates_days_range(client):
    with patch(
        "lecturelink_api.routers.dashboard_v2.get_academic_timeline",
        new_callable=AsyncMock,
    ):
        resp = await client.get("/api/dashboard/timeline?days=0")
    assert resp.status_code == 422

    with patch(
        "lecturelink_api.routers.dashboard_v2.get_academic_timeline",
        new_callable=AsyncMock,
    ):
        resp = await client.get("/api/dashboard/timeline?days=31")
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# Actions
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_actions_returns_list(client):
    mock_resp = DashboardActionsResponse(actions=[])
    with patch(
        "lecturelink_api.routers.dashboard_v2.get_best_next_actions",
        new_callable=AsyncMock,
        return_value=mock_resp,
    ):
        resp = await client.get("/api/dashboard/actions")
    assert resp.status_code == 200
    assert "actions" in resp.json()


@pytest.mark.asyncio
async def test_actions_respects_limit_param(client):
    mock_resp = DashboardActionsResponse(actions=[])
    with patch(
        "lecturelink_api.routers.dashboard_v2.get_best_next_actions",
        new_callable=AsyncMock,
        return_value=mock_resp,
    ) as mock_fn:
        resp = await client.get("/api/dashboard/actions?limit=2")
    assert resp.status_code == 200
    mock_fn.assert_called_once()
    assert mock_fn.call_args.args[2] == 2


# ---------------------------------------------------------------------------
# Courses
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_courses_returns_list(client):
    mock_courses = [
        CourseIntelligenceV2(
            course_id="c1",
            course_name="Physics",
            readiness=0.75,
            risk="low",
            assessment_count=2,
        )
    ]
    with patch(
        "lecturelink_api.routers.dashboard_v2.get_all_course_readiness",
        new_callable=AsyncMock,
        return_value=mock_courses,
    ):
        resp = await client.get("/api/dashboard/courses")
    assert resp.status_code == 200
    body = resp.json()
    assert "courses" in body
    assert len(body["courses"]) == 1
    assert body["courses"][0]["course_id"] == "c1"


# ---------------------------------------------------------------------------
# Readiness detail
# ---------------------------------------------------------------------------

_SAMPLE_READINESS = AssessmentReadinessV2(
    assessment_id="a1",
    title="Midterm 1",
    course_id="c1",
    course_name="Physics",
    assessment_type="exam",
    due_date="2026-04-01",
    days_until_due=18,
    readiness=0.62,
    breakdown=ReadinessBreakdown(
        coverage=0.8, practice=0.5, freshness=0.6, effort=0.4
    ),
    weak_concepts=[],
    suggested_actions=[
        SuggestedAction(
            action_type="practice_test",
            title="Practice Test",
            description="Focus on weak concepts",
            estimated_minutes=15,
            target_course_id="c1",
            target_assessment_id="a1",
            urgency="medium",
            expected_impact="+15% readiness",
        )
    ],
    urgency="medium",
    concept_count=10,
    covered_count=8,
)


@pytest.mark.asyncio
async def test_readiness_detail_returns_full_breakdown(client):
    with patch(
        "lecturelink_api.routers.dashboard_v2.compute_assessment_readiness",
        new_callable=AsyncMock,
        return_value=_SAMPLE_READINESS,
    ):
        resp = await client.get("/api/dashboard/readiness/a1")
    assert resp.status_code == 200
    body = resp.json()
    assert body["assessment_id"] == "a1"
    assert "breakdown" in body
    assert body["breakdown"]["coverage"] == 0.8
    assert len(body["suggested_actions"]) == 1


@pytest.mark.asyncio
async def test_readiness_not_found_returns_404(client):
    with patch(
        "lecturelink_api.routers.dashboard_v2.compute_assessment_readiness",
        new_callable=AsyncMock,
        side_effect=KeyError("not found"),
    ):
        resp = await client.get("/api/dashboard/readiness/nonexistent")
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Stats
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_stats_returns_weekly(client):
    mock_stats = StatsRow(
        streak=5,
        xp_this_week=320,
        study_minutes_this_week=180,
        concepts_practiced_this_week=24,
    )
    with patch(
        "lecturelink_api.routers.dashboard_v2.get_weekly_stats",
        new_callable=AsyncMock,
        return_value=mock_stats,
    ):
        resp = await client.get("/api/dashboard/stats")
    assert resp.status_code == 200
    body = resp.json()
    assert body["streak"] == 5
    assert body["xp_this_week"] == 320
    assert body["study_minutes_this_week"] == 180
    assert body["concepts_practiced_this_week"] == 24


# ---------------------------------------------------------------------------
# Auth — all endpoints require authentication
# ---------------------------------------------------------------------------

_PROTECTED_ENDPOINTS = [
    "/api/dashboard/timeline",
    "/api/dashboard/actions",
    "/api/dashboard/courses",
    "/api/dashboard/readiness/some-id",
    "/api/dashboard/stats",
]


@pytest.mark.asyncio
@pytest.mark.parametrize("endpoint", _PROTECTED_ENDPOINTS)
async def test_endpoints_require_auth(unauth_client, endpoint):
    resp = await unauth_client.get(endpoint)
    assert resp.status_code in (401, 403)
