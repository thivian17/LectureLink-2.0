"""Integration tests for lecture upload, status polling, and listing.

Tests the full upload → status → list → detail flow with mocked Supabase.
"""

from __future__ import annotations

import io
import uuid
from unittest.mock import MagicMock, patch

import pytest

from tests.integration.conftest import (
    make_chunk,
    make_concept,
    make_course,
    make_lecture,
    mock_chain,
)

pytestmark = [pytest.mark.integration]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _table_router(table_map: dict[str, MagicMock]):
    """Return a side_effect for sb.table() that routes by table name."""

    def _route(name):
        return table_map.get(name, mock_chain(None))

    return _route


# ---------------------------------------------------------------------------
# Upload
# ---------------------------------------------------------------------------


class TestLectureUpload:
    """POST /api/lectures/upload."""

    @pytest.mark.asyncio
    async def test_upload_creates_lecture_record(self, client):
        course_id = str(uuid.uuid4())
        lecture_id = str(uuid.uuid4())

        with (
            patch("lecturelink_api.routers.lectures.create_client") as mc,
            patch("lecturelink_api.routers.lectures.check_rate_limit"),
        ):
            sb = MagicMock()
            mc.return_value = sb

            # _sb_admin for storage upload
            with patch("lecturelink_api.routers.lectures._sb_admin") as admin:
                admin.return_value = MagicMock()

                sb.table.side_effect = _table_router({
                    "courses": mock_chain([{"id": course_id}]),
                    "lectures": mock_chain(
                        [{"id": lecture_id, "processing_status": "pending"}]
                    ),
                })

                resp = await client.post(
                    "/api/lectures/upload",
                    data={"course_id": course_id, "title": "Lecture 1"},
                    files=[("files", ("audio.mp3", io.BytesIO(b"fake"), "audio/mpeg"))],
                )

        assert resp.status_code == 200
        data = resp.json()
        assert data["lecture_id"] == lecture_id
        assert data["status"] == "processing"

    @pytest.mark.asyncio
    async def test_upload_rejects_unsupported_file_type(self, client):
        course_id = str(uuid.uuid4())

        with (
            patch("lecturelink_api.routers.lectures.create_client") as mc,
            patch("lecturelink_api.routers.lectures.check_rate_limit"),
        ):
            sb = MagicMock()
            mc.return_value = sb
            sb.table.side_effect = _table_router({
                "courses": mock_chain([{"id": course_id}]),
            })

            with patch("lecturelink_api.routers.lectures._sb_admin") as admin:
                admin.return_value = MagicMock()

                resp = await client.post(
                    "/api/lectures/upload",
                    data={"course_id": course_id, "title": "Bad file"},
                    files=[("files", ("virus.exe", io.BytesIO(b"x"), "application/octet-stream"))],
                )

        assert resp.status_code == 400
        assert "Unsupported file type" in resp.json()["detail"]

    @pytest.mark.asyncio
    async def test_upload_validates_course_ownership(self, client):
        bad_course = str(uuid.uuid4())

        with (
            patch("lecturelink_api.routers.lectures.create_client") as mc,
            patch("lecturelink_api.routers.lectures.check_rate_limit"),
        ):
            sb = MagicMock()
            mc.return_value = sb
            sb.table.side_effect = _table_router({
                "courses": mock_chain(None),  # not found
            })

            resp = await client.post(
                "/api/lectures/upload",
                data={"course_id": bad_course, "title": "No course"},
                files=[("files", ("audio.mp3", io.BytesIO(b"x"), "audio/mpeg"))],
            )

        assert resp.status_code == 404
        assert resp.json()["detail"] == "Course not found"


# ---------------------------------------------------------------------------
# Status
# ---------------------------------------------------------------------------


