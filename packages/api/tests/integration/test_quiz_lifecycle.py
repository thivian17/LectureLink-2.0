"""Integration tests for quiz generation, retrieval, submission, and listing.

Full lifecycle: generate → poll status → take quiz → submit → score.
"""

from __future__ import annotations

import uuid
from unittest.mock import MagicMock, patch

import pytest

from tests.integration.conftest import (
    FAKE_USER_ID,
    make_course,
    make_quiz,
    make_quiz_question,
    mock_chain,
)

pytestmark = [pytest.mark.integration]


def _table_router(table_map: dict[str, MagicMock]):
    def _route(name):
        return table_map.get(name, mock_chain(None))

    return _route


# ---------------------------------------------------------------------------
# Generation
# ---------------------------------------------------------------------------


class TestQuizGeneration:
    """POST /api/quizzes/generate."""

    @pytest.mark.asyncio
    async def test_generate_returns_201_with_quiz_id(self, client):
        course_id = str(uuid.uuid4())
        quiz_id = str(uuid.uuid4())

        with (
            patch("lecturelink_api.routers.quizzes.create_client") as mc,
            patch(
                "lecturelink_api.routers.quizzes.check_rate_limit",
            ),
            patch("lecturelink_api.routers.quizzes.generate_quiz_background"),
        ):
            sb = MagicMock()
            mc.return_value = sb

            sb.table.side_effect = _table_router({
                "courses": mock_chain([{"id": course_id, "name": "PHYS 201"}]),
                "quizzes": mock_chain([{"id": quiz_id}]),
            })

            resp = await client.post(
                "/api/quizzes/generate",
                json={
                    "course_id": course_id,
                    "num_questions": 5,
                    "difficulty": "medium",
                },
            )

        assert resp.status_code == 201
        data = resp.json()
        assert data["quiz_id"] == quiz_id
        assert data["status"] == "generating"

    @pytest.mark.asyncio
    async def test_generate_course_not_found(self, client):
        bad_id = str(uuid.uuid4())

        with (
            patch("lecturelink_api.routers.quizzes.create_client") as mc,
            patch(
                "lecturelink_api.routers.quizzes.check_rate_limit",
            ),
        ):
            sb = MagicMock()
            mc.return_value = sb
            sb.table.side_effect = _table_router({
                "courses": mock_chain(None),
            })

            resp = await client.post(
                "/api/quizzes/generate",
                json={"course_id": bad_id, "num_questions": 5, "difficulty": "medium"},
            )

        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_generate_with_assessment_target(self, client):
        course_id = str(uuid.uuid4())
        quiz_id = str(uuid.uuid4())
        assessment_id = str(uuid.uuid4())

        with (
            patch("lecturelink_api.routers.quizzes.create_client") as mc,
            patch(
                "lecturelink_api.routers.quizzes.check_rate_limit",
            ),
            patch("lecturelink_api.routers.quizzes.generate_quiz_background"),
        ):
            sb = MagicMock()
            mc.return_value = sb

            sb.table.side_effect = _table_router({
                "courses": mock_chain([{"id": course_id, "name": "PHYS 201"}]),
                "assessments": mock_chain([{"title": "Midterm 1"}]),
                "quizzes": mock_chain([{"id": quiz_id}]),
            })

            resp = await client.post(
                "/api/quizzes/generate",
                json={
                    "course_id": course_id,
                    "target_assessment_id": assessment_id,
                    "num_questions": 10,
                    "difficulty": "hard",
                },
            )

        assert resp.status_code == 201


# ---------------------------------------------------------------------------
# Retrieval
# ---------------------------------------------------------------------------


