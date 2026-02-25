"""Tests for study coach routes."""

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
    for method in ("select", "eq", "in_", "order", "limit", "single", "insert"):
        getattr(chain, method).return_value = chain
    return chain


def _mock_supabase(course_data=None):
    sb = MagicMock()
    sb.auth = MagicMock()
    sb.auth.set_session = MagicMock()
    sb.table.return_value = _mock_chain(
        course_data if course_data is not None else [{"id": COURSE_ID}]
    )
    return sb


def _performance_data():
    return {
        "overall": {
            "total_questions_attempted": 20,
            "overall_accuracy": 0.7,
            "quizzes_taken": 2,
            "average_quiz_score": 70.0,
            "strongest_category": "physics",
            "weakest_category": "math",
        },
        "concepts": [],
        "quiz_history": [],
        "weak_concepts": [],
        "strong_concepts": [],
    }


# ---------------------------------------------------------------------------
# Fixtures (same pattern as test_quiz_routes.py)
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
# Study Coach Chat
# ---------------------------------------------------------------------------


class TestStudyCoachChat:
    @pytest.mark.asyncio
    async def test_chat_returns_200(self, client):
        with (
            patch("lecturelink_api.routers.coach.create_client") as mock_create,
            patch("lecturelink_api.routers.coach.check_rate_limit"),
            patch(
                "lecturelink_api.services.coach.chat_with_coach",
                new_callable=AsyncMock,
            ) as mock_chat,
        ):
            mock_create.return_value = _mock_supabase()
            mock_chat.return_value = {
                "message": "Focus on entropy this week.",
                "recommendations": [
                    {"concept": "Entropy", "action": "Review lecture 3", "priority": "high"}
                ],
                "suggested_quiz": {"focus": None, "difficulty": "adaptive"},
            }

            resp = await client.post(
                f"/api/courses/{COURSE_ID}/study-coach/chat",
                json={"message": "What should I study?"},
            )

        assert resp.status_code == 200
        data = resp.json()
        assert "Focus on entropy" in data["message"]
        assert len(data["recommendations"]) == 1
        assert data["recommendations"][0]["concept"] == "Entropy"

    @pytest.mark.asyncio
    async def test_returns_404_for_missing_course(self, client):
        with (
            patch("lecturelink_api.routers.coach.create_client") as mock_create,
            patch("lecturelink_api.routers.coach.check_rate_limit"),
        ):
            mock_create.return_value = _mock_supabase(course_data=[])

            resp = await client.post(
                f"/api/courses/{COURSE_ID}/study-coach/chat",
                json={"message": "Help me study"},
            )

        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_rejects_empty_message(self, client):
        with (
            patch("lecturelink_api.routers.coach.create_client") as mock_create,
            patch("lecturelink_api.routers.coach.check_rate_limit"),
        ):
            mock_create.return_value = _mock_supabase()

            resp = await client.post(
                f"/api/courses/{COURSE_ID}/study-coach/chat",
                json={"message": ""},
            )

        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# Performance Endpoint
# ---------------------------------------------------------------------------


class TestPerformanceEndpoint:
    @pytest.mark.asyncio
    async def test_get_performance_returns_200(self, client):
        with (
            patch("lecturelink_api.routers.coach.create_client") as mock_create,
            patch(
                "lecturelink_api.services.performance.get_performance",
                new_callable=AsyncMock,
            ) as mock_perf,
        ):
            mock_create.return_value = _mock_supabase()
            mock_perf.return_value = _performance_data()

            resp = await client.get(f"/api/courses/{COURSE_ID}/performance")

        assert resp.status_code == 200
        data = resp.json()
        assert data["overall"]["quizzes_taken"] == 2

    @pytest.mark.asyncio
    async def test_performance_404_for_missing_course(self, client):
        with patch("lecturelink_api.routers.coach.create_client") as mock_create:
            mock_create.return_value = _mock_supabase(course_data=[])

            resp = await client.get(f"/api/courses/{COURSE_ID}/performance")

        assert resp.status_code == 404
