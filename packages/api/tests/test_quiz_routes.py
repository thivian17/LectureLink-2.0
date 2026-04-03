"""Tests for quiz generation, retrieval, submission, and concept endpoints."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
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
OTHER_USER_ID = str(uuid.uuid4())


def _fake_user():
    return {"id": FAKE_USER_ID, "email": FAKE_EMAIL, "token": FAKE_TOKEN}


def _now_str():
    return datetime.now(UTC).isoformat()


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


def _sample_quiz(quiz_id: str | None = None, **overrides) -> dict:
    qid = quiz_id or str(uuid.uuid4())
    base = {
        "id": qid,
        "course_id": str(uuid.uuid4()),
        "user_id": FAKE_USER_ID,
        "title": "Practice Quiz - PHYS 201",
        "status": "ready",
        "question_count": 2,
        "difficulty": "mixed",
        "best_score": None,
        "attempt_count": 0,
        "created_at": _now_str(),
    }
    base.update(overrides)
    return base


def _sample_questions(quiz_id: str) -> list[dict]:
    return [
        {
            "id": str(uuid.uuid4()),
            "quiz_id": quiz_id,
            "question_index": 0,
            "question_type": "mcq",
            "question_text": "What is a thermodynamic system?",
            "options": [
                {"label": "A", "text": "A region of space", "is_correct": True},
                {"label": "B", "text": "A heat engine", "is_correct": False},
                {"label": "C", "text": "A chemical compound", "is_correct": False},
                {"label": "D", "text": "A physical force", "is_correct": False},
            ],
            "correct_answer": "A",
            "explanation": "A thermodynamic system is a region of space.",
            "source_chunk_ids": [],
        },
        {
            "id": str(uuid.uuid4()),
            "quiz_id": quiz_id,
            "question_index": 1,
            "question_type": "true_false",
            "question_text": "Energy can be created.",
            "options": [
                {"label": "True", "text": "True", "is_correct": False},
                {"label": "False", "text": "False", "is_correct": True},
            ],
            "correct_answer": "False",
            "explanation": "Energy cannot be created or destroyed.",
            "source_chunk_ids": [],
        },
    ]


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
    from lecturelink_api.services.task_queue import get_task_queue
    mock_tq = MagicMock()
    mock_tq.enqueue_lecture_processing = AsyncMock()
    mock_tq.enqueue_quiz_generation = AsyncMock()
    mock_tq.enqueue_syllabus_processing = AsyncMock()
    app.dependency_overrides[get_task_queue] = lambda: mock_tq
    yield mock_tq
    app.dependency_overrides.pop(get_task_queue, None)


@pytest_asyncio.fixture()
async def client(_override_auth, _override_settings, _override_task_queue):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


# ---------------------------------------------------------------------------
# Quiz generation tests
# ---------------------------------------------------------------------------


class TestQuizGenerate:
    @pytest.mark.asyncio
    async def test_generate_returns_quiz_id(self, client):
        course_id = str(uuid.uuid4())
        quiz_id = str(uuid.uuid4())

        with (
            patch("lecturelink_api.auth.create_client") as mock_create,
            patch(
                "lecturelink_api.routers.quizzes.check_rate_limit",
            ),
        ):
            sb = MagicMock()
            mock_create.return_value = sb

            course_chain = _mock_chain([{"id": course_id, "name": "PHYS 201"}])
            insert_chain = _mock_chain([{"id": quiz_id}])

            sb.table.side_effect = lambda name: (
                course_chain if name == "courses" else insert_chain
            )

            resp = await client.post(
                "/api/quizzes/generate",
                json={"course_id": course_id},
            )

        assert resp.status_code == 201
        data = resp.json()
        assert data["quiz_id"] == quiz_id
        assert data["status"] == "generating"

    @pytest.mark.asyncio
    async def test_generate_rate_limited(self, client):
        from fastapi import HTTPException

        with (
            patch("lecturelink_api.auth.create_client") as mock_create,
            patch(
                "lecturelink_api.routers.quizzes.check_rate_limit",
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
                "/api/quizzes/generate",
                json={"course_id": str(uuid.uuid4())},
            )

        assert resp.status_code == 429


# ---------------------------------------------------------------------------
# Quiz retrieval tests
# ---------------------------------------------------------------------------


class TestQuizGet:
    @pytest.mark.asyncio
    async def test_get_ready_quiz_includes_answers(self, client):
        quiz = _sample_quiz()
        questions = _sample_questions(quiz["id"])

        with patch("lecturelink_api.auth.create_client") as mock_create:
            sb = MagicMock()
            mock_create.return_value = sb

            quiz_chain = _mock_chain([quiz])
            questions_chain = _mock_chain(questions)

            call_count = {"n": 0}

            def table_side_effect(name):
                call_count["n"] += 1
                if name == "quiz_questions":
                    return questions_chain
                return quiz_chain

            sb.table.side_effect = table_side_effect

            resp = await client.get(f"/api/quizzes/{quiz['id']}")

        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ready"
        assert "questions" in data
        assert len(data["questions"]) == 2

        # Verify correct_answer, correct_option_index, and explanation are included
        for q in data["questions"]:
            assert "correct_answer" in q
            assert "correct_option_index" in q
            assert "explanation" in q
            # is_correct should still be stripped from options
            if q.get("options"):
                for opt in q["options"]:
                    assert "is_correct" not in opt

        # MCQ: correct_answer="A" with option A is_correct → index 0
        mcq = [q for q in data["questions"] if q["question_type"] == "mcq"][0]
        assert mcq["correct_option_index"] == 0
        assert mcq["correct_answer"] == "A region of space"

        # True/false: correct_answer="False" with False is_correct → index 1
        tf = [q for q in data["questions"] if q["question_type"] == "true_false"][0]
        assert tf["correct_option_index"] == 1

    @pytest.mark.asyncio
    async def test_get_generating_quiz_no_questions(self, client):
        quiz = _sample_quiz(status="generating")

        with patch("lecturelink_api.auth.create_client") as mock_create:
            sb = MagicMock()
            mock_create.return_value = sb
            sb.table.return_value = _mock_chain([quiz])

            resp = await client.get(f"/api/quizzes/{quiz['id']}")

        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "generating"
        assert "questions" not in data


# ---------------------------------------------------------------------------
# Quiz submission tests
# ---------------------------------------------------------------------------


class TestQuizSubmit:
    @pytest.mark.asyncio
    async def test_submit_returns_score_with_answers(self, client):
        quiz = _sample_quiz()
        questions = _sample_questions(quiz["id"])

        mock_score_result = {
            "score": 50.0,
            "total_questions": 2,
            "correct_count": 1,
            "results": [
                {
                    "question_id": questions[0]["id"],
                    "is_correct": True,
                    "student_answer": "A",
                    "correct_answer": "A",
                    "explanation": "A thermodynamic system is a region of space.",
                    "source_chunk_ids": [],
                },
                {
                    "question_id": questions[1]["id"],
                    "is_correct": False,
                    "student_answer": "True",
                    "correct_answer": "False",
                    "explanation": "Energy cannot be created or destroyed.",
                    "source_chunk_ids": [],
                },
            ],
        }

        with (
            patch("lecturelink_api.auth.create_client") as mock_create,
            patch(
                "lecturelink_api.routers.quizzes.score_quiz",
                return_value=mock_score_result,
            ),
        ):
            sb = MagicMock()
            mock_create.return_value = sb
            sb.table.return_value = _mock_chain([{"id": quiz["id"], "status": "ready"}])

            resp = await client.post(
                f"/api/quizzes/{quiz['id']}/submit",
                json={
                    "answers": [
                        {"question_id": questions[0]["id"], "student_answer": "A"},
                        {"question_id": questions[1]["id"], "student_answer": "True"},
                    ]
                },
            )

        assert resp.status_code == 200
        data = resp.json()
        assert data["score"] == 50.0
        assert data["correct_count"] == 1
        assert data["total_questions"] == 2

        # After submission, answers SHOULD include correct_answer + explanation
        for r in data["results"]:
            assert "correct_answer" in r
            assert "explanation" in r


# ---------------------------------------------------------------------------
# Course quizzes / concepts list tests
# ---------------------------------------------------------------------------


class TestCourseQuizzes:
    @pytest.mark.asyncio
    async def test_list_course_quizzes(self, client):
        course_id = str(uuid.uuid4())
        quizzes = [
            _sample_quiz(course_id=course_id),
            _sample_quiz(course_id=course_id, best_score=85.0, attempt_count=2),
        ]

        with patch("lecturelink_api.auth.create_client") as mock_create:
            sb = MagicMock()
            mock_create.return_value = sb

            course_chain = _mock_chain({"id": course_id})
            quizzes_chain = _mock_chain(quizzes)

            sb.table.side_effect = lambda name: (
                course_chain if name == "courses" else quizzes_chain
            )

            resp = await client.get(f"/api/courses/{course_id}/quizzes")

        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 2

    @pytest.mark.asyncio
    async def test_list_course_concepts(self, client):
        course_id = str(uuid.uuid4())
        lecture_id = str(uuid.uuid4())
        concept_id = str(uuid.uuid4())

        concepts = [
            {
                "id": concept_id,
                "title": "Thermodynamic System",
                "description": "A region of space...",
                "category": "definition",
                "difficulty_estimate": 0.3,
                "lecture_id": lecture_id,
            }
        ]
        lectures = [
            {"id": lecture_id, "title": "Lecture 1", "lecture_number": 1}
        ]
        links = [
            {
                "concept_id": concept_id,
                "assessment_id": str(uuid.uuid4()),
                "relevance_score": 0.85,
            }
        ]
        assessments = [
            {"id": links[0]["assessment_id"], "title": "Midterm 1"}
        ]

        with patch("lecturelink_api.auth.create_client") as mock_create:
            sb = MagicMock()
            mock_create.return_value = sb

            call_count = {"n": 0}

            def table_side_effect(name):
                call_count["n"] += 1
                if name == "courses":
                    return _mock_chain({"id": course_id})
                if name == "concepts":
                    return _mock_chain(concepts)
                if name == "lectures":
                    return _mock_chain(lectures)
                if name == "concept_assessment_links":
                    return _mock_chain(links)
                if name == "assessments":
                    return _mock_chain(assessments)
                return _mock_chain([])

            sb.table.side_effect = table_side_effect

            resp = await client.get(f"/api/courses/{course_id}/concepts")

        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["title"] == "Thermodynamic System"
        assert data[0]["lecture_title"] == "Lecture 1"
        assert len(data[0]["linked_assessments"]) == 1

    @pytest.mark.asyncio
    async def test_cross_user_quiz_access(self, client):
        """Quizzes owned by another user should not be visible."""
        quiz = _sample_quiz(user_id=OTHER_USER_ID)

        with patch("lecturelink_api.auth.create_client") as mock_create:
            sb = MagicMock()
            mock_create.return_value = sb
            # Simulate RLS: user_id filter returns no data
            sb.table.return_value = _mock_chain(None)

            resp = await client.get(f"/api/quizzes/{quiz['id']}")

        assert resp.status_code == 404
