"""Tests for study actions routes."""

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
    for method in (
        "select", "eq", "in_", "order", "limit", "single",
        "gte", "lte",
    ):
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
# Global study actions
# ---------------------------------------------------------------------------


class TestGlobalStudyActions:
    @pytest.mark.asyncio
    async def test_returns_200_with_actions(self, client):
        with (
            patch(
                "lecturelink_api.routers.study_actions.create_client"
            ) as mock_create,
            patch(
                "lecturelink_api.services.study_actions_llm.get_study_actions_llm",
                new_callable=AsyncMock,
            ) as mock_actions,
        ):
            mock_create.return_value = _mock_supabase()
            mock_actions.return_value = []

            resp = await client.get("/api/study-actions")

        assert resp.status_code == 200
        data = resp.json()
        assert "actions" in data
        assert "generated_at" in data

    @pytest.mark.asyncio
    async def test_empty_for_no_courses(self, client):
        with (
            patch(
                "lecturelink_api.routers.study_actions.create_client"
            ) as mock_create,
            patch(
                "lecturelink_api.services.study_actions_llm.get_study_actions_llm",
                new_callable=AsyncMock,
            ) as mock_actions,
        ):
            mock_create.return_value = _mock_supabase(course_data=[])
            mock_actions.return_value = []

            resp = await client.get("/api/study-actions")

        assert resp.status_code == 200
        assert resp.json()["actions"] == []


# ---------------------------------------------------------------------------
# Course-specific study actions
# ---------------------------------------------------------------------------


class TestCourseStudyActions:
    @pytest.mark.asyncio
    async def test_returns_200_for_valid_course(self, client):
        with (
            patch(
                "lecturelink_api.routers.study_actions.create_client"
            ) as mock_create,
            patch(
                "lecturelink_api.services.study_actions_llm.get_study_actions_llm",
                new_callable=AsyncMock,
            ) as mock_actions,
        ):
            mock_create.return_value = _mock_supabase()
            mock_actions.return_value = []

            resp = await client.get(f"/api/courses/{COURSE_ID}/study-actions")

        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_returns_404_for_invalid_course(self, client):
        with patch(
            "lecturelink_api.routers.study_actions.create_client"
        ) as mock_create:
            mock_create.return_value = _mock_supabase(course_data=[])

            resp = await client.get(f"/api/courses/{COURSE_ID}/study-actions")

        assert resp.status_code == 404
