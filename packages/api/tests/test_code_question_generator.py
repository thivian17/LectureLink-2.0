"""Tests for coding question generation and hint endpoint."""

from __future__ import annotations

import json
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


def _make_plan(**overrides):
    """Build a minimal quiz plan for testing coding generation."""
    defaults = {
        "concepts": [{
            "concept": {
                "id": "c1", "title": "Binary Search",
                "category": "algorithm",
                "description": "Efficient search in sorted arrays",
            },
            "grounding_chunks": [
                {
                    "id": "chunk-1",
                    "content": "Binary search divides the search interval in half",
                },
            ],
        }],
        "difficulty": "medium",
        "num_questions": 1,
        "mastery": 0.5,
    }
    return {**defaults, **overrides}


def _sample_coding_question():
    """A valid coding question as Gemini would return."""
    ref_solution = (
        "def binary_search(arr, target):\n"
        "    lo, hi = 0, len(arr) - 1\n"
        "    while lo <= hi:\n"
        "        mid = (lo + hi) // 2\n"
        "        if arr[mid] == target:\n"
        "            return mid\n"
        "        elif arr[mid] < target:\n"
        "            lo = mid + 1\n"
        "        else:\n"
        "            hi = mid - 1\n"
        "    return -1"
    )
    return {
        "question_text": "Implement binary search on a sorted list.",
        "question_type": "code_writing",
        "correct_answer": ref_solution,
        "explanation": "Binary search divides the interval in half each step.",
        "source_chunk_ids": ["chunk-1"],
        "concept_id": "c1",
        "difficulty": 0.5,
        "code_metadata": {
            "language": "python",
            "starter_code": (
                "def binary_search(arr, target):\n"
                "    # Your code here\n"
                "    pass"
            ),
            "reference_solution": ref_solution,
            "grading_rubric": {
                "correctness": {
                    "weight": 40,
                    "criteria": "Returns correct index",
                },
                "concept_understanding": {
                    "weight": 30,
                    "criteria": "Uses divide-and-conquer",
                },
                "code_quality": {
                    "weight": 20,
                    "criteria": "Clean code",
                },
                "edge_cases": {
                    "weight": 10,
                    "criteria": "Handles empty array",
                },
            },
            "hints": [
                "Think about dividing the array",
                "Compare middle element",
                "Adjust bounds",
            ],
            "example_inputs_outputs": [
                {
                    "input": "binary_search([1,2,3,4,5], 3)",
                    "expected": "2",
                },
            ],
            "common_mistakes": [
                "Off-by-one in bounds",
                "Infinite loop with wrong midpoint",
            ],
            "max_lines": 20,
            "time_limit_minutes": 10,
            "related_lecture_concepts": ["Binary Search"],
        },
    }


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_genai():
    """Patch the genai client used by code_question_generator."""
    mock_client = MagicMock()
    mock_client.aio.models.generate_content = AsyncMock()
    with patch(
        "lecturelink_api.services.code_question_generator._get_client",
        return_value=mock_client,
    ):
        yield mock_client


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
# detect_coding_relevance tests
# ---------------------------------------------------------------------------


class TestDetectCodingRelevance:
    def test_returns_true_for_homework(self):
        from lecturelink_api.services.code_question_generator import (
            detect_coding_relevance,
        )

        assert detect_coding_relevance({"type": "homework", "topics": []}) is True

    def test_returns_true_for_project(self):
        from lecturelink_api.services.code_question_generator import (
            detect_coding_relevance,
        )

        assert detect_coding_relevance({"type": "project", "topics": []}) is True

    def test_returns_true_for_lab(self):
        from lecturelink_api.services.code_question_generator import (
            detect_coding_relevance,
        )

        assert detect_coding_relevance({"type": "lab", "topics": []}) is True

    def test_returns_true_for_coding_topics(self):
        from lecturelink_api.services.code_question_generator import (
            detect_coding_relevance,
        )

        assert detect_coding_relevance({
            "type": "exam",
            "topics": ["Implement a sorting algorithm"],
        }) is True

    def test_returns_true_for_python_topic(self):
        from lecturelink_api.services.code_question_generator import (
            detect_coding_relevance,
        )

        assert detect_coding_relevance({
            "type": "exam",
            "topics": ["Python basics"],
        }) is True

    def test_returns_false_for_exam_without_coding(self):
        from lecturelink_api.services.code_question_generator import (
            detect_coding_relevance,
        )

        assert detect_coding_relevance({
            "type": "exam",
            "topics": ["History of computing", "Ethics"],
        }) is False

    def test_returns_false_for_exam_no_topics(self):
        from lecturelink_api.services.code_question_generator import (
            detect_coding_relevance,
        )

        assert detect_coding_relevance({"type": "exam", "topics": []}) is False


