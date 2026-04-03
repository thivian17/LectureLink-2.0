"""Tests for Learn Mode router endpoints."""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

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
    # Register the learn router if not already registered
    from lecturelink_api.routers.learn import router as learn_router
    # Check if already included
    already_included = any(
        getattr(r, "path", "").startswith("/api/learn")
        for r in app.routes
    )
    if not already_included:
        app.include_router(learn_router)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


# ---------------------------------------------------------------------------
# Start session tests
# ---------------------------------------------------------------------------


class TestStartSession:
    @pytest.mark.asyncio
    async def test_start_session_valid(self, client):
        course_id = str(uuid.uuid4())
        mock_result = {
            "session_id": "sess-1",
            "daily_briefing": {
                "course_name": "PHYS 201",
                "focus_description": "Entropy",
                "assessment_context": None,
                "time_budget": 15,
                "concepts_planned": [],
            },
            "flash_review_cards": [],
        }

        with (
            patch("lecturelink_api.auth.create_client") as mock_create,
            patch(
                "lecturelink_api.routers.learn.start_learn_session",
                new_callable=AsyncMock,
                return_value=mock_result,
            ),
        ):
            sb = MagicMock()
            mock_create.return_value = sb

            resp = await client.post(
                f"/api/learn/{course_id}/session/start",
                json={"time_budget_minutes": 15},
            )

        assert resp.status_code == 200
        data = resp.json()
        assert data["session_id"] == "sess-1"

    @pytest.mark.asyncio
    async def test_start_session_rejects_time_below_10(self, client):
        course_id = str(uuid.uuid4())

        with patch("lecturelink_api.auth.create_client"):
            resp = await client.post(
                f"/api/learn/{course_id}/session/start",
                json={"time_budget_minutes": 5},
            )

        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_start_session_rejects_time_above_25(self, client):
        course_id = str(uuid.uuid4())

        with patch("lecturelink_api.auth.create_client"):
            resp = await client.post(
                f"/api/learn/{course_id}/session/start",
                json={"time_budget_minutes": 30},
            )

        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# Auth tests
# ---------------------------------------------------------------------------


class TestAuthRequired:
    @pytest.mark.asyncio
    async def test_no_auth_returns_401_or_403(self):
        from lecturelink_api.auth import get_current_user
        from lecturelink_api.config import Settings, get_settings

        # Remove auth override
        app.dependency_overrides.pop(get_current_user, None)
        app.dependency_overrides[get_settings] = lambda: Settings(
            SUPABASE_URL="https://fake.supabase.co",
            SUPABASE_ANON_KEY="fake-anon-key",
        )

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            resp = await ac.post(
                f"/api/learn/{uuid.uuid4()}/session/start",
                json={"time_budget_minutes": 15},
            )

        assert resp.status_code in (401, 403)
        app.dependency_overrides.pop(get_settings, None)


# ---------------------------------------------------------------------------
# Session endpoint tests
# ---------------------------------------------------------------------------


