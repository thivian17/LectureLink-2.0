"""Tests for the course materials router."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from lecturelink_api.main import app

# ---------------------------------------------------------------------------
# Fake user / helpers
# ---------------------------------------------------------------------------

FAKE_USER_ID = str(uuid.uuid4())
FAKE_EMAIL = "test@university.edu"
FAKE_TOKEN = "fake-jwt-token"

_AUTH_MOD = "lecturelink_api.auth"


def _fake_user():
    return {"id": FAKE_USER_ID, "email": FAKE_EMAIL, "token": FAKE_TOKEN}


def _now_str():
    return datetime.now(UTC).isoformat()


def _mock_execute(data, count=None):
    resp = MagicMock()
    resp.data = data
    resp.count = count
    return resp


def _mock_chain(final_data, count=None):
    chain = MagicMock()
    chain.execute.return_value = _mock_execute(final_data, count)
    for method in (
        "select", "insert", "update", "delete",
        "eq", "gte", "order", "in_",
    ):
        getattr(chain, method).return_value = chain
    return chain


def _sample_material(material_id: str | None = None, **overrides) -> dict:
    mid = material_id or str(uuid.uuid4())
    data = {
        "id": mid,
        "course_id": str(uuid.uuid4()),
        "user_id": FAKE_USER_ID,
        "title": "Chapter 5 Notes",
        "material_type": "notes",
        "file_name": "chapter5.pdf",
        "file_size_bytes": 1024000,
        "storage_path": f"{FAKE_USER_ID}/course1/{mid}/chapter5.pdf",
        "processing_status": "completed",
        "processing_error": None,
        "retry_count": 0,
        "linked_assessment_id": None,
        "week_number": 5,
        "relevant_date": None,
        "created_at": _now_str(),
    }
    data.update(overrides)
    return data


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


@pytest.fixture()
def _override_task_queue():
    from lecturelink_api.services.task_queue import TaskQueueService, get_task_queue

    mock_tq = MagicMock(spec=TaskQueueService)
    mock_tq.enqueue_material_processing = AsyncMock()
    app.dependency_overrides[get_task_queue] = lambda: mock_tq
    yield mock_tq
    app.dependency_overrides.pop(get_task_queue, None)


@pytest_asyncio.fixture()
async def client(_override_auth, _override_settings, _override_task_queue):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


# ---------------------------------------------------------------------------
# Upload tests
# ---------------------------------------------------------------------------


def _setup_upload_sb(mock_create, table_responses=None):
    """Set up a Supabase mock for upload tests with proper rate limit handling.

    table_responses: dict mapping table name to (data, count) tuples.
    Default handles rate_limit_events (count=0) and courses (found).
    """
    sb = MagicMock()
    mock_create.return_value = sb
    sb.auth.set_session = MagicMock()

    defaults = {
        "rate_limit_events": ([], 0),
        "courses": ([{"id": "course-1"}], None),
        "course_materials": ([_sample_material(processing_status="pending")], None),
    }
    if table_responses:
        defaults.update(table_responses)

    def table_side_effect(name):
        data, count = defaults.get(name, ([], None))
        return _mock_chain(data, count)

    sb.table.side_effect = table_side_effect

    # Storage mocks
    sb.storage.from_.return_value.upload.return_value = None
    sb.storage.from_.return_value.create_signed_url.return_value = {
        "signedURL": "https://fake.supabase.co/signed/file.pdf"
    }

    return sb


class TestMaterialUpload:
    @pytest.mark.asyncio
    async def test_upload_rejects_invalid_extension(self, client):
        """Should reject non-allowed file types."""
        with patch(f"{_AUTH_MOD}.create_client") as mock_create, patch("lecturelink_api.routers.materials._sb_admin", return_value=MagicMock()):
            _setup_upload_sb(mock_create)

            resp = await client.post(
                "/api/courses/course-1/materials/upload",
                data={"material_type": "notes"},
                files={"file": ("malware.exe", b"evil content", "application/octet-stream")},
            )

        assert resp.status_code == 400
        assert "Unsupported file type" in resp.json()["detail"]

    @pytest.mark.asyncio
    async def test_upload_rejects_oversized_file(self, client):
        """Should reject files over 50 MB."""
        with patch(f"{_AUTH_MOD}.create_client") as mock_create, patch("lecturelink_api.routers.materials._sb_admin", return_value=MagicMock()):
            _setup_upload_sb(mock_create)

            big_content = b"x" * (51 * 1024 * 1024)
            resp = await client.post(
                "/api/courses/course-1/materials/upload",
                data={"material_type": "notes"},
                files={"file": ("big.pdf", big_content, "application/pdf")},
            )

        assert resp.status_code == 413
        assert "File too large" in resp.json()["detail"]

    @pytest.mark.asyncio
    async def test_upload_creates_record_and_enqueues(self, client, _override_task_queue):
        """Should create DB record and enqueue processing."""
        material_record = _sample_material(processing_status="pending")

        with patch(f"{_AUTH_MOD}.create_client") as mock_create, patch("lecturelink_api.routers.materials._sb_admin", return_value=MagicMock()):
            _setup_upload_sb(mock_create, {
                "course_materials": ([material_record], None),
            })

            resp = await client.post(
                "/api/courses/course-1/materials/upload",
                data={"material_type": "notes", "title": "Chapter 5"},
                files={"file": ("chapter5.pdf", b"PDF content", "application/pdf")},
            )

        assert resp.status_code == 201
        data = resp.json()
        assert data["material_type"] == "notes"
        assert data["processing_status"] == "pending"

        _override_task_queue.enqueue_material_processing.assert_called_once()

    @pytest.mark.asyncio
    async def test_upload_verifies_course_ownership(self, client):
        """Should 404 if user doesn't own the course."""
        with patch(f"{_AUTH_MOD}.create_client") as mock_create, patch("lecturelink_api.routers.materials._sb_admin", return_value=MagicMock()):
            _setup_upload_sb(mock_create, {
                "courses": ([], None),
            })

            resp = await client.post(
                "/api/courses/nonexistent/materials/upload",
                data={"material_type": "notes"},
                files={"file": ("notes.pdf", b"content", "application/pdf")},
            )

        assert resp.status_code == 404
        assert "Course not found" in resp.json()["detail"]


