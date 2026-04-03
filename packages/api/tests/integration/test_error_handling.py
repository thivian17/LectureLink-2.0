"""Integration tests for error handling across all Phase 2 endpoints.

Verifies correct HTTP status codes for auth, not-found, validation,
rate-limit, and retry error scenarios.
"""

from __future__ import annotations

import uuid
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException
from httpx import ASGITransport, AsyncClient
from lecturelink_api.main import app

from tests.integration.conftest import (
    make_lecture,
    mock_chain,
)

pytestmark = [pytest.mark.integration]


def _table_router(table_map: dict[str, MagicMock]):
    def _route(name):
        return table_map.get(name, mock_chain(None))

    return _route


# ---------------------------------------------------------------------------
# Auth errors
# ---------------------------------------------------------------------------


class TestAuthErrors:
    """Requests without valid authentication."""

    @pytest.mark.asyncio
    async def test_missing_auth_header_returns_401(self, unauthenticated_client):
        """Request without Authorization header returns 401."""
        resp = await unauthenticated_client.get("/api/courses")
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_invalid_bearer_token_returns_401(self, override_settings):
        """Invalid JWT in Authorization header returns 401."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            resp = await ac.get(
                "/api/courses",
                headers={"Authorization": "Bearer invalid-garbage-token"},
            )
        assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Not-found errors
# ---------------------------------------------------------------------------


class TestNotFoundErrors:
    """404 responses for missing resources."""

    @pytest.mark.asyncio
    async def test_lecture_not_found(self, client):
        lid = str(uuid.uuid4())
        with patch("lecturelink_api.auth.create_client") as mc:
            sb = MagicMock()
            mc.return_value = sb
            sb.table.return_value = mock_chain(None)

            resp = await client.get(f"/api/lectures/{lid}")

        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_lecture_status_not_found(self, client):
        lid = str(uuid.uuid4())
        with patch("lecturelink_api.auth.create_client") as mc:
            sb = MagicMock()
            mc.return_value = sb
            sb.table.return_value = mock_chain(None)

            resp = await client.get(f"/api/lectures/{lid}/status")

        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_quiz_not_found(self, client):
        qid = str(uuid.uuid4())
        with patch("lecturelink_api.auth.create_client") as mc:
            sb = MagicMock()
            mc.return_value = sb
            sb.table.return_value = mock_chain(None)

            resp = await client.get(f"/api/quizzes/{qid}")

        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_quiz_submit_not_found(self, client):
        qid = str(uuid.uuid4())
        with patch("lecturelink_api.auth.create_client") as mc:
            sb = MagicMock()
            mc.return_value = sb
            sb.table.return_value = mock_chain(None)

            resp = await client.post(
                f"/api/quizzes/{qid}/submit",
                json={"answers": [{"question_id": "x", "student_answer": "A"}]},
            )

        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_search_course_not_found(self, client):
        cid = str(uuid.uuid4())
        with patch("lecturelink_api.auth.create_client") as mc:
            sb = MagicMock()
            mc.return_value = sb
            sb.table.return_value = mock_chain(None)

            resp = await client.post(
                "/api/search",
                json={"course_id": cid, "query": "heat"},
            )

        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Validation errors
# ---------------------------------------------------------------------------


class TestValidationErrors:
    """422 responses for invalid request payloads."""

    @pytest.mark.asyncio
    async def test_search_empty_query_rejected(self, client):
        resp = await client.post(
            "/api/search",
            json={"course_id": str(uuid.uuid4()), "query": ""},
        )
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_search_limit_out_of_range(self, client):
        """Limit > 50 should fail validation (le=50 on SearchRequest)."""
        resp = await client.post(
            "/api/search",
            json={
                "course_id": str(uuid.uuid4()),
                "query": "heat",
                "limit": 100,
            },
        )
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_quiz_generate_too_many_questions(self, client):
        """num_questions > 30 should fail validation (le=30)."""
        resp = await client.post(
            "/api/quizzes/generate",
            json={
                "course_id": str(uuid.uuid4()),
                "num_questions": 50,
                "difficulty": "medium",
            },
        )
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_qa_empty_question_rejected(self, client):
        resp = await client.post(
            "/api/qa",
            json={"course_id": str(uuid.uuid4()), "question": ""},
        )
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# Rate-limit errors
# ---------------------------------------------------------------------------


class TestRateLimitErrors:
    """429 responses when rate limits are exceeded."""

    @pytest.mark.asyncio
    async def test_qa_rate_limit_exceeded(self, client):
        course_id = str(uuid.uuid4())

        with (
            patch("lecturelink_api.auth.create_client") as mc,
            patch(
                "lecturelink_api.routers.search.check_rate_limit",
                side_effect=HTTPException(
                    status_code=429,
                    detail="Rate limit exceeded for qa_question.",
                    headers={"Retry-After": "3600"},
                ),
            ),
        ):
            sb = MagicMock()
            mc.return_value = sb

            resp = await client.post(
                "/api/qa",
                json={"course_id": course_id, "question": "What is heat?"},
            )

        assert resp.status_code == 429

    @pytest.mark.asyncio
    async def test_lecture_upload_rate_limit_exceeded(self, client):
        import io

        course_id = str(uuid.uuid4())

        with (
            patch("lecturelink_api.auth.create_client") as mc,
            patch(
                "lecturelink_api.routers.lectures.check_rate_limit",
                side_effect=HTTPException(
                    status_code=429,
                    detail="Rate limit exceeded for lecture_upload.",
                    headers={"Retry-After": "86400"},
                ),
            ),
        ):
            sb = MagicMock()
            mc.return_value = sb

            resp = await client.post(
                "/api/lectures/upload",
                data={"course_id": course_id, "title": "Test"},
                files=[("files", ("a.mp3", io.BytesIO(b"x"), "audio/mpeg"))],
            )

        assert resp.status_code == 429

    @pytest.mark.asyncio
    async def test_quiz_generate_rate_limit_exceeded(self, client):
        course_id = str(uuid.uuid4())

        with (
            patch("lecturelink_api.auth.create_client") as mc,
            patch(
                "lecturelink_api.routers.quizzes.check_rate_limit",
                side_effect=HTTPException(
                    status_code=429,
                    detail="Rate limit exceeded for quiz_generate.",
                    headers={"Retry-After": "86400"},
                ),
            ),
        ):
            sb = MagicMock()
            mc.return_value = sb

            resp = await client.post(
                "/api/quizzes/generate",
                json={
                    "course_id": course_id,
                    "num_questions": 5,
                    "difficulty": "medium",
                },
            )

        assert resp.status_code == 429


# ---------------------------------------------------------------------------
# Retry / reprocess errors
# ---------------------------------------------------------------------------


class TestRetryErrors:
    """Error responses for retry/reprocess edge cases."""

    @pytest.mark.asyncio
    async def test_retry_non_failed_lecture_returns_400(self, client):
        lid = str(uuid.uuid4())
        course_id = str(uuid.uuid4())
        lec = make_lecture(course_id, lecture_id=lid, processing_status="completed")

        with patch("lecturelink_api.auth.create_client") as mc:
            sb = MagicMock()
            mc.return_value = sb
            sb.table.return_value = mock_chain([lec])

            resp = await client.post(f"/api/lectures/{lid}/retry")

        assert resp.status_code == 400
        assert "not in failed state" in resp.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_retry_max_retries_exceeded_returns_400(self, client):
        lid = str(uuid.uuid4())
        course_id = str(uuid.uuid4())
        lec = make_lecture(
            course_id,
            lecture_id=lid,
            processing_status="failed",
            retry_count=3,
        )

        with patch("lecturelink_api.auth.create_client") as mc:
            sb = MagicMock()
            mc.return_value = sb
            sb.table.return_value = mock_chain([lec])

            resp = await client.post(f"/api/lectures/{lid}/retry")

        assert resp.status_code == 400
        assert "maximum retries" in resp.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_retry_not_found(self, client):
        lid = str(uuid.uuid4())

        with patch("lecturelink_api.auth.create_client") as mc:
            sb = MagicMock()
            mc.return_value = sb
            sb.table.return_value = mock_chain(None)

            resp = await client.post(f"/api/lectures/{lid}/retry")

        assert resp.status_code == 404
