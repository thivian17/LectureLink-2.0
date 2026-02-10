"""Integration tests for search and Q&A endpoints.

Verifies POST /api/search and POST /api/qa with mocked service functions.
"""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from tests.integration.conftest import (
    make_search_result,
    mock_chain,
)

pytestmark = [pytest.mark.integration]


# ---------------------------------------------------------------------------
# Search
# ---------------------------------------------------------------------------


class TestSearchEndpoint:
    """POST /api/search."""

    @pytest.mark.asyncio
    async def test_search_returns_results(self, client):
        course_id = str(uuid.uuid4())
        lecture_id = str(uuid.uuid4())
        results = [
            make_search_result(lecture_id),
            make_search_result(lecture_id, content="Entropy increases in isolated systems."),
        ]

        with (
            patch("lecturelink_api.routers.search.create_client") as mc,
            patch(
                "lecturelink_api.routers.search.search_lectures",
                new_callable=AsyncMock,
                return_value=results,
            ),
            patch(
                "lecturelink_api.routers.search.highlight_search_terms",
                side_effect=lambda content, query: f"<b>{query}</b> in {content[:30]}",
            ),
        ):
            sb = MagicMock()
            mc.return_value = sb
            sb.table.return_value = mock_chain([{"id": course_id, "name": "PHYS 201"}])

            resp = await client.post(
                "/api/search",
                json={"course_id": course_id, "query": "heat transfer"},
            )

        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 2
        assert data[0]["lecture_id"] == lecture_id
        assert data[0]["score"] == pytest.approx(0.85)
        assert data[0]["highlight"] is not None

    @pytest.mark.asyncio
    async def test_search_empty_results(self, client):
        course_id = str(uuid.uuid4())

        with (
            patch("lecturelink_api.routers.search.create_client") as mc,
            patch(
                "lecturelink_api.routers.search.search_lectures",
                new_callable=AsyncMock,
                return_value=[],
            ),
        ):
            sb = MagicMock()
            mc.return_value = sb
            sb.table.return_value = mock_chain([{"id": course_id, "name": "PHYS 201"}])

            resp = await client.post(
                "/api/search",
                json={"course_id": course_id, "query": "quantum entanglement"},
            )

        assert resp.status_code == 200
        assert resp.json() == []

    @pytest.mark.asyncio
    async def test_search_course_not_found(self, client):
        bad_id = str(uuid.uuid4())

        with patch("lecturelink_api.routers.search.create_client") as mc:
            sb = MagicMock()
            mc.return_value = sb
            sb.table.return_value = mock_chain(None)

            resp = await client.post(
                "/api/search",
                json={"course_id": bad_id, "query": "heat"},
            )

        assert resp.status_code == 404
        assert resp.json()["detail"] == "Course not found"

    @pytest.mark.asyncio
    async def test_search_respects_limit(self, client):
        """Verify limit parameter is forwarded to service."""
        course_id = str(uuid.uuid4())
        lecture_id = str(uuid.uuid4())
        results = [make_search_result(lecture_id) for _ in range(3)]

        with (
            patch("lecturelink_api.routers.search.create_client") as mc,
            patch(
                "lecturelink_api.routers.search.search_lectures",
                new_callable=AsyncMock,
                return_value=results,
            ) as mock_search,
            patch(
                "lecturelink_api.routers.search.highlight_search_terms",
                return_value="highlighted",
            ),
        ):
            sb = MagicMock()
            mc.return_value = sb
            sb.table.return_value = mock_chain([{"id": course_id, "name": "PHYS 201"}])

            resp = await client.post(
                "/api/search",
                json={"course_id": course_id, "query": "heat", "limit": 3},
            )

        assert resp.status_code == 200
        _, kwargs = mock_search.call_args
        assert kwargs.get("limit") == 3 or mock_search.call_args[1].get("limit") == 3

    @pytest.mark.asyncio
    async def test_search_filters_by_lecture_ids(self, client):
        course_id = str(uuid.uuid4())
        lecture_id = str(uuid.uuid4())

        with (
            patch("lecturelink_api.routers.search.create_client") as mc,
            patch(
                "lecturelink_api.routers.search.search_lectures",
                new_callable=AsyncMock,
                return_value=[make_search_result(lecture_id)],
            ) as mock_search,
            patch(
                "lecturelink_api.routers.search.highlight_search_terms",
                return_value="highlighted",
            ),
        ):
            sb = MagicMock()
            mc.return_value = sb
            sb.table.return_value = mock_chain([{"id": course_id, "name": "PHYS 201"}])

            resp = await client.post(
                "/api/search",
                json={
                    "course_id": course_id,
                    "query": "heat",
                    "lecture_ids": [lecture_id],
                },
            )

        assert resp.status_code == 200
        _, kwargs = mock_search.call_args
        assert kwargs.get("lecture_ids") == [lecture_id]


