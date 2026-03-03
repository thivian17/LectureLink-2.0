"""Tests for gamification router endpoints."""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from lecturelink_api.main import app

FAKE_USER_ID = str(uuid.uuid4())
FAKE_TOKEN = "fake-jwt-token"
COURSE_ID = str(uuid.uuid4())
ASSESSMENT_ID = str(uuid.uuid4())


def _fake_user():
    return {"id": FAKE_USER_ID, "email": "test@uni.edu", "token": FAKE_TOKEN}


def _mock_execute(data):
    resp = MagicMock()
    resp.data = data
    resp.count = 0
    return resp


def _mock_chain(final_data):
    chain = MagicMock()
    chain.execute.return_value = _mock_execute(final_data)
    for method in ("select", "eq", "in_", "order", "limit", "single",
                    "gte", "lte", "insert", "upsert", "update"):
        getattr(chain, method).return_value = chain
    return chain


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
# Tests
# ---------------------------------------------------------------------------


class TestGetState:
    @pytest.mark.asyncio
    async def test_returns_gamification_state(self, client):
        mock_state = {
            "streak": {"current": 5, "longest": 10, "studied_today": True, "freeze_available": True},
            "level": {"current": 3, "total_xp": 400, "xp_to_next": 200, "progress_percent": 33.3},
            "today_xp": 50,
            "badges_count": 2,
            "recent_badges": [],
        }
        with patch(
            "lecturelink_api.routers.gamification.get_user_gamification",
            new_callable=AsyncMock,
            return_value=mock_state,
        ), patch(
            "lecturelink_api.routers.gamification.create_client",
        ) as mock_create:
            mock_sb = MagicMock()
            mock_sb.auth = MagicMock()
            mock_create.return_value = mock_sb

            resp = await client.get("/api/gamification/state")

        assert resp.status_code == 200
        data = resp.json()
        assert data["streak"]["current_streak"] == 5
        assert data["level"]["current_level"] == 3
        assert data["today_xp"] == 50


class TestXPHistory:
    @pytest.mark.asyncio
    async def test_returns_xp_history(self, client):
        mock_history = [
            {"date": "2025-01-01", "xp": 100},
            {"date": "2025-01-02", "xp": 50},
        ]
        with patch(
            "lecturelink_api.routers.gamification.get_xp_history",
            new_callable=AsyncMock,
            return_value=mock_history,
        ), patch(
            "lecturelink_api.routers.gamification.create_client",
        ) as mock_create:
            mock_sb = MagicMock()
            mock_sb.auth = MagicMock()
            mock_create.return_value = mock_sb

            resp = await client.get("/api/gamification/xp/history?days=7")

        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 2


class TestStreakFreeze:
    @pytest.mark.asyncio
    async def test_freeze_success(self, client):
        with patch(
            "lecturelink_api.routers.gamification.use_streak_freeze",
            new_callable=AsyncMock,
            return_value={"success": True, "freezes_remaining": 0},
        ), patch(
            "lecturelink_api.routers.gamification.create_client",
        ) as mock_create:
            mock_sb = MagicMock()
            mock_sb.auth = MagicMock()
            mock_create.return_value = mock_sb

            resp = await client.post("/api/gamification/streak/freeze")

        assert resp.status_code == 200
        assert resp.json()["success"] is True

    @pytest.mark.asyncio
    async def test_freeze_fails_no_available(self, client):
        with patch(
            "lecturelink_api.routers.gamification.use_streak_freeze",
            new_callable=AsyncMock,
            return_value={"success": False, "freezes_remaining": 0},
        ), patch(
            "lecturelink_api.routers.gamification.create_client",
        ) as mock_create:
            mock_sb = MagicMock()
            mock_sb.auth = MagicMock()
            mock_create.return_value = mock_sb

            resp = await client.post("/api/gamification/streak/freeze")

        assert resp.status_code == 400


class TestBadges:
    @pytest.mark.asyncio
    async def test_returns_badges(self, client):
        mock_badges = {
            "earned": [{"badge_id": "streak_3", "name": "3-Day Starter",
                        "description": "desc", "icon": "flame",
                        "category": "streak", "earned_at": "2025-01-01"}],
            "available": [],
            "total_earned": 1,
            "total_available": 20,
        }
        with patch(
            "lecturelink_api.routers.gamification.get_user_badges",
            new_callable=AsyncMock,
            return_value=mock_badges,
        ), patch(
            "lecturelink_api.routers.gamification.create_client",
        ) as mock_create:
            mock_sb = MagicMock()
            mock_sb.auth = MagicMock()
            mock_create.return_value = mock_sb

            resp = await client.get("/api/gamification/badges")

        assert resp.status_code == 200
        assert resp.json()["total_earned"] == 1


