"""Performance baseline tests for API endpoints.

Mock-based latency tests verify that endpoint overhead is minimal.
Live tests (gated behind @pytest.mark.live) measure real-world latency.
"""

from __future__ import annotations

import time
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from tests.integration.conftest import (
    make_quiz,
    make_quiz_question,
    make_search_result,
    mock_chain,
)

pytestmark = [pytest.mark.integration]


def _table_router(table_map: dict[str, MagicMock]):
    def _route(name):
        return table_map.get(name, mock_chain(None))

    return _route


# ---------------------------------------------------------------------------
# Mock-based latency (measures framework overhead, not external I/O)
# ---------------------------------------------------------------------------


class TestEndpointLatency:
    """Verify API response times are within acceptable bounds (mocked)."""

    @pytest.mark.asyncio
    async def test_lecture_status_latency(self, client):
        """GET /api/lectures/{id}/status responds within 200ms."""
        lid = str(uuid.uuid4())

        with patch("lecturelink_api.auth.create_client") as mc:
            sb = MagicMock()
            mc.return_value = sb
            sb.table.return_value = mock_chain([{
                "processing_status": "completed",
                "processing_stage": "completed",
                "processing_progress": 1.0,
                "processing_error": None,
            }])

            timings = []
            for _ in range(3):
                start = time.perf_counter()
                resp = await client.get(f"/api/lectures/{lid}/status")
                elapsed = time.perf_counter() - start
                assert resp.status_code == 200
                timings.append(elapsed)

        median = sorted(timings)[1]
        assert median < 0.2, f"Median {median:.3f}s exceeds 200ms target"

    @pytest.mark.asyncio
    async def test_search_endpoint_latency(self, client):
        """POST /api/search responds within 500ms (mocked backend)."""
        course_id = str(uuid.uuid4())
        lecture_id = str(uuid.uuid4())
        results = [make_search_result(lecture_id) for _ in range(10)]

        with (
            patch("lecturelink_api.auth.create_client") as mc,
            patch(
                "lecturelink_api.routers.search.search_lectures",
                new_callable=AsyncMock,
                return_value=results,
            ),
            patch(
                "lecturelink_api.routers.search.highlight_search_terms",
                return_value="highlighted",
            ),
        ):
            sb = MagicMock()
            mc.return_value = sb
            sb.table.return_value = mock_chain([{"id": course_id, "name": "PHYS 201"}])

            timings = []
            for _ in range(3):
                start = time.perf_counter()
                resp = await client.post(
                    "/api/search",
                    json={"course_id": course_id, "query": "heat transfer"},
                )
                elapsed = time.perf_counter() - start
                assert resp.status_code == 200
                timings.append(elapsed)

        median = sorted(timings)[1]
        assert median < 0.5, f"Median {median:.3f}s exceeds 500ms target"

    @pytest.mark.asyncio
    async def test_quiz_questions_latency(self, client):
        """GET /api/quizzes/{id} (with questions) responds within 300ms."""
        quiz_id = str(uuid.uuid4())
        quiz_data = make_quiz("cid", quiz_id=quiz_id, question_count=10)
        questions = [
            make_quiz_question(quiz_id, question_index=i)
            for i in range(10)
        ]

        def _table(name):
            if name == "quizzes":
                return mock_chain([quiz_data])
            if name == "quiz_questions":
                return mock_chain(questions)
            return mock_chain(None)

        with patch("lecturelink_api.auth.create_client") as mc:
            sb = MagicMock()
            mc.return_value = sb
            sb.table.side_effect = _table

            timings = []
            for _ in range(3):
                start = time.perf_counter()
                resp = await client.get(f"/api/quizzes/{quiz_id}")
                elapsed = time.perf_counter() - start
                assert resp.status_code == 200
                timings.append(elapsed)

        median = sorted(timings)[1]
        assert median < 0.3, f"Median {median:.3f}s exceeds 300ms target"

    @pytest.mark.asyncio
    async def test_quiz_submit_latency(self, client):
        """POST /api/quizzes/{id}/submit responds within 500ms."""
        quiz_id = str(uuid.uuid4())
        q_id = str(uuid.uuid4())
        scoring = {
            "score": 0.8,
            "total_questions": 5,
            "correct_count": 4,
            "results": [
                {"question_id": q_id, "is_correct": True,
                 "correct_answer": "A", "explanation": "ok", "source_chunks": []}
            ],
        }

        with (
            patch("lecturelink_api.auth.create_client") as mc,
            patch(
                "lecturelink_api.routers.quizzes.score_quiz",
                return_value=scoring,
            ),
        ):
            sb = MagicMock()
            mc.return_value = sb
            sb.table.return_value = mock_chain([{"id": quiz_id, "status": "ready"}])

            timings = []
            for _ in range(3):
                start = time.perf_counter()
                resp = await client.post(
                    f"/api/quizzes/{quiz_id}/submit",
                    json={"answers": [{"question_id": q_id, "student_answer": "A"}]},
                )
                elapsed = time.perf_counter() - start
                assert resp.status_code == 200
                timings.append(elapsed)

        median = sorted(timings)[1]
        assert median < 0.5, f"Median {median:.3f}s exceeds 500ms target"

    @pytest.mark.asyncio
    async def test_list_lectures_latency(self, client):
        """GET /api/courses/{id}/lectures responds within 200ms."""
        course_id = str(uuid.uuid4())

        with patch("lecturelink_api.auth.create_client") as mc:
            sb = MagicMock()
            mc.return_value = sb
            sb.table.side_effect = _table_router({
                "courses": mock_chain([{"id": course_id}]),
                "lectures": mock_chain([]),
            })

            timings = []
            for _ in range(3):
                start = time.perf_counter()
                resp = await client.get(f"/api/courses/{course_id}/lectures")
                elapsed = time.perf_counter() - start
                assert resp.status_code == 200
                timings.append(elapsed)

        median = sorted(timings)[1]
        assert median < 0.2, f"Median {median:.3f}s exceeds 200ms target"

    @pytest.mark.asyncio
    async def test_list_concepts_latency(self, client):
        """GET /api/courses/{id}/concepts responds within 300ms."""
        course_id = str(uuid.uuid4())

        def _table(name):
            if name == "courses":
                return mock_chain([{"id": course_id}])
            if name == "concepts":
                return mock_chain([])
            return mock_chain(None)

        with patch("lecturelink_api.auth.create_client") as mc:
            sb = MagicMock()
            mc.return_value = sb
            sb.table.side_effect = _table

            timings = []
            for _ in range(3):
                start = time.perf_counter()
                resp = await client.get(f"/api/courses/{course_id}/concepts")
                elapsed = time.perf_counter() - start
                assert resp.status_code == 200
                timings.append(elapsed)

        median = sorted(timings)[1]
        assert median < 0.3, f"Median {median:.3f}s exceeds 300ms target"