# ---------------------------------------------------------------------------
# get_default_rubric tests
# ---------------------------------------------------------------------------


class TestGetDefaultRubric:
    def test_code_writing_rubric(self):
        from lecturelink_api.services.code_question_generator import (
            get_default_rubric,
        )

        rubric = get_default_rubric("code_writing")
        assert "correctness" in rubric
        assert "concept_understanding" in rubric
        assert "code_quality" in rubric
        assert "edge_cases" in rubric
        total = sum(v["weight"] for v in rubric.values())
        assert total == 100

    def test_code_fix_rubric(self):
        from lecturelink_api.services.code_question_generator import (
            get_default_rubric,
        )

        rubric = get_default_rubric("code_fix")
        assert "bug_identification" in rubric
        assert "fix_correctness" in rubric
        assert "explanation" in rubric
        assert "code_quality" in rubric
        total = sum(v["weight"] for v in rubric.values())
        assert total == 100

    def test_code_explain_rubric(self):
        from lecturelink_api.services.code_question_generator import (
            get_default_rubric,
        )

        rubric = get_default_rubric("code_explain")
        assert "output_correctness" in rubric
        assert "trace_accuracy" in rubric
        assert "concept_identification" in rubric
        assert "clarity" in rubric
        total = sum(v["weight"] for v in rubric.values())
        assert total == 100

    def test_unknown_type_falls_back(self):
        from lecturelink_api.services.code_question_generator import (
            get_default_rubric,
        )

        rubric = get_default_rubric("unknown_type")
        # Falls back to code_writing rubric
        assert "correctness" in rubric


# ---------------------------------------------------------------------------
# generate_coding_questions tests
# ---------------------------------------------------------------------------