class TestQuizRetrieval:
    """GET /api/quizzes/{id}."""

    @pytest.mark.asyncio
    async def test_get_ready_quiz_includes_questions(self, client):
        quiz_id = str(uuid.uuid4())
        q1_id = str(uuid.uuid4())
        q2_id = str(uuid.uuid4())

        quiz_data = make_quiz("cid", quiz_id=quiz_id, question_count=2)
        q1 = make_quiz_question(quiz_id, question_index=0, question_id=q1_id)
        q2 = make_quiz_question(quiz_id, question_index=1, question_id=q2_id,
                                question_text="What is entropy?")

        call_n = {"n": 0}

        def _table(name):
            call_n["n"] += 1
            if name == "quizzes":
                return mock_chain([quiz_data])
            if name == "quiz_questions":
                return mock_chain([q1, q2])
            return mock_chain(None)

        with patch("lecturelink_api.routers.quizzes.create_client") as mc:
            sb = MagicMock()
            mc.return_value = sb
            sb.table.side_effect = _table

            resp = await client.get(f"/api/quizzes/{quiz_id}")

        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ready"
        assert "questions" in data
        assert len(data["questions"]) == 2

    @pytest.mark.asyncio
    async def test_get_quiz_strips_is_correct_from_options(self, client):
        """CRITICAL: Options must NOT include is_correct field."""
        quiz_id = str(uuid.uuid4())
        quiz_data = make_quiz("cid", quiz_id=quiz_id)
        q = make_quiz_question(quiz_id)

        def _table(name):
            if name == "quizzes":
                return mock_chain([quiz_data])
            if name == "quiz_questions":
                return mock_chain([q])
            return mock_chain(None)

        with patch("lecturelink_api.routers.quizzes.create_client") as mc:
            sb = MagicMock()
            mc.return_value = sb
            sb.table.side_effect = _table

            resp = await client.get(f"/api/quizzes/{quiz_id}")

        assert resp.status_code == 200
        questions = resp.json()["questions"]
        for question in questions:
            if question.get("options"):
                for opt in question["options"]:
                    assert "is_correct" not in opt, "is_correct leaked to client!"

    @pytest.mark.asyncio
    async def test_get_quiz_not_found(self, client):
        bad_id = str(uuid.uuid4())

        with patch("lecturelink_api.routers.quizzes.create_client") as mc:
            sb = MagicMock()
            mc.return_value = sb
            sb.table.return_value = mock_chain(None)

            resp = await client.get(f"/api/quizzes/{bad_id}")

        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_generating_quiz_has_no_questions(self, client):
        quiz_id = str(uuid.uuid4())
        quiz_data = make_quiz("cid", quiz_id=quiz_id, status="generating")

        with patch("lecturelink_api.routers.quizzes.create_client") as mc:
            sb = MagicMock()
            mc.return_value = sb
            sb.table.return_value = mock_chain([quiz_data])

            resp = await client.get(f"/api/quizzes/{quiz_id}")

        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "generating"
        assert "questions" not in data


# ---------------------------------------------------------------------------
# Submission
# ---------------------------------------------------------------------------