class TestSessionEndpoints:
    @pytest.mark.asyncio
    async def test_get_session_not_found(self, client):
        with (
            patch("lecturelink_api.auth.create_client") as mock_create,
            patch(
                "lecturelink_api.routers.learn.get_session",
                new_callable=AsyncMock,
                return_value=None,
            ),
        ):
            sb = MagicMock()
            mock_create.return_value = sb

            resp = await client.get("/api/learn/session/nonexistent")

        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_get_concept_brief(self, client):
        mock_brief = {
            "concept_id": "c1",
            "concept_title": "Entropy",
            "sections": {
                "what_is_this": "Entropy is...",
                "why_it_matters": "It matters because...",
                "key_relationship": "dS = dQ/T",
            },
            "gut_check": {
                "question_text": "What is entropy?",
                "options": ["A", "B", "C"],
                "correct_index": 0,
                "explanation": "A is correct.",
            },
            "sources": [],
            "mastery_tier": "novice",
        }

        with (
            patch("lecturelink_api.auth.create_client") as mock_create,
            patch(
                "lecturelink_api.routers.learn.get_concept_brief",
                new_callable=AsyncMock,
                return_value=mock_brief,
            ),
        ):
            sb = MagicMock()
            mock_create.return_value = sb

            resp = await client.get("/api/learn/session/sess-1/concept/0")

        assert resp.status_code == 200
        data = resp.json()
        assert data["concept_title"] == "Entropy"

    @pytest.mark.asyncio
    async def test_submit_flash_review(self, client):
        mock_session = {
            "id": "sess-1",
            "user_id": FAKE_USER_ID,
            "session_data": {"flash_review_results": []},
        }
        mock_result = {
            "card_id": "card-1",
            "answer_index": 0,
            "time_ms": 1500,
            "answered_at": "2026-01-01T10:00:00+00:00",
        }

        with (
            patch("lecturelink_api.auth.create_client") as mock_create,
            patch(
                "lecturelink_api.routers.learn.get_session",
                new_callable=AsyncMock,
                return_value=mock_session,
            ),
            patch(
                "lecturelink_api.routers.learn.submit_flash_review_answer",
                new_callable=AsyncMock,
                return_value=mock_result,
            ),
        ):
            sb = MagicMock()
            mock_create.return_value = sb

            resp = await client.post(
                "/api/learn/session/sess-1/flash-review",
                json={"card_id": "card-1", "answer_index": 0, "time_ms": 1500},
            )

        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_complete_session(self, client):
        mock_result = {
            "session_summary": {
                "duration_minutes": 15,
                "concepts_covered": [],
                "quiz_score": {"correct": 5, "total": 8, "accuracy": 0.63},
                "combo_max": 3,
            },
            "xp_summary": {
                "total_earned": 100,
                "breakdown": [],
                "level_before": 1,
                "level_after": 1,
                "leveled_up": False,
            },
            "streak": {"current": 3, "longest": 5, "milestone_hit": False},
            "badges_earned": [],
            "tomorrow_preview": "Continue preparing for Thermodynamics",
        }

        with (
            patch("lecturelink_api.auth.create_client") as mock_create,
            patch(
                "lecturelink_api.routers.learn.complete_learn_session",
                new_callable=AsyncMock,
                return_value=mock_result,
            ),
        ):
            sb = MagicMock()
            mock_create.return_value = sb

            resp = await client.put("/api/learn/session/sess-1/complete")

        assert resp.status_code == 200
        data = resp.json()
        assert data["tomorrow_preview"] == "Continue preparing for Thermodynamics"

    @pytest.mark.asyncio
    async def test_abandon_session(self, client):
        mock_result = {
            "status": "abandoned",
            "session_id": "sess-1",
            "partial_xp_preserved": True,
        }

        with (
            patch("lecturelink_api.auth.create_client") as mock_create,
            patch(
                "lecturelink_api.routers.learn.abandon_learn_session",
                new_callable=AsyncMock,
                return_value=mock_result,
            ),
        ):
            sb = MagicMock()
            mock_create.return_value = sb

            resp = await client.put("/api/learn/session/sess-1/abandon")

        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "abandoned"

    @pytest.mark.asyncio
    async def test_get_power_quiz(self, client):
        mock_result = {
            "quiz_id": "quiz-1",
            "questions": [
                {
                    "question_id": "q1",
                    "question_text": "What is X?",
                    "options": ["A", "B", "C", "D"],
                    "concept_id": "c1",
                    "concept_title": "Concept 1",
                }
            ],
        }

        with (
            patch("lecturelink_api.auth.create_client") as mock_create,
            patch(
                "lecturelink_api.routers.learn.get_power_quiz",
                new_callable=AsyncMock,
                return_value=mock_result,
            ),
        ):
            sb = MagicMock()
            mock_create.return_value = sb

            resp = await client.get("/api/learn/session/sess-1/quiz")

        assert resp.status_code == 200
        data = resp.json()
        assert len(data["questions"]) == 1

    @pytest.mark.asyncio
    async def test_submit_quiz_answer(self, client):
        mock_result = {
            "correct": True,
            "correct_answer": "B) Answer",
            "explanation": "Because...",
            "source_citation": "",
            "xp_earned": 20,
            "combo_count": 1,
            "combo_multiplier": 1,
        }

        with (
            patch("lecturelink_api.auth.create_client") as mock_create,
            patch(
                "lecturelink_api.routers.learn.submit_power_quiz_answer",
                new_callable=AsyncMock,
                return_value=mock_result,
            ),
        ):
            sb = MagicMock()
            mock_create.return_value = sb

            resp = await client.post(
                "/api/learn/session/sess-1/quiz/answer",
                json={"question_id": "q1", "answer_index": 1, "time_ms": 5000},
            )

        assert resp.status_code == 200
        data = resp.json()
        assert data["correct"] is True