class TestLectureStatusProgression:
    """GET /api/lectures/{id}/status."""

    @pytest.mark.asyncio
    async def test_status_pending(self, client):
        lid = str(uuid.uuid4())
        with patch("lecturelink_api.routers.lectures.create_client") as mc:
            sb = MagicMock()
            mc.return_value = sb
            sb.table.return_value = mock_chain([{
                "processing_status": "pending",
                "processing_stage": None,
                "processing_progress": 0.0,
                "processing_error": None,
            }])

            resp = await client.get(f"/api/lectures/{lid}/status")

        assert resp.status_code == 200
        data = resp.json()
        assert data["processing_status"] == "pending"
        assert data["processing_progress"] == 0.0

    @pytest.mark.asyncio
    async def test_status_processing_with_stage(self, client):
        lid = str(uuid.uuid4())
        with patch("lecturelink_api.routers.lectures.create_client") as mc:
            sb = MagicMock()
            mc.return_value = sb
            sb.table.return_value = mock_chain([{
                "processing_status": "processing",
                "processing_stage": "transcribing",
                "processing_progress": 0.15,
                "processing_error": None,
            }])

            resp = await client.get(f"/api/lectures/{lid}/status")

        assert resp.status_code == 200
        data = resp.json()
        assert data["processing_status"] == "processing"
        assert data["processing_stage"] == "transcribing"
        assert data["processing_progress"] == pytest.approx(0.15)

    @pytest.mark.asyncio
    async def test_status_completed(self, client):
        lid = str(uuid.uuid4())
        with patch("lecturelink_api.routers.lectures.create_client") as mc:
            sb = MagicMock()
            mc.return_value = sb
            sb.table.return_value = mock_chain([{
                "processing_status": "completed",
                "processing_stage": "completed",
                "processing_progress": 1.0,
                "processing_error": None,
            }])

            resp = await client.get(f"/api/lectures/{lid}/status")

        assert resp.status_code == 200
        data = resp.json()
        assert data["processing_status"] == "completed"
        assert data["processing_progress"] == 1.0
        assert data["processing_error"] is None

    @pytest.mark.asyncio
    async def test_status_failed_shows_error(self, client):
        lid = str(uuid.uuid4())
        with patch("lecturelink_api.routers.lectures.create_client") as mc:
            sb = MagicMock()
            mc.return_value = sb
            sb.table.return_value = mock_chain([{
                "processing_status": "failed",
                "processing_stage": "transcribing",
                "processing_progress": 0.15,
                "processing_error": "Transcription timed out",
            }])

            resp = await client.get(f"/api/lectures/{lid}/status")

        assert resp.status_code == 200
        data = resp.json()
        assert data["processing_status"] == "failed"
        assert data["processing_error"] == "Transcription timed out"

    @pytest.mark.asyncio
    async def test_status_not_found(self, client):
        lid = str(uuid.uuid4())
        with patch("lecturelink_api.routers.lectures.create_client") as mc:
            sb = MagicMock()
            mc.return_value = sb
            sb.table.return_value = mock_chain(None)

            resp = await client.get(f"/api/lectures/{lid}/status")

        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# List & detail
# ---------------------------------------------------------------------------


class TestLectureListAndDetail:
    """GET /api/courses/{id}/lectures and GET /api/lectures/{id}."""

    @pytest.mark.asyncio
    async def test_list_lectures_returns_array(self, client):
        course = make_course()
        lec1 = make_lecture(course["id"])
        lec2 = make_lecture(course["id"], title="Lecture 2: Heat Transfer")

        with patch("lecturelink_api.routers.lectures.create_client") as mc:
            sb = MagicMock()
            mc.return_value = sb
            sb.table.side_effect = _table_router({
                "courses": mock_chain([{"id": course["id"]}]),
                "lectures": mock_chain([lec1, lec2]),
            })

            resp = await client.get(f"/api/courses/{course['id']}/lectures")

        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 2
        assert data[0]["title"] == lec1["title"]

    @pytest.mark.asyncio
    async def test_list_lectures_course_not_found(self, client):
        cid = str(uuid.uuid4())
        with patch("lecturelink_api.routers.lectures.create_client") as mc:
            sb = MagicMock()
            mc.return_value = sb
            sb.table.side_effect = _table_router({
                "courses": mock_chain(None),
            })

            resp = await client.get(f"/api/courses/{cid}/lectures")

        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_get_lecture_detail_includes_concepts(self, client):
        course = make_course()
        lec = make_lecture(course["id"])
        concept = make_concept(course["id"], lec["id"], title="First Law")
        chunk = make_chunk(lec["id"], slide_number=3)

        call_count = {"n": 0}

        def _table(name):
            nonlocal call_count
            call_count["n"] += 1
            if name == "lectures":
                return mock_chain([lec])
            if name == "concepts":
                return mock_chain([
                    {
                        "id": concept["id"],
                        "title": concept["title"],
                        "description": concept["description"],
                        "category": concept["category"],
                        "difficulty_estimate": concept["difficulty_estimate"],
                    }
                ])
            if name == "concept_assessment_links":
                return mock_chain([])
            if name == "lecture_chunks":
                return mock_chain([{"slide_number": 3}, {"slide_number": 5}])
            return mock_chain(None)

        with patch("lecturelink_api.routers.lectures.create_client") as mc:
            sb = MagicMock()
            mc.return_value = sb
            sb.table.side_effect = _table

            resp = await client.get(f"/api/lectures/{lec['id']}")

        assert resp.status_code == 200
        data = resp.json()
        assert data["title"] == lec["title"]
        assert data["slide_count"] == 2  # slides 3 and 5
        assert len(data["concepts"]) == 1
        assert data["concepts"][0]["title"] == "First Law"