class TestQuizSubmission:
    """POST /api/quizzes/{id}/submit."""

    @pytest.mark.asyncio
    async def test_submit_returns_scored_results(self, client):
        quiz_id = str(uuid.uuid4())
        q1_id = str(uuid.uuid4())
        scoring_result = {
            "score": 1.0,
            "total_questions": 1,
            "correct_count": 1,
            "results": [
                {
                    "question_id": q1_id,
                    "is_correct": True,
                    "correct_answer": "A",
                    "explanation": "Correct!",
                    "source_chunks": [],
                }
            ],
        }

        with (
            patch("lecturelink_api.routers.quizzes.create_client") as mc,
            patch(
                "lecturelink_api.routers.quizzes.score_quiz",
                return_value=scoring_result,
            ),
        ):
            sb = MagicMock()
            mc.return_value = sb
            sb.table.return_value = mock_chain([{"id": quiz_id, "status": "ready"}])

            resp = await client.post(
                f"/api/quizzes/{quiz_id}/submit",
                json={
                    "answers": [
                        {"question_id": q1_id, "student_answer": "A"},
                    ]
                },
            )

        assert resp.status_code == 200
        data = resp.json()
        assert data["score"] == 1.0
        assert data["total_questions"] == 1
        assert data["correct_count"] == 1
        assert len(data["results"]) == 1

    @pytest.mark.asyncio
    async def test_submit_partial_score(self, client):
        quiz_id = str(uuid.uuid4())
        q1_id = str(uuid.uuid4())
        q2_id = str(uuid.uuid4())
        scoring_result = {
            "score": 0.5,
            "total_questions": 2,
            "correct_count": 1,
            "results": [
                {"question_id": q1_id, "is_correct": True, "correct_answer": "A",
                 "explanation": "Correct!", "source_chunks": []},
                {"question_id": q2_id, "is_correct": False, "correct_answer": "B",
                 "explanation": "Entropy increases.", "source_chunks": []},
            ],
        }

        with (
            patch("lecturelink_api.routers.quizzes.create_client") as mc,
            patch(
                "lecturelink_api.routers.quizzes.score_quiz",
                return_value=scoring_result,
            ),
        ):
            sb = MagicMock()
            mc.return_value = sb
            sb.table.return_value = mock_chain([{"id": quiz_id, "status": "ready"}])

            resp = await client.post(
                f"/api/quizzes/{quiz_id}/submit",
                json={
                    "answers": [
                        {"question_id": q1_id, "student_answer": "A"},
                        {"question_id": q2_id, "student_answer": "C"},
                    ]
                },
            )

        assert resp.status_code == 200
        data = resp.json()
        assert data["score"] == pytest.approx(0.5)
        assert data["correct_count"] == 1

    @pytest.mark.asyncio
    async def test_submit_quiz_not_found(self, client):
        bad_id = str(uuid.uuid4())

        with patch("lecturelink_api.routers.quizzes.create_client") as mc:
            sb = MagicMock()
            mc.return_value = sb
            sb.table.return_value = mock_chain(None)

            resp = await client.post(
                f"/api/quizzes/{bad_id}/submit",
                json={"answers": [{"question_id": "x", "student_answer": "A"}]},
            )

        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_submit_not_ready_quiz_rejected(self, client):
        quiz_id = str(uuid.uuid4())

        with patch("lecturelink_api.routers.quizzes.create_client") as mc:
            sb = MagicMock()
            mc.return_value = sb
            sb.table.return_value = mock_chain([{"id": quiz_id, "status": "generating"}])

            resp = await client.post(
                f"/api/quizzes/{quiz_id}/submit",
                json={"answers": [{"question_id": "x", "student_answer": "A"}]},
            )

        assert resp.status_code == 400
        assert "not ready" in resp.json()["detail"].lower()


# ---------------------------------------------------------------------------
# Listing
# ---------------------------------------------------------------------------


class TestQuizListing:
    """GET /api/courses/{id}/quizzes."""

    @pytest.mark.asyncio
    async def test_list_quizzes_for_course(self, client):
        course_id = str(uuid.uuid4())
        q1 = make_quiz(course_id, status="ready", question_count=5)
        q2 = make_quiz(course_id, status="generating", question_count=0)

        with patch("lecturelink_api.routers.quizzes.create_client") as mc:
            sb = MagicMock()
            mc.return_value = sb
            sb.table.side_effect = _table_router({
                "courses": mock_chain([{"id": course_id}]),
                "quizzes": mock_chain([q1, q2]),
            })

            resp = await client.get(f"/api/courses/{course_id}/quizzes")

        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 2
        assert data[0]["question_count"] == 5

    @pytest.mark.asyncio
    async def test_list_quizzes_course_not_found(self, client):
        bad_id = str(uuid.uuid4())

        with patch("lecturelink_api.routers.quizzes.create_client") as mc:
            sb = MagicMock()
            mc.return_value = sb
            sb.table.side_effect = _table_router({
                "courses": mock_chain(None),
            })

            resp = await client.get(f"/api/courses/{bad_id}/quizzes")

        assert resp.status_code == 404