class TestGenerateCodingQuestions:
    @pytest.mark.asyncio
    async def test_generates_coding_questions(self, mock_genai):
        from lecturelink_api.services.code_question_generator import (
            generate_coding_questions,
        )

        mock_genai.aio.models.generate_content.return_value = MagicMock(
            text=json.dumps([_sample_coding_question()])
        )

        questions = await generate_coding_questions(_make_plan())
        assert len(questions) == 1
        q = questions[0]
        assert q["question_type"] == "code_writing"
        assert "code_metadata" in q
        assert q["code_metadata"]["language"] == "python"
        assert len(q["code_metadata"]["hints"]) == 3
        assert q["code_metadata"]["grading_rubric"]["correctness"]["weight"] == 40

    @pytest.mark.asyncio
    async def test_sets_default_language(self, mock_genai):
        """Language from parameter should be used as default in metadata."""
        from lecturelink_api.services.code_question_generator import (
            generate_coding_questions,
        )

        q_data = _sample_coding_question()
        del q_data["code_metadata"]["language"]  # Remove explicit language

        mock_genai.aio.models.generate_content.return_value = MagicMock(
            text=json.dumps([q_data])
        )

        questions = await generate_coding_questions(
            _make_plan(), language="javascript"
        )
        assert questions[0]["code_metadata"]["language"] == "javascript"

    @pytest.mark.asyncio
    async def test_fills_missing_metadata_defaults(self, mock_genai):
        """Missing code_metadata fields should be filled with defaults."""
        from lecturelink_api.services.code_question_generator import (
            generate_coding_questions,
        )

        q_data = {
            "question_text": "Fix this code",
            "question_type": "code_fix",
            "correct_answer": "fixed code",
            "explanation": "The bug was...",
            "source_chunk_ids": ["chunk-1"],
            "concept_id": "c1",
            "difficulty": 0.4,
            "code_metadata": {},  # Empty metadata — should get defaults
        }

        mock_genai.aio.models.generate_content.return_value = MagicMock(
            text=json.dumps([q_data])
        )

        questions = await generate_coding_questions(_make_plan())
        assert len(questions) == 1
        meta = questions[0]["code_metadata"]
        assert meta["language"] == "python"
        assert meta["starter_code"] == ""
        assert meta["reference_solution"] == "fixed code"
        assert "bug_identification" in meta["grading_rubric"]  # code_fix rubric
        assert meta["hints"] == []
        assert meta["max_lines"] == 30

    @pytest.mark.asyncio
    async def test_filters_invalid_question_type(self, mock_genai):
        """Non-coding question types should be filtered out."""
        from lecturelink_api.services.code_question_generator import (
            generate_coding_questions,
        )

        q_data = _sample_coding_question()
        q_data["question_type"] = "mcq"  # Invalid for coding generator

        mock_genai.aio.models.generate_content.return_value = MagicMock(
            text=json.dumps([q_data])
        )

        questions = await generate_coding_questions(_make_plan())
        assert len(questions) == 0

    @pytest.mark.asyncio
    async def test_filters_missing_fields(self, mock_genai):
        """Questions missing required fields should be filtered."""
        from lecturelink_api.services.code_question_generator import (
            generate_coding_questions,
        )

        mock_genai.aio.models.generate_content.return_value = MagicMock(
            text=json.dumps([{
                "question_text": "Incomplete question",
                "question_type": "code_writing",
                # Missing correct_answer and explanation
            }])
        )

        questions = await generate_coding_questions(_make_plan())
        assert len(questions) == 0

    @pytest.mark.asyncio
    async def test_uses_critic_feedback(self, mock_genai):
        """Critic feedback should appear in the prompt."""
        from lecturelink_api.services.code_question_generator import (
            generate_coding_questions,
        )

        mock_genai.aio.models.generate_content.return_value = MagicMock(
            text=json.dumps([_sample_coding_question()])
        )

        feedback = [
            {"question_index": 0, "verdict": "revise", "feedback": "Too easy"},
        ]

        await generate_coding_questions(_make_plan(), critic_feedback=feedback)

        call_args = mock_genai.aio.models.generate_content.call_args
        prompt_text = call_args.kwargs.get(
            "contents", call_args[1].get("contents", "")
        )
        assert "REVISION" in prompt_text or "Too easy" in prompt_text

    @pytest.mark.asyncio
    async def test_raises_on_invalid_json(self, mock_genai):
        """Should raise on invalid JSON response."""
        from lecturelink_api.services.code_question_generator import (
            generate_coding_questions,
        )

        mock_genai.aio.models.generate_content.return_value = MagicMock(
            text="not valid json"
        )

        with pytest.raises(json.JSONDecodeError):
            await generate_coding_questions(_make_plan())

    @pytest.mark.asyncio
    async def test_includes_mastery_in_prompt(self, mock_genai):
        """Mastery level should be passed to Gemini."""
        from lecturelink_api.services.code_question_generator import (
            generate_coding_questions,
        )

        mock_genai.aio.models.generate_content.return_value = MagicMock(
            text=json.dumps([_sample_coding_question()])
        )

        plan = _make_plan(mastery=0.9)
        await generate_coding_questions(plan)

        call_args = mock_genai.aio.models.generate_content.call_args
        prompt_text = call_args.kwargs.get(
            "contents", call_args[1].get("contents", "")
        )
        assert "0.9" in prompt_text


# ---------------------------------------------------------------------------
# Hint endpoint tests
# ---------------------------------------------------------------------------