# ---------------------------------------------------------------------------
# Q&A
# ---------------------------------------------------------------------------


class TestQAEndpoint:
    """POST /api/qa."""

    def _qa_result(self):
        return {
            "answer": "Heat transfers through three mechanisms.",
            "confidence": 0.92,
            "source_chunks": [
                {
                    "chunk_id": str(uuid.uuid4()),
                    "content": "Conduction occurs via molecular vibration.",
                    "lecture_title": "Lecture 1: Thermodynamics",
                    "timestamp": 110.5,
                }
            ],
            "follow_up_suggestions": [
                "What is the difference between conduction and convection?",
            ],
        }

    @pytest.mark.asyncio
    async def test_qa_returns_answer(self, client):
        course_id = str(uuid.uuid4())
        qa_result = self._qa_result()

        with (
            patch("lecturelink_api.routers.search.create_client") as mc,
            patch(
                "lecturelink_api.routers.search.check_rate_limit",
            ),
            patch(
                "lecturelink_api.routers.search.ask_lecture_question",
                new_callable=AsyncMock,
                return_value=qa_result,
            ),
        ):
            sb = MagicMock()
            mc.return_value = sb
            sb.table.return_value = mock_chain([{"id": course_id, "name": "PHYS 201"}])

            resp = await client.post(
                "/api/qa",
                json={"course_id": course_id, "question": "How does heat transfer work?"},
            )

        assert resp.status_code == 200
        data = resp.json()
        assert data["answer"] == qa_result["answer"]
        assert data["confidence"] == pytest.approx(0.92)
        assert len(data["follow_up_suggestions"]) >= 1

    @pytest.mark.asyncio
    async def test_qa_no_content_fallback(self, client):
        course_id = str(uuid.uuid4())
        empty_result = {
            "answer": "I don't have enough lecture content to answer that question.",
            "confidence": 0.0,
            "source_chunks": [],
            "follow_up_suggestions": [],
        }

        with (
            patch("lecturelink_api.routers.search.create_client") as mc,
            patch(
                "lecturelink_api.routers.search.check_rate_limit",
            ),
            patch(
                "lecturelink_api.routers.search.ask_lecture_question",
                new_callable=AsyncMock,
                return_value=empty_result,
            ),
        ):
            sb = MagicMock()
            mc.return_value = sb
            sb.table.return_value = mock_chain([{"id": course_id, "name": "PHYS 201"}])

            resp = await client.post(
                "/api/qa",
                json={"course_id": course_id, "question": "What is dark matter?"},
            )

        assert resp.status_code == 200
        data = resp.json()
        assert data["confidence"] == 0.0
        assert data["source_chunks"] == []

    @pytest.mark.asyncio
    async def test_qa_course_not_found(self, client):
        bad_id = str(uuid.uuid4())

        with (
            patch("lecturelink_api.routers.search.create_client") as mc,
            patch(
                "lecturelink_api.routers.search.check_rate_limit",
            ),
        ):
            sb = MagicMock()
            mc.return_value = sb
            sb.table.return_value = mock_chain(None)

            resp = await client.post(
                "/api/qa",
                json={"course_id": bad_id, "question": "What is heat?"},
            )

        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_qa_empty_question_rejected(self, client):
        """Empty question string fails Pydantic validation (min_length=1)."""
        course_id = str(uuid.uuid4())

        resp = await client.post(
            "/api/qa",
            json={"course_id": course_id, "question": ""},
        )

        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_qa_includes_source_chunks(self, client):
        course_id = str(uuid.uuid4())
        chunk_id = str(uuid.uuid4())
        qa_result = {
            "answer": "Heat transfer is a fundamental concept.",
            "confidence": 0.85,
            "source_chunks": [
                {
                    "chunk_id": chunk_id,
                    "content": "Heat flows from hot to cold.",
                    "lecture_title": "Lecture 1",
                    "timestamp": 42.0,
                }
            ],
            "follow_up_suggestions": [],
        }

        with (
            patch("lecturelink_api.routers.search.create_client") as mc,
            patch(
                "lecturelink_api.routers.search.check_rate_limit",
            ),
            patch(
                "lecturelink_api.routers.search.ask_lecture_question",
                new_callable=AsyncMock,
                return_value=qa_result,
            ),
        ):
            sb = MagicMock()
            mc.return_value = sb
            sb.table.return_value = mock_chain([{"id": course_id, "name": "PHYS 201"}])

            resp = await client.post(
                "/api/qa",
                json={"course_id": course_id, "question": "What is heat transfer?"},
            )

        assert resp.status_code == 200
        chunks = resp.json()["source_chunks"]
        assert len(chunks) == 1
        assert chunks[0]["chunk_id"] == chunk_id
        assert "content" in chunks[0]
        assert "lecture_title" in chunks[0]
