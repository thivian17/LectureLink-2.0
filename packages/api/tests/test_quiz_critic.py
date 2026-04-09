"""Tests for the quiz question critic."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.fixture
def mock_genai():
    """Patch the genai client used by quiz_critic."""
    mock_client = MagicMock()
    mock_client.aio.models.generate_content = AsyncMock()
    with patch(
        "lecturelink_api.services.quiz_critic._get_client",
        return_value=mock_client,
    ):
        yield mock_client


def _make_plan():
    return {
        "concepts": [{
            "concept": {"id": "c1"},
            "grounding_chunks": [
                {"id": "c1", "content": "Source material"},
            ],
        }],
        "difficulty": "medium",
    }


def _make_question(**overrides):
    defaults = {
        "question_index": 0,
        "question_text": "Test?",
        "question_type": "mcq",
        "concept_id": "c1",
        "correct_answer": "A",
        "explanation": "Because",
    }
    return {**defaults, **overrides}


class TestCritiqueQuestions:
    @pytest.mark.asyncio
    async def test_accepts_faithful_question(self, mock_genai):
        """Question matching source material should be accepted."""
        from lecturelink_api.services.quiz_critic import critique_questions

        mock_genai.aio.models.generate_content.return_value = MagicMock(
            text=json.dumps([{
                "question_index": 0, "verdict": "accept",
                "faithfulness_score": 0.95, "clarity_score": 0.9,
                "difficulty_score": 0.8, "feedback": "Good question",
            }])
        )

        reviews = await critique_questions(
            [_make_question()], _make_plan()
        )
        assert reviews[0]["verdict"] == "accept"

    @pytest.mark.asyncio
    async def test_rejects_low_faithfulness(self, mock_genai):
        """Question with faithfulness < 0.7 should be auto-rejected."""
        from lecturelink_api.services.quiz_critic import critique_questions

        mock_genai.aio.models.generate_content.return_value = MagicMock(
            text=json.dumps([{
                "question_index": 0, "verdict": "revise",
                "faithfulness_score": 0.4, "clarity_score": 0.9,
                "difficulty_score": 0.8, "feedback": "Not in source",
            }])
        )

        reviews = await critique_questions(
            [_make_question()], _make_plan()
        )
        assert reviews[0]["verdict"] == "reject"  # Auto-rejected

    @pytest.mark.asyncio
    async def test_clamps_scores(self, mock_genai):
        """Scores should be clamped to [0.0, 1.0]."""
        from lecturelink_api.services.quiz_critic import critique_questions

        mock_genai.aio.models.generate_content.return_value = MagicMock(
            text=json.dumps([{
                "question_index": 0, "verdict": "accept",
                "faithfulness_score": 1.5, "clarity_score": -0.2,
                "difficulty_score": 0.8, "feedback": "",
            }])
        )

        reviews = await critique_questions(
            [_make_question()], _make_plan()
        )
        assert reviews[0]["faithfulness_score"] == 1.0
        assert reviews[0]["clarity_score"] == 0.0

    @pytest.mark.asyncio
    async def test_normalizes_invalid_verdict(self, mock_genai):
        """Invalid verdict should default to 'revise'."""
        from lecturelink_api.services.quiz_critic import critique_questions

        mock_genai.aio.models.generate_content.return_value = MagicMock(
            text=json.dumps([{
                "question_index": 0, "verdict": "maybe",
                "faithfulness_score": 0.9, "clarity_score": 0.9,
                "difficulty_score": 0.8, "feedback": "",
            }])
        )

        reviews = await critique_questions(
            [_make_question()], _make_plan()
        )
        assert reviews[0]["verdict"] == "revise"

    @pytest.mark.asyncio
    async def test_handles_json_parse_error(self, mock_genai):
        """On parse failure, should accept all questions as fallback."""
        from lecturelink_api.services.quiz_critic import critique_questions

        mock_genai.aio.models.generate_content.return_value = MagicMock(
            text="not valid json"
        )

        reviews = await critique_questions(
            [_make_question()], _make_plan()
        )
        assert len(reviews) == 1
        assert reviews[0]["verdict"] == "accept"  # Fallback

    @pytest.mark.asyncio
    async def test_handles_multiple_questions(self, mock_genai):
        """Should return reviews for all questions."""
        from lecturelink_api.services.quiz_critic import critique_questions

        mock_genai.aio.models.generate_content.return_value = MagicMock(
            text=json.dumps([
                {
                    "question_index": 0, "verdict": "accept",
                    "faithfulness_score": 0.9, "clarity_score": 0.9,
                    "difficulty_score": 0.8,
                },
                {
                    "question_index": 1, "verdict": "revise",
                    "faithfulness_score": 0.8, "clarity_score": 0.6,
                    "difficulty_score": 0.5, "feedback": "Too vague",
                },
            ])
        )

        questions = [
            _make_question(question_index=0),
            _make_question(question_index=1),
        ]
        reviews = await critique_questions(questions, _make_plan())
        assert len(reviews) == 2
        assert reviews[0]["verdict"] == "accept"
        assert reviews[1]["verdict"] == "revise"
