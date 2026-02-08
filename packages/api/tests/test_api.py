"""API tests using httpx AsyncClient with mocked Supabase."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from lecturelink_api.main import app

# ---------------------------------------------------------------------------
# Fake user / auth helpers
# ---------------------------------------------------------------------------

FAKE_USER_ID = str(uuid.uuid4())
FAKE_EMAIL = "test@university.edu"
FAKE_TOKEN = "fake-jwt-token"


def _fake_user():
    return {"id": FAKE_USER_ID, "email": FAKE_EMAIL, "token": FAKE_TOKEN}


def _now_str():
    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def _override_auth():
    """Override auth dependency to return fake user without hitting Supabase."""
    from lecturelink_api.auth import get_current_user

    app.dependency_overrides[get_current_user] = lambda: _fake_user()
    yield
    app.dependency_overrides.pop(get_current_user, None)


@pytest.fixture()
def _override_settings():
    """Override settings so no .env file is required."""
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
# Supabase mock helpers
# ---------------------------------------------------------------------------


def _mock_execute(data):
    """Return a mock that looks like supabase.execute() result."""
    resp = MagicMock()
    resp.data = data
    return resp


def _mock_chain(final_data):
    """Build a chainable mock (select/eq/order etc.) that returns final_data on .execute()."""
    chain = MagicMock()
    chain.execute.return_value = _mock_execute(final_data)
    # Every chained method returns the same chain
    for method in (
        "select", "insert", "update", "delete",
        "eq", "order", "single", "maybe_single",
    ):
        getattr(chain, method).return_value = chain
    return chain


def _sample_course(course_id: str | None = None) -> dict:
    cid = course_id or str(uuid.uuid4())
    return {
        "id": cid,
        "user_id": FAKE_USER_ID,
        "name": "Intro to CS",
        "code": "CS101",
        "semester_start": "2026-01-12",
        "semester_end": "2026-05-01",
        "meeting_days": ["Tue", "Thu"],
        "meeting_time": "10:00",
        "holidays": [],
        "target_grade": 0.8,
        "created_at": _now_str(),
        "updated_at": _now_str(),
    }


def _sample_assessment(course_id: str, assessment_id: str | None = None) -> dict:
    aid = assessment_id or str(uuid.uuid4())
    return {
        "id": aid,
        "course_id": course_id,
        "syllabus_id": str(uuid.uuid4()),
        "title": "Midterm 1",
        "type": "exam",
        "due_date": "2026-03-15",
        "due_date_raw": "Week 8 Thursday",
        "is_date_ambiguous": False,
        "weight_percent": 20.0,
        "topics": ["Chapter 1", "Chapter 2"],
        "created_at": _now_str(),
    }


# ---------------------------------------------------------------------------
# Course CRUD tests
# ---------------------------------------------------------------------------


class TestCourses:
    @pytest.mark.asyncio
    async def test_create_course(self, client):
        course = _sample_course()
        with patch("lecturelink_api.routers.courses.create_client") as mock_create:
            sb = MagicMock()
            mock_create.return_value = sb
            sb.table.return_value = _mock_chain([course])

            resp = await client.post("/api/courses", json={
                "name": "Intro to CS",
                "code": "CS101",
                "semester_start": "2026-01-12",
                "semester_end": "2026-05-01",
            })

        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "Intro to CS"
        assert data["code"] == "CS101"

    @pytest.mark.asyncio
    async def test_list_courses(self, client):
        courses = [_sample_course(), _sample_course()]
        with patch("lecturelink_api.routers.courses.create_client") as mock_create:
            sb = MagicMock()
            mock_create.return_value = sb
            sb.table.return_value = _mock_chain(courses)

            resp = await client.get("/api/courses")

        assert resp.status_code == 200
        assert len(resp.json()) == 2

    @pytest.mark.asyncio
    async def test_get_course(self, client):
        course = _sample_course("abc-123")
        with patch("lecturelink_api.routers.courses.create_client") as mock_create:
            sb = MagicMock()
            mock_create.return_value = sb
            sb.table.return_value = _mock_chain(course)

            resp = await client.get("/api/courses/abc-123")

        assert resp.status_code == 200
        assert resp.json()["id"] == "abc-123"

    @pytest.mark.asyncio
    async def test_get_course_not_found(self, client):
        with patch("lecturelink_api.routers.courses.create_client") as mock_create:
            sb = MagicMock()
            mock_create.return_value = sb
            sb.table.return_value = _mock_chain(None)

            resp = await client.get(f"/api/courses/{uuid.uuid4()}")

        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_update_course(self, client):
        updated = _sample_course("abc-123")
        updated["name"] = "Advanced CS"
        with patch("lecturelink_api.routers.courses.create_client") as mock_create:
            sb = MagicMock()
            mock_create.return_value = sb
            sb.table.return_value = _mock_chain([updated])

            resp = await client.patch("/api/courses/abc-123", json={"name": "Advanced CS"})

        assert resp.status_code == 200
        assert resp.json()["name"] == "Advanced CS"

    @pytest.mark.asyncio
    async def test_update_course_empty_body(self, client):
        with patch("lecturelink_api.routers.courses.create_client") as mock_create:
            sb = MagicMock()
            mock_create.return_value = sb

            resp = await client.patch("/api/courses/abc-123", json={})

        assert resp.status_code == 400

    @pytest.mark.asyncio
    async def test_delete_course(self, client):
        with patch("lecturelink_api.routers.courses.create_client") as mock_create:
            sb = MagicMock()
            mock_create.return_value = sb
            sb.table.return_value = _mock_chain([{"id": "abc-123"}])

            resp = await client.delete("/api/courses/abc-123")

        assert resp.status_code == 204

    @pytest.mark.asyncio
    async def test_delete_course_not_found(self, client):
        with patch("lecturelink_api.routers.courses.create_client") as mock_create:
            sb = MagicMock()
            mock_create.return_value = sb
            sb.table.return_value = _mock_chain([])

            resp = await client.delete(f"/api/courses/{uuid.uuid4()}")

        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Syllabus tests
# ---------------------------------------------------------------------------


class TestSyllabi:
    @pytest.mark.asyncio
    async def test_upload_triggers_processing(self, client):
        course_id = str(uuid.uuid4())
        syllabus_id = str(uuid.uuid4())

        with patch("lecturelink_api.routers.syllabi.create_client") as mock_create:
            sb = MagicMock()
            mock_create.return_value = sb

            # Course ownership check
            course_chain = _mock_chain({"id": course_id})
            # Syllabi insert
            insert_chain = _mock_chain([{"id": syllabus_id, "status": "processing"}])

            sb.table.side_effect = lambda name: (
                course_chain if name == "courses" else insert_chain
            )
            sb.storage.from_.return_value.upload.return_value = None

            with patch("lecturelink_api.routers.syllabi.process_syllabus"):
                resp = await client.post(
                    "/api/syllabi/upload",
                    data={"course_id": course_id},
                    files={"file": ("syllabus.pdf", b"%PDF-1.4 fake", "application/pdf")},
                )

        assert resp.status_code == 201
        data = resp.json()
        assert data["status"] == "processing"
        assert data["syllabus_id"] == syllabus_id

    @pytest.mark.asyncio
    async def test_upload_rejects_unsupported_type(self, client):
        resp = await client.post(
            "/api/syllabi/upload",
            data={"course_id": str(uuid.uuid4())},
            files={"file": ("notes.txt", b"hello", "text/plain")},
        )
        assert resp.status_code == 400
        assert "Unsupported file type" in resp.json()["detail"]

    @pytest.mark.asyncio
    async def test_get_syllabus(self, client):
        sid = str(uuid.uuid4())
        syllabus_data = {
            "id": sid,
            "course_id": str(uuid.uuid4()),
            "user_id": FAKE_USER_ID,
            "file_url": "https://example.com/file.pdf",
            "file_name": "syllabus.pdf",
            "raw_extraction": {"course_name": {"value": "CS101", "confidence": 0.9}},
            "grade_breakdown": [],
            "extraction_confidence": 0.85,
            "needs_review": True,
            "reviewed_at": None,
            "created_at": _now_str(),
        }
        with patch("lecturelink_api.routers.syllabi.create_client") as mock_create:
            sb = MagicMock()
            mock_create.return_value = sb
            sb.table.return_value = _mock_chain(syllabus_data)

            resp = await client.get(f"/api/syllabi/{sid}")

        assert resp.status_code == 200
        assert resp.json()["id"] == sid

    @pytest.mark.asyncio
    async def test_get_syllabus_status_complete(self, client):
        sid = str(uuid.uuid4())
        with patch("lecturelink_api.routers.syllabi.create_client") as mock_create:
            sb = MagicMock()
            mock_create.return_value = sb
            sb.table.return_value = _mock_chain(
                {"id": sid, "status": "processed", "needs_review": True}
            )

            resp = await client.get(f"/api/syllabi/{sid}/status")

        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "complete"
        assert data["needs_review"] is True

    @pytest.mark.asyncio
    async def test_get_syllabus_status_processing(self, client):
        sid = str(uuid.uuid4())
        with patch("lecturelink_api.routers.syllabi.create_client") as mock_create:
            sb = MagicMock()
            mock_create.return_value = sb
            sb.table.return_value = _mock_chain(
                {"id": sid, "status": "processing", "needs_review": False}
            )

            resp = await client.get(f"/api/syllabi/{sid}/status")

        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "processing"

    @pytest.mark.asyncio
    async def test_get_syllabus_status_error(self, client):
        sid = str(uuid.uuid4())
        with patch("lecturelink_api.routers.syllabi.create_client") as mock_create:
            sb = MagicMock()
            mock_create.return_value = sb
            sb.table.return_value = _mock_chain(
                {"id": sid, "status": "error", "needs_review": True}
            )

            resp = await client.get(f"/api/syllabi/{sid}/status")

        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "error"

    @pytest.mark.asyncio
    async def test_review_syllabus(self, client):
        sid = str(uuid.uuid4())
        reviewed = {
            "id": sid,
            "course_id": str(uuid.uuid4()),
            "user_id": FAKE_USER_ID,
            "file_url": None,
            "file_name": None,
            "raw_extraction": {"course_name": {"value": "CS 102", "confidence": 1.0}},
            "grade_breakdown": [],
            "extraction_confidence": 0.9,
            "needs_review": False,
            "reviewed_at": _now_str(),
            "created_at": _now_str(),
        }
        with patch("lecturelink_api.routers.syllabi.create_client") as mock_create:
            sb = MagicMock()
            mock_create.return_value = sb
            sb.table.return_value = _mock_chain([reviewed])

            resp = await client.put(
                f"/api/syllabi/{sid}/review",
                json={"raw_extraction": {"course_name": {"value": "CS 102", "confidence": 1.0}}},
            )

        assert resp.status_code == 200
        assert resp.json()["needs_review"] is False


# ---------------------------------------------------------------------------
# Assessment tests
# ---------------------------------------------------------------------------


class TestAssessments:
    @pytest.mark.asyncio
    async def test_list_assessments(self, client):
        course_id = str(uuid.uuid4())
        assessments = [_sample_assessment(course_id), _sample_assessment(course_id)]

        with patch("lecturelink_api.routers.assessments.create_client") as mock_create:
            sb = MagicMock()
            mock_create.return_value = sb

            course_chain = _mock_chain({"id": course_id})
            assessment_chain = _mock_chain(assessments)
            sb.table.side_effect = lambda name: (
                course_chain if name == "courses" else assessment_chain
            )

            resp = await client.get(f"/api/courses/{course_id}/assessments")

        assert resp.status_code == 200
        assert len(resp.json()) == 2

    @pytest.mark.asyncio
    async def test_get_priorities(self, client):
        course_id = str(uuid.uuid4())
        priorities = [
            {
                "assessment_id": str(uuid.uuid4()),
                "title": "Midterm",
                "course_id": course_id,
                "due_date": "2026-03-15",
                "weight_percent": 20.0,
                "priority_score": 85.5,
            }
        ]

        with patch("lecturelink_api.routers.assessments.create_client") as mock_create:
            sb = MagicMock()
            mock_create.return_value = sb

            course_chain = _mock_chain({"id": course_id})
            sb.table.return_value = course_chain
            sb.rpc.return_value = _mock_chain(priorities)

            resp = await client.get(f"/api/courses/{course_id}/assessments/priorities")

        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["priority_score"] == 85.5

    @pytest.mark.asyncio
    async def test_update_assessment(self, client):
        course_id = str(uuid.uuid4())
        assessment_id = str(uuid.uuid4())
        updated = _sample_assessment(course_id, assessment_id)
        updated["title"] = "Final Exam"

        with patch("lecturelink_api.routers.assessments.create_client") as mock_create:
            sb = MagicMock()
            mock_create.return_value = sb

            # First call: select existing assessment; second call: verify course; third: update
            existing_chain = _mock_chain({"id": assessment_id, "course_id": course_id})
            course_chain = _mock_chain({"id": course_id})
            update_chain = _mock_chain([updated])

            call_count = {"n": 0}
            chains = [existing_chain, course_chain, update_chain]

            def table_side_effect(name):
                idx = min(call_count["n"], len(chains) - 1)
                call_count["n"] += 1
                return chains[idx]

            sb.table.side_effect = table_side_effect

            resp = await client.patch(
                f"/api/assessments/{assessment_id}",
                json={"title": "Final Exam"},
            )

        assert resp.status_code == 200
        assert resp.json()["title"] == "Final Exam"

    @pytest.mark.asyncio
    async def test_delete_assessment(self, client):
        course_id = str(uuid.uuid4())
        assessment_id = str(uuid.uuid4())

        with patch("lecturelink_api.routers.assessments.create_client") as mock_create:
            sb = MagicMock()
            mock_create.return_value = sb

            existing_chain = _mock_chain({"id": assessment_id, "course_id": course_id})
            course_chain = _mock_chain({"id": course_id})
            delete_chain = _mock_chain([{"id": assessment_id}])

            call_count = {"n": 0}
            chains = [existing_chain, course_chain, delete_chain]

            def table_side_effect(name):
                idx = min(call_count["n"], len(chains) - 1)
                call_count["n"] += 1
                return chains[idx]

            sb.table.side_effect = table_side_effect

            resp = await client.delete(f"/api/assessments/{assessment_id}")

        assert resp.status_code == 204


# ---------------------------------------------------------------------------
# Auth middleware tests
# ---------------------------------------------------------------------------


class TestAuth:
    @pytest.mark.asyncio
    async def test_missing_token_rejected(self):
        """Without auth override, missing bearer token is rejected."""
        from lecturelink_api.auth import get_current_user
        from lecturelink_api.config import Settings, get_settings

        app.dependency_overrides.pop(get_current_user, None)
        app.dependency_overrides[get_settings] = lambda: Settings(
            SUPABASE_URL="https://fake.supabase.co",
            SUPABASE_ANON_KEY="fake-anon-key",
        )

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            resp = await ac.get("/api/courses")

        # HTTPBearer rejects requests without Authorization header (401 or 403)
        assert resp.status_code in (401, 403)
        app.dependency_overrides.pop(get_settings, None)

    @pytest.mark.asyncio
    async def test_invalid_token_returns_401(self):
        """With an invalid token, Supabase validation fails → 401."""
        from lecturelink_api.auth import get_current_user
        from lecturelink_api.config import Settings, get_settings

        app.dependency_overrides.pop(get_current_user, None)
        app.dependency_overrides[get_settings] = lambda: Settings(
            SUPABASE_URL="https://fake.supabase.co",
            SUPABASE_ANON_KEY="fake-anon-key",
        )

        with patch("lecturelink_api.auth.create_client") as mock_create:
            sb = MagicMock()
            mock_create.return_value = sb
            sb.auth.get_user.side_effect = Exception("Invalid JWT")

            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as ac:
                resp = await ac.get(
                    "/api/courses",
                    headers={"Authorization": "Bearer bad-token"},
                )

        assert resp.status_code == 401
        app.dependency_overrides.pop(get_settings, None)

    @pytest.mark.asyncio
    async def test_health_no_auth_required(self):
        """Health check should work without authentication."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            resp = await ac.get("/health")
        assert resp.status_code == 200
        assert resp.json() == {"status": "ok"}
