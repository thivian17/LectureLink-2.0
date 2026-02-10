"""Tests for lecture upload, status, retry, and reprocess endpoints."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
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


def _now_str():
    return datetime.now(timezone.utc).isoformat()


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


def _sample_lecture(lecture_id: str | None = None, **overrides) -> dict:
    lid = lecture_id or str(uuid.uuid4())
    base = {
        "id": lid,
        "course_id": str(uuid.uuid4()),
        "user_id": FAKE_USER_ID,
        "title": "Lecture 1: Thermodynamics",
        "lecture_number": 1,
        "lecture_date": "2026-01-15",
        "processing_status": "completed",
        "processing_stage": "completed",
        "processing_progress": 1.0,
        "processing_error": None,
        "summary": "Introduction to thermodynamics",
        "duration_seconds": 3000,
        "transcript": "Welcome to today's lecture...",
        "retry_count": 0,
        "created_at": _now_str(),
    }
    base.update(overrides)
    return base


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
        SUPABASE_SERVICE_KEY="fake-service-key",
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
# Upload tests
# ---------------------------------------------------------------------------


class TestLectureUpload:
    @pytest.mark.asyncio
    async def test_upload_valid_audio(self, client):
        course_id = str(uuid.uuid4())
        lecture_id = str(uuid.uuid4())

        with (
            patch("lecturelink_api.routers.lectures.create_client") as mock_create,
            patch("lecturelink_api.routers.lectures.check_rate_limit"),
            patch("lecturelink_api.routers.lectures.run_lecture_processing"),
        ):
            sb = MagicMock()
            mock_create.return_value = sb

            course_chain = _mock_chain({"id": course_id})
            insert_chain = _mock_chain([{"id": lecture_id, "status": "pending"}])

            sb.table.side_effect = lambda name: (
                course_chain if name == "courses" else insert_chain
            )
            sb.storage.from_.return_value.upload.return_value = None

            resp = await client.post(
                "/api/lectures/upload",
                data={
                    "course_id": course_id,
                    "title": "Lecture 1",
                },
                files={"files": ("lecture.mp3", b"fake-audio", "audio/mpeg")},
            )

        assert resp.status_code == 200
        data = resp.json()
        assert data["lecture_id"] == lecture_id
        assert data["status"] == "processing"

    @pytest.mark.asyncio
    async def test_upload_rejects_invalid_type(self, client):
        with (
            patch("lecturelink_api.routers.lectures.create_client") as mock_create,
            patch("lecturelink_api.routers.lectures.check_rate_limit"),
        ):
            sb = MagicMock()
            mock_create.return_value = sb
            sb.table.return_value = _mock_chain({"id": "c1"})

            resp = await client.post(
                "/api/lectures/upload",
                data={"course_id": "c1", "title": "Lecture 1"},
                files={"files": ("notes.txt", b"hello", "text/plain")},
            )

        assert resp.status_code == 400
        assert "Unsupported file type" in resp.json()["detail"]

    @pytest.mark.asyncio
    async def test_upload_rejects_oversized_file(self, client):
        with (
            patch("lecturelink_api.routers.lectures.create_client") as mock_create,
            patch("lecturelink_api.routers.lectures.check_rate_limit"),
        ):
            sb = MagicMock()
            mock_create.return_value = sb
            sb.table.return_value = _mock_chain({"id": "c1"})

            # 51 MB PDF — exceeds 50 MB limit for slides
            big_file = b"x" * (51 * 1024 * 1024)
            resp = await client.post(
                "/api/lectures/upload",
                data={"course_id": "c1", "title": "Lecture 1"},
                files={"files": ("slides.pdf", big_file, "application/pdf")},
            )

        assert resp.status_code == 413
        assert "too large" in resp.json()["detail"]

    @pytest.mark.asyncio
    async def test_upload_without_auth(self):
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
                "/api/lectures/upload",
                data={"course_id": "c1", "title": "L1"},
                files={"files": ("a.mp3", b"x", "audio/mpeg")},
            )

        assert resp.status_code in (401, 403)
        app.dependency_overrides.pop(get_settings, None)

    @pytest.mark.asyncio
    async def test_upload_rate_limited(self, client):
        from fastapi import HTTPException

        with (
            patch("lecturelink_api.routers.lectures.create_client") as mock_create,
            patch(
                "lecturelink_api.routers.lectures.check_rate_limit",
                side_effect=HTTPException(
                    status_code=429,
                    detail="Rate limit exceeded",
                    headers={"Retry-After": "86400"},
                ),
            ),
        ):
            sb = MagicMock()
            mock_create.return_value = sb

            resp = await client.post(
                "/api/lectures/upload",
                data={"course_id": "c1", "title": "L1"},
                files={"files": ("a.mp3", b"x", "audio/mpeg")},
            )

        assert resp.status_code == 429


# ---------------------------------------------------------------------------
# GET tests
# ---------------------------------------------------------------------------


class TestLectureGet:
    @pytest.mark.asyncio
    async def test_get_lecture_detail(self, client):
        lecture = _sample_lecture()

        with patch("lecturelink_api.routers.lectures.create_client") as mock_create:
            sb = MagicMock()
            mock_create.return_value = sb

            lecture_chain = _mock_chain([lecture])
            concepts_chain = _mock_chain([])
            chunks_chain = _mock_chain([])

            call_count = {"n": 0}
            chains = [lecture_chain, concepts_chain, chunks_chain]

            def table_side_effect(name):
                idx = min(call_count["n"], len(chains) - 1)
                call_count["n"] += 1
                return chains[idx]

            sb.table.side_effect = table_side_effect

            resp = await client.get(f"/api/lectures/{lecture['id']}")

        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == lecture["id"]
        assert data["transcript"] == lecture["transcript"]
        assert "concepts" in data

    @pytest.mark.asyncio
    async def test_get_lecture_status(self, client):
        lecture_id = str(uuid.uuid4())

        with patch("lecturelink_api.routers.lectures.create_client") as mock_create:
            sb = MagicMock()
            mock_create.return_value = sb
            sb.table.return_value = _mock_chain([{
                "processing_status": "processing",
                "processing_stage": "transcribing",
                "processing_progress": 0.15,
                "processing_error": None,
            }])

            resp = await client.get(f"/api/lectures/{lecture_id}/status")

        assert resp.status_code == 200
        data = resp.json()
        assert data["processing_status"] == "processing"
        assert data["processing_stage"] == "transcribing"
        assert data["processing_progress"] == 0.15

    @pytest.mark.asyncio
    async def test_list_course_lectures(self, client):
        course_id = str(uuid.uuid4())
        lectures = [_sample_lecture(course_id=course_id), _sample_lecture(course_id=course_id)]

        with patch("lecturelink_api.routers.lectures.create_client") as mock_create:
            sb = MagicMock()
            mock_create.return_value = sb

            course_chain = _mock_chain({"id": course_id})
            lectures_chain = _mock_chain(lectures)

            sb.table.side_effect = lambda name: (
                course_chain if name == "courses" else lectures_chain
            )

            resp = await client.get(f"/api/courses/{course_id}/lectures")

        assert resp.status_code == 200
        assert len(resp.json()) == 2


# ---------------------------------------------------------------------------
# Retry / Reprocess tests
# ---------------------------------------------------------------------------


class TestLectureRetry:
    @pytest.mark.asyncio
    async def test_retry_failed_lecture(self, client):
        lecture = _sample_lecture(processing_status="failed", retry_count=1)

        with (
            patch("lecturelink_api.routers.lectures.create_client") as mock_create,
            patch("lecturelink_api.routers.lectures.run_lecture_processing"),
        ):
            sb = MagicMock()
            mock_create.return_value = sb

            select_chain = _mock_chain([lecture])
            update_chain = _mock_chain([lecture])

            call_count = {"n": 0}

            def table_side_effect(name):
                call_count["n"] += 1
                return select_chain if call_count["n"] == 1 else update_chain

            sb.table.side_effect = table_side_effect

            resp = await client.post(f"/api/lectures/{lecture['id']}/retry")

        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "processing"
        assert data["retry_count"] == 2

    @pytest.mark.asyncio
    async def test_retry_non_failed_lecture(self, client):
        lecture = _sample_lecture(processing_status="completed")

        with patch("lecturelink_api.routers.lectures.create_client") as mock_create:
            sb = MagicMock()
            mock_create.return_value = sb
            sb.table.return_value = _mock_chain([lecture])

            resp = await client.post(f"/api/lectures/{lecture['id']}/retry")

        assert resp.status_code == 400
        assert "not in failed state" in resp.json()["detail"]

    @pytest.mark.asyncio
    async def test_retry_max_exceeded(self, client):
        lecture = _sample_lecture(processing_status="failed", retry_count=3)

        with patch("lecturelink_api.routers.lectures.create_client") as mock_create:
            sb = MagicMock()
            mock_create.return_value = sb
            sb.table.return_value = _mock_chain([lecture])

            resp = await client.post(f"/api/lectures/{lecture['id']}/retry")

        assert resp.status_code == 400
        assert "Maximum retries exceeded" in resp.json()["detail"]

    @pytest.mark.asyncio
    async def test_reprocess_lecture(self, client):
        lecture = _sample_lecture()

        with (
            patch("lecturelink_api.routers.lectures.create_client") as mock_create,
            patch(
                "lecturelink_api.routers.lectures.cleanup_lecture_data",
            ),
            patch("lecturelink_api.routers.lectures.run_lecture_processing"),
        ):
            sb = MagicMock()
            mock_create.return_value = sb

            select_chain = _mock_chain([lecture])
            update_chain = _mock_chain([lecture])

            call_count = {"n": 0}

            def table_side_effect(name):
                call_count["n"] += 1
                return select_chain if call_count["n"] == 1 else update_chain

            sb.table.side_effect = table_side_effect

            resp = await client.post(f"/api/lectures/{lecture['id']}/reprocess")

        assert resp.status_code == 200
        assert resp.json()["status"] == "processing"