# ---------------------------------------------------------------------------
# List tests
# ---------------------------------------------------------------------------


class TestMaterialList:
    @pytest.mark.asyncio
    async def test_list_returns_user_materials(self, client):
        """Should return materials for the course."""
        materials = [_sample_material(), _sample_material()]

        with patch(f"{_AUTH_MOD}.create_client") as mock_create, patch("lecturelink_api.routers.materials._sb_admin", return_value=MagicMock()):
            sb = MagicMock()
            mock_create.return_value = sb
            sb.auth.set_session = MagicMock()
            sb.table.return_value = _mock_chain(materials)

            resp = await client.get("/api/courses/course-1/materials")

        assert resp.status_code == 200
        data = resp.json()
        assert len(data["materials"]) == 2

    @pytest.mark.asyncio
    async def test_list_filters_by_type(self, client):
        """Should filter by material_type query param."""
        materials = [_sample_material(material_type="notes")]

        with patch(f"{_AUTH_MOD}.create_client") as mock_create, patch("lecturelink_api.routers.materials._sb_admin", return_value=MagicMock()):
            sb = MagicMock()
            mock_create.return_value = sb
            sb.auth.set_session = MagicMock()
            sb.table.return_value = _mock_chain(materials)

            resp = await client.get(
                "/api/courses/course-1/materials?material_type=notes"
            )

        assert resp.status_code == 200
        data = resp.json()
        assert len(data["materials"]) == 1
        assert data["materials"][0]["material_type"] == "notes"


# ---------------------------------------------------------------------------
# Status tests
# ---------------------------------------------------------------------------


class TestMaterialStatus:
    @pytest.mark.asyncio
    async def test_status_returns_processing_state(self, client):
        """Should return current processing status."""
        material = _sample_material(processing_status="processing")

        with patch(f"{_AUTH_MOD}.create_client") as mock_create, patch("lecturelink_api.routers.materials._sb_admin", return_value=MagicMock()):
            sb = MagicMock()
            mock_create.return_value = sb
            sb.auth.set_session = MagicMock()
            sb.table.return_value = _mock_chain([material], count=5)

            resp = await client.get(f"/api/materials/{material['id']}/status")

        assert resp.status_code == 200
        data = resp.json()
        assert data["processing_status"] == "processing"


