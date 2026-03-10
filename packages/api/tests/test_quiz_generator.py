"""Tests for the quiz question generator."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.fixture
def mock_genai():
    """Patch the genai client used by quiz_generator."""
    mock_client = MagicMock()
    mock_client.aio.models.generate_content = AsyncMock()
    with patch(
        "lecturelink_api.services.quiz_generator._get_client",
        return_value=mock_client,
    ):
        yield mock_client


def _make_plan(**overrides):
    """Build a minimal quiz plan for testing."""
    defaults = {
        "concepts": [{
            "concept": {
                "id": "c1", "title": "First Law",
                "category": "concept", "description": "Energy conservation",
            },
            "grounding_chunks": [
                {"chunk_id": "chunk-1", "content": "Energy is conserved"},
            ],
        }],
        "difficulty": "medium",
        "num_questions": 1,
    }
    return {**defaults, **overrides}


class TestGenerateQuestions:
    @pytest.mark.asyncio
    async def test_generates_questions_from_plan(self, mock_genai):
        """Should generate questions matching the plan."""
        from lecturelink_api.services.quiz_generator import generate_questions

        mock_genai.aio.models.generate_content.return_value = MagicMock(
            text=json.dumps([{
                "question_text": "What is the first law?",
                "question_type": "mcq",
                "options": [
                    {"label": "A", "text": "Energy is conserved",
                     "is_correct": True},
                    {"label": "B", "text": "Energy is created",
                     "is_correct": False},
                    {"label": "C", "text": "Energy is destroyed",
                     "is_correct": False},
                    {"label": "D", "text": "Energy is infinite",
                     "is_correct": False},
                ],
                "correct_answer": "A",
                "explanation": "The first law states energy is conserved.",
                "source_chunk_ids": ["chunk-1"],
                "concept_id": "c1",
            }])
        )

        questions = await generate_questions(_make_plan())
        assert len(questions) == 1
        assert questions[0]["question_type"] == "mcq"
        assert len(questions[0]["options"]) == 4

    @pytest.mark.asyncio
    async def test_filters_invalid_mcq(self, mock_genai):
        """MCQ with wrong option count should be filtered."""
        from lecturelink_api.services.quiz_generator import generate_questions

        mock_genai.aio.models.generate_content.return_value = MagicMock(
            text=json.dumps([{
                "question_text": "Bad question",
                "question_type": "mcq",
                "options": [
                    {"label": "A", "text": "yes", "is_correct": True},
                    {"label": "B", "text": "no", "is_correct": False},
                ],
                "correct_answer": "A",
                "explanation": "test",
                "source_chunk_ids": [],
                "concept_id": "c1",
            }])
        )

        questions = await generate_questions(_make_plan())
        assert len(questions) == 0  # Filtered out

    @pytest.mark.asyncio
    async def test_filters_mcq_multiple_correct(self, mock_genai):
        """MCQ with multiple correct answers should be filtered."""
        from lecturelink_api.services.quiz_generator import generate_questions

        mock_genai.aio.models.generate_content.return_value = MagicMock(
            text=json.dumps([{
                "question_text": "Bad question",
                "question_type": "mcq",
                "options": [
                    {"label": "A", "text": "a", "is_correct": True},
                    {"label": "B", "text": "b", "is_correct": True},
                    {"label": "C", "text": "c", "is_correct": False},
                    {"label": "D", "text": "d", "is_correct": False},
                ],
                "correct_answer": "A",
                "explanation": "test",
                "source_chunk_ids": [],
                "concept_id": "c1",
            }])
        )

        questions = await generate_questions(_make_plan())
        assert len(questions) == 0

    @pytest.mark.asyncio
    async def test_filters_missing_fields(self, mock_genai):
        """Questions missing required fields should be filtered."""
        from lecturelink_api.services.quiz_generator import generate_questions

        mock_genai.aio.models.generate_content.return_value = MagicMock(
            text=json.dumps([{
                "question_text": "Missing explanation",
                "question_type": "true_false",
                "correct_answer": "True",
                # Missing explanation
                "source_chunk_ids": [],
                "concept_id": "c1",
            }])
        )

        questions = await generate_questions(_make_plan())
        assert len(questions) == 0

    @pytest.mark.asyncio
    async def test_passes_true_false_validation(self, mock_genai):
        """True/false questions should pass validation."""
        from lecturelink_api.services.quiz_generator import generate_questions

        mock_genai.aio.models.generate_content.return_value = MagicMock(
            text=json.dumps([{
                "question_text": "Energy is conserved.",
                "question_type": "true_false",
                "correct_answer": "True",
                "explanation": "First law says so.",
                "source_chunk_ids": ["chunk-1"],
                "concept_id": "c1",
            }])
        )

        questions = await generate_questions(_make_plan())
        assert len(questions) == 1
        assert questions[0]["question_type"] == "true_false"

    @pytest.mark.asyncio
    async def test_uses_critic_feedback_for_revision(self, mock_genai):
        """On revision pass, critic feedback should be in prompt."""
        from lecturelink_api.services.quiz_generator import generate_questions

        mock_genai.aio.models.generate_content.return_value = MagicMock(
            text=json.dumps([{
                "question_text": "Revised Q",
                "question_type": "true_false",
                "correct_answer": "True",
                "explanation": "Because...",
                "source_chunk_ids": ["c1"],
                "concept_id": "c1",
            }])
        )

        feedback = [
            {"question_index": 0, "verdict": "revise",
             "feedback": "Too vague"},
        ]

        await generate_questions(
            _make_plan(), critic_feedback=feedback
        )

        call_args = mock_genai.aio.models.generate_content.call_args
        prompt_text = call_args.kwargs.get(
            "contents", call_args[1].get("contents", "")
        )
        assert "REVISION" in prompt_text or "Too vague" in prompt_text

    @pytest.mark.asyncio
    async def test_raises_on_invalid_json(self, mock_genai):
        """Should raise on invalid JSON response."""
        from lecturelink_api.services.quiz_generator import generate_questions

        mock_genai.aio.models.generate_content.return_value = MagicMock(
            text="not valid json"
        )

        with pytest.raises(json.JSONDecodeError):
            await generate_questions(_make_plan())