class TestHintEndpoint:
    @pytest.mark.asyncio
    async def test_returns_hint(self, client):
        quiz_id = str(uuid.uuid4())
        question_id = str(uuid.uuid4())

        with patch("lecturelink_api.auth.create_client") as mock_create:
            sb = MagicMock()
            mock_create.return_value = sb

            quiz_chain = _mock_chain([{"id": quiz_id}])
            question_chain = _mock_chain([{
                "id": question_id,
                "code_metadata": {
                    "hints": ["Hint A", "Hint B", "Hint C"],
                },
            }])

            sb.table.side_effect = lambda name: (
                quiz_chain if name == "quizzes" else question_chain
            )

            resp = await client.post(
                f"/api/quizzes/{quiz_id}/questions/{question_id}/hint",
                json={"hint_index": 0},
            )

        assert resp.status_code == 200
        data = resp.json()
        assert data["hint"] == "Hint A"
        assert data["hints_remaining"] == 2
        assert data["hint_index"] == 0

    @pytest.mark.asyncio
    async def test_returns_last_hint(self, client):
        quiz_id = str(uuid.uuid4())
        question_id = str(uuid.uuid4())

        with patch("lecturelink_api.auth.create_client") as mock_create:
            sb = MagicMock()
            mock_create.return_value = sb

            quiz_chain = _mock_chain([{"id": quiz_id}])
            question_chain = _mock_chain([{
                "id": question_id,
                "code_metadata": {
                    "hints": ["Hint A", "Hint B", "Hint C"],
                },
            }])

            sb.table.side_effect = lambda name: (
                quiz_chain if name == "quizzes" else question_chain
            )

            resp = await client.post(
                f"/api/quizzes/{quiz_id}/questions/{question_id}/hint",
                json={"hint_index": 2},
            )

        assert resp.status_code == 200
        data = resp.json()
        assert data["hint"] == "Hint C"
        assert data["hints_remaining"] == 0

    @pytest.mark.asyncio
    async def test_hint_index_out_of_bounds(self, client):
        quiz_id = str(uuid.uuid4())
        question_id = str(uuid.uuid4())

        with patch("lecturelink_api.auth.create_client") as mock_create:
            sb = MagicMock()
            mock_create.return_value = sb

            quiz_chain = _mock_chain([{"id": quiz_id}])
            question_chain = _mock_chain([{
                "id": question_id,
                "code_metadata": {
                    "hints": ["Hint A"],
                },
            }])

            sb.table.side_effect = lambda name: (
                quiz_chain if name == "quizzes" else question_chain
            )

            resp = await client.post(
                f"/api/quizzes/{quiz_id}/questions/{question_id}/hint",
                json={"hint_index": 5},
            )

        assert resp.status_code == 400

    @pytest.mark.asyncio
    async def test_no_hints_available(self, client):
        quiz_id = str(uuid.uuid4())
        question_id = str(uuid.uuid4())

        with patch("lecturelink_api.auth.create_client") as mock_create:
            sb = MagicMock()
            mock_create.return_value = sb

            quiz_chain = _mock_chain([{"id": quiz_id}])
            question_chain = _mock_chain([{
                "id": question_id,
                "code_metadata": None,
            }])

            sb.table.side_effect = lambda name: (
                quiz_chain if name == "quizzes" else question_chain
            )

            resp = await client.post(
                f"/api/quizzes/{quiz_id}/questions/{question_id}/hint",
                json={"hint_index": 0},
            )

        assert resp.status_code == 400

    @pytest.mark.asyncio
    async def test_question_not_found(self, client):
        quiz_id = str(uuid.uuid4())
        question_id = str(uuid.uuid4())

        with patch("lecturelink_api.auth.create_client") as mock_create:
            sb = MagicMock()
            mock_create.return_value = sb

            quiz_chain = _mock_chain([{"id": quiz_id}])
            question_chain = _mock_chain([])  # No question found

            sb.table.side_effect = lambda name: (
                quiz_chain if name == "quizzes" else question_chain
            )

            resp = await client.post(
                f"/api/quizzes/{quiz_id}/questions/{question_id}/hint",
                json={"hint_index": 0},
            )

        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_quiz_not_found(self, client):
        quiz_id = str(uuid.uuid4())
        question_id = str(uuid.uuid4())

        with patch("lecturelink_api.auth.create_client") as mock_create:
            sb = MagicMock()
            mock_create.return_value = sb

            sb.table.return_value = _mock_chain([])  # No quiz found

            resp = await client.post(
                f"/api/quizzes/{quiz_id}/questions/{question_id}/hint",
                json={"hint_index": 0},
            )

        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_empty_hints_array(self, client):
        quiz_id = str(uuid.uuid4())
        question_id = str(uuid.uuid4())

        with patch("lecturelink_api.auth.create_client") as mock_create:
            sb = MagicMock()
            mock_create.return_value = sb

            quiz_chain = _mock_chain([{"id": quiz_id}])
            question_chain = _mock_chain([{
                "id": question_id,
                "code_metadata": {"hints": []},
            }])

            sb.table.side_effect = lambda name: (
                quiz_chain if name == "quizzes" else question_chain
            )

            resp = await client.post(
                f"/api/quizzes/{quiz_id}/questions/{question_id}/hint",
                json={"hint_index": 0},
            )

        assert resp.status_code == 400