class TestReadiness:
    @pytest.mark.asyncio
    async def test_returns_readiness_list(self, client):
        mock_readiness = [
            {
                "assessment_id": ASSESSMENT_ID,
                "title": "Midterm",
                "due_date": None,
                "weight_percent": 30.0,
                "type": "exam",
                "readiness_score": 65.0,
                "days_until_due": 10,
                "urgency": "strong",
                "trend": 0.0,
                "concept_scores": [],
            }
        ]
        with patch(
            "lecturelink_api.routers.gamification.get_all_assessment_readiness",
            new_callable=AsyncMock,
            return_value=mock_readiness,
        ), patch(
            "lecturelink_api.routers.gamification.create_client",
        ) as mock_create:
            mock_sb = MagicMock()
            mock_sb.auth = MagicMock()
            mock_create.return_value = mock_sb

            resp = await client.get("/api/gamification/readiness")

        assert resp.status_code == 200
        assert len(resp.json()) == 1


class TestReadinessDetail:
    @pytest.mark.asyncio
    async def test_returns_single_readiness(self, client):
        mock_result = {
            "assessment_id": ASSESSMENT_ID,
            "title": "Midterm",
            "due_date": None,
            "weight_percent": 30.0,
            "type": "exam",
            "readiness_score": 72.5,
            "days_until_due": 5,
            "urgency": "strong",
            "trend": 2.5,
            "concept_scores": [],
        }
        with patch(
            "lecturelink_api.routers.gamification.get_assessment_readiness",
            new_callable=AsyncMock,
            return_value=mock_result,
        ), patch(
            "lecturelink_api.routers.gamification.create_client",
        ) as mock_create:
            mock_sb = MagicMock()
            mock_sb.auth = MagicMock()
            mock_create.return_value = mock_sb

            resp = await client.get(f"/api/gamification/readiness/{ASSESSMENT_ID}")

        assert resp.status_code == 200
        assert resp.json()["readiness_score"] == 72.5

    @pytest.mark.asyncio
    async def test_not_found(self, client):
        with patch(
            "lecturelink_api.routers.gamification.get_assessment_readiness",
            new_callable=AsyncMock,
            return_value={"assessment_id": "x", "readiness_score": 0, "error": "not_found"},
        ), patch(
            "lecturelink_api.routers.gamification.create_client",
        ) as mock_create:
            mock_sb = MagicMock()
            mock_sb.auth = MagicMock()
            mock_create.return_value = mock_sb

            resp = await client.get("/api/gamification/readiness/nonexistent")

        assert resp.status_code == 404


class TestCourseReadiness:
    @pytest.mark.asyncio
    async def test_returns_summary(self, client):
        mock_result = {
            "course_id": COURSE_ID,
            "course_name": "Physics 101",
            "overall_readiness": 65.0,
            "next_assessment": None,
            "concepts_mastered": 3,
            "concepts_total": 10,
        }
        with patch(
            "lecturelink_api.routers.gamification.get_course_readiness_summary",
            new_callable=AsyncMock,
            return_value=mock_result,
        ), patch(
            "lecturelink_api.routers.gamification.create_client",
        ) as mock_create:
            mock_sb = MagicMock()
            mock_sb.auth = MagicMock()
            mock_create.return_value = mock_sb

            resp = await client.get(f"/api/gamification/courses/{COURSE_ID}/readiness")

        assert resp.status_code == 200
        assert resp.json()["course_name"] == "Physics 101"


class TestGradeProjection:
    @pytest.mark.asyncio
    async def test_returns_projection(self, client):
        mock_result = {
            "projected_grade_low": 80.0,
            "projected_grade_high": 90.0,
            "grade_letter": "B+",
            "completed_assessments": [],
            "upcoming_assessments": [],
        }
        with patch(
            "lecturelink_api.routers.gamification.get_grade_projection",
            new_callable=AsyncMock,
            return_value=mock_result,
        ), patch(
            "lecturelink_api.routers.gamification.create_client",
        ) as mock_create:
            mock_sb = MagicMock()
            mock_sb.auth = MagicMock()
            mock_create.return_value = mock_sb

            resp = await client.get(f"/api/gamification/courses/{COURSE_ID}/grade-projection")

        assert resp.status_code == 200
        assert resp.json()["grade_letter"] == "B+"


class TestWeeklyProgress:
    @pytest.mark.asyncio
    async def test_returns_weekly_progress(self, client):
        with patch(
            "lecturelink_api.routers.gamification.create_client",
        ) as mock_create:
            mock_sb = MagicMock()
            mock_sb.auth = MagicMock()
            mock_sb.table.return_value = _mock_chain([])
            mock_create.return_value = mock_sb

            with patch(
                "lecturelink_api.routers.gamification.get_xp_history",
                new_callable=AsyncMock,
                return_value=[{"date": "2025-01-01", "xp": 0}] * 7,
            ):
                resp = await client.get("/api/gamification/weekly-progress")

        assert resp.status_code == 200
        data = resp.json()
        assert data["sessions_count"] == 0
        assert data["total_xp"] == 0