# ---------------------------------------------------------------------------
# Delete tests
# ---------------------------------------------------------------------------


class TestMaterialDelete:
    @pytest.mark.asyncio
    async def test_delete_removes_material_and_storage(self, client):
        """Should delete DB record and storage file."""
        material = _sample_material()

        with patch(f"{_AUTH_MOD}.create_client") as mock_create, patch("lecturelink_api.routers.materials._sb_admin", return_value=MagicMock()):
            sb = MagicMock()
            mock_create.return_value = sb
            sb.auth.set_session = MagicMock()
            sb.table.return_value = _mock_chain([material])
            sb.storage.from_.return_value.remove.return_value = None

            resp = await client.delete(f"/api/materials/{material['id']}")

        assert resp.status_code == 204

    @pytest.mark.asyncio
    async def test_delete_verifies_ownership(self, client):
        """Should 403 if user doesn't own the material."""
        material = _sample_material(user_id="other-user-id")

        with patch(f"{_AUTH_MOD}.create_client") as mock_create, patch("lecturelink_api.routers.materials._sb_admin", return_value=MagicMock()):
            sb = MagicMock()
            mock_create.return_value = sb
            sb.auth.set_session = MagicMock()
            sb.table.return_value = _mock_chain([material])

            resp = await client.delete(f"/api/materials/{material['id']}")

        assert resp.status_code == 403


# ---------------------------------------------------------------------------
# Retry tests
# ---------------------------------------------------------------------------


class TestMaterialRetry:
    @pytest.mark.asyncio
    async def test_retry_rejects_non_failed(self, client):
        """Should 400 if material is not in failed state."""
        material = _sample_material(processing_status="completed")

        with patch(f"{_AUTH_MOD}.create_client") as mock_create, patch("lecturelink_api.routers.materials._sb_admin", return_value=MagicMock()):
            sb = MagicMock()
            mock_create.return_value = sb
            sb.auth.set_session = MagicMock()
            sb.table.return_value = _mock_chain([material])

            resp = await client.post(f"/api/materials/{material['id']}/retry")

        assert resp.status_code == 400
        assert "not in failed state" in resp.json()["detail"]

    @pytest.mark.asyncio
    async def test_retry_rejects_max_retries(self, client):
        """Should 400 if retry_count >= 3."""
        material = _sample_material(processing_status="failed", retry_count=3)

        with patch(f"{_AUTH_MOD}.create_client") as mock_create, patch("lecturelink_api.routers.materials._sb_admin", return_value=MagicMock()):
            sb = MagicMock()
            mock_create.return_value = sb
            sb.auth.set_session = MagicMock()
            sb.table.return_value = _mock_chain([material])

            resp = await client.post(f"/api/materials/{material['id']}/retry")

        assert resp.status_code == 400
        assert "Maximum retries" in resp.json()["detail"]

    @pytest.mark.asyncio
    async def test_retry_re_enqueues_processing(self, client, _override_task_queue):
        """Should re-enqueue and return updated status."""
        material = _sample_material(processing_status="failed", retry_count=1)

        with patch(f"{_AUTH_MOD}.create_client") as mock_create, patch("lecturelink_api.routers.materials._sb_admin", return_value=MagicMock()):
            sb = MagicMock()
            mock_create.return_value = sb
            sb.auth.set_session = MagicMock()
            sb.table.return_value = _mock_chain([material])
            sb.storage.from_.return_value.create_signed_url.return_value = {
                "signedURL": "https://fake.supabase.co/signed/file.pdf"
            }

            resp = await client.post(f"/api/materials/{material['id']}/retry")

        assert resp.status_code == 200
        data = resp.json()
        assert data["processing_status"] == "pending"
        assert data["retry_count"] == 2
        _override_task_queue.enqueue_material_processing.assert_called_once()
