"""Tests for search and Q&A endpoints."""

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


def _mock_execute(data):
    resp = MagicMock()
    resp.data = data
    resp.count = 0
    return resp


def _mock_chain(final_data):
    chain = MagicMock()
    chain.execute.return_value = _mock_execute(final_data)
    for method in (
        "select", "insert", "update", "delete",
        "eq", "order", "single", "maybe_single", "in_",
    ):
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
# Search tests
# ---------------------------------------------------------------------------


class TestSearch:
    @pytest.mark.asyncio
    async def test_search_valid_query(self, client):
        course_id = str(uuid.uuid4())
        mock_chunks = [
            {
                "chunk_id": str(uuid.uuid4()),
                "lecture_id": str(uuid.uuid4()),
                "lecture_title": "Lecture 1",
                "content": "Thermodynamics is the study of heat and energy.",
                "start_time": 15.5,
                "end_time": 35.0,
                "slide_number": 2,
                "score": 0.92,
            }
        ]

        with (
            patch("lecturelink_api.routers.search.create_client") as mock_create,
            patch(
                "lecturelink_api.routers.search.search_lectures",
                new_callable=AsyncMock,
                return_value=mock_chunks,
            ),
        ):
            sb = MagicMock()
            mock_create.return_value = sb
            sb.table.return_value = _mock_chain({"id": course_id, "name": "PHYS 201"})

            resp = await client.post(
                "/api/search",
                json={"course_id": course_id, "query": "thermodynamics"},
            )

        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["lecture_title"] == "Lecture 1"
        assert data[0]["highlight"] is not None

    @pytest.mark.asyncio
    async def test_search_empty_query_rejected(self, client):
        resp = await client.post(
            "/api/search",
            json={"course_id": str(uuid.uuid4()), "query": ""},
        )
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_search_without_auth(self):
        from lecturelink_api.auth import get_current_user
        from lecturelink_api.config import Settings, get_settings

        app.dependency_overrides.pop(get_current_user, None)
        app.dependency_overrides[get_settings] = lambda: Settings(
            SUPABASE_URL="https://fake.supabase.co",
            SUPABASE_ANON_KEY="fake-anon-key",
        )

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            resp = await ac.post(
                "/api/search",
                json={"course_id": "c1", "query": "test"},
            )

        assert resp.status_code in (401, 403)
        app.dependency_overrides.pop(get_settings, None)


# ---------------------------------------------------------------------------
# Q&A tests
# ---------------------------------------------------------------------------


class TestQA:
    @pytest.mark.asyncio
    async def test_qa_valid_question(self, client):
        course_id = str(uuid.uuid4())
        mock_answer = {
            "answer": "Heat transfer occurs via conduction, convection, and radiation.",
            "confidence": 0.92,
            "source_chunks": [
                {
                    "chunk_id": str(uuid.uuid4()),
                    "content": "Three types of heat transfer...",
                    "lecture_title": "Lecture 1",
                    "start_time": 110.0,
                    "end_time": 135.5,
                    "slide_number": 4,
                }
            ],
            "follow_up_suggestions": [
                "What is the difference between conduction and convection?",
            ],
        }

        with (
            patch("lecturelink_api.routers.search.create_client") as mock_create,
            patch("lecturelink_api.routers.search.check_rate_limit"),
            patch(
                "lecturelink_api.routers.search.ask_lecture_question",
                new_callable=AsyncMock,
                return_value=mock_answer,
            ),
        ):
            sb = MagicMock()
            mock_create.return_value = sb
            sb.table.return_value = _mock_chain([{"id": course_id, "name": "PHYS 201"}])

            resp = await client.post(
                "/api/qa",
                json={"course_id": course_id, "question": "How does heat transfer work?"},
            )

        assert resp.status_code == 200
        data = resp.json()
        assert data["confidence"] == 0.92
        assert len(data["source_chunks"]) == 1

    @pytest.mark.asyncio
    async def test_qa_rate_limited(self, client):
        from fastapi import HTTPException

        with (
            patch("lecturelink_api.routers.search.create_client") as mock_create,
            patch(
                "lecturelink_api.routers.search.check_rate_limit",
                side_effect=HTTPException(
                    status_code=429,
                    detail="Rate limit exceeded",
                    headers={"Retry-After": "3600"},
                ),
            ),
        ):
            sb = MagicMock()
            mock_create.return_value = sb

            resp = await client.post(
                "/api/qa",
                json={
                    "course_id": str(uuid.uuid4()),
                    "question": "What is heat?",
                },
            )

        assert resp.status_code == 429
