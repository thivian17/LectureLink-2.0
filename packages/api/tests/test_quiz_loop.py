"""Tests for the quiz generation loop orchestrator."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.fixture
def mock_genai():
    """Patch the genai client used by generator and critic."""
    mock = MagicMock()
    mock.aio.models.generate_content = AsyncMock()
    with patch(
        "lecturelink_api.services.quiz_generator._get_client",
        return_value=mock,
    ), patch(
        "lecturelink_api.services.quiz_critic._get_client",
        return_value=mock,
    ):
        yield mock


def _make_plan():
    return {
        "concepts": [
            {
                "concept": {
                    "id": "c1", "title": "T1", "category": "c",
                },
                "grounding_chunks": [
                    {"chunk_id": "ch1", "content": "src"},
                ],
            },
        ],
        "difficulty": "medium",
        "num_questions": 1,
    }


def _gen_response(questions):
    """Create a mock generate_content response."""
    return MagicMock(text=json.dumps(questions))


def _mcq_question(index=0, concept_id="c1"):
    return {
        "question_text": f"Q{index}?",
        "question_type": "mcq",
        "question_index": index,
        "options": [
            {"label": "A", "text": "a", "is_correct": True},
            {"label": "B", "text": "b", "is_correct": False},
            {"label": "C", "text": "c", "is_correct": False},
            {"label": "D", "text": "d", "is_correct": False},
        ],
        "correct_answer": "A",
        "explanation": "...",
        "concept_id": concept_id,
        "source_chunk_ids": ["ch1"],
    }


class TestQuizLoop:
    @pytest.mark.asyncio
    async def test_single_iteration_all_accepted(self, mock_genai):
        """When all questions accepted on first pass, loop runs once."""
        from lecturelink_api.services.quiz_loop import (
            run_quiz_generation_loop,
        )

        mock_genai.aio.models.generate_content.side_effect = [
            # Generator response
            _gen_response([_mcq_question(0)]),
            # Critic response
            _gen_response([{
                "question_index": 0, "verdict": "accept",
                "faithfulness_score": 0.9, "clarity_score": 0.9,
                "difficulty_score": 0.8, "feedback": "Good",
            }]),
        ]

        result = await run_quiz_generation_loop(_make_plan())
        assert len(result) == 1
        assert result[0]["question_text"] == "Q0?"

    @pytest.mark.asyncio
    async def test_revision_loop(self, mock_genai):
        """Questions flagged for revision should be regenerated."""
        from lecturelink_api.services.quiz_loop import (
            run_quiz_generation_loop,
        )

        mock_genai.aio.models.generate_content.side_effect = [
            # Iteration 1: generator
            _gen_response([_mcq_question(0)]),
            # Iteration 1: critic — revise
            _gen_response([{
                "question_index": 0, "verdict": "revise",
                "faithfulness_score": 0.8, "clarity_score": 0.6,
                "difficulty_score": 0.5, "feedback": "Too vague",
            }]),
            # Iteration 2: generator (revision)
            _gen_response([_mcq_question(0)]),
            # Iteration 2: critic — accept
            _gen_response([{
                "question_index": 0, "verdict": "accept",
                "faithfulness_score": 0.95, "clarity_score": 0.9,
                "difficulty_score": 0.8,
            }]),
        ]

        result = await run_quiz_generation_loop(_make_plan())
        assert len(result) == 1
        # Generator was called twice (initial + revision)
        assert mock_genai.aio.models.generate_content.call_count == 4

    @pytest.mark.asyncio
    async def test_rejected_questions_dropped(self, mock_genai):
        """Rejected questions should not appear in results."""
        from lecturelink_api.services.quiz_loop import (
            run_quiz_generation_loop,
        )

        mock_genai.aio.models.generate_content.side_effect = [
            _gen_response([_mcq_question(0)]),
            _gen_response([{
                "question_index": 0, "verdict": "reject",
                "faithfulness_score": 0.3, "clarity_score": 0.5,
                "difficulty_score": 0.5, "feedback": "Not grounded",
            }]),
        ]

        result = await run_quiz_generation_loop(_make_plan())
        assert len(result) == 0

    @pytest.mark.asyncio
    async def test_reindexes_questions(self, mock_genai):
        """Final questions should be re-indexed 0, 1, 2..."""
        from lecturelink_api.services.quiz_loop import (
            run_quiz_generation_loop,
        )

        plan = {
            "concepts": [
                {
                    "concept": {"id": "c1", "title": "T1", "category": "c"},
                    "grounding_chunks": [
                        {"chunk_id": "ch1", "content": "src"},
                    ],
                },
                {
                    "concept": {"id": "c2", "title": "T2", "category": "c"},
                    "grounding_chunks": [
                        {"chunk_id": "ch2", "content": "src"},
                    ],
                },
            ],
            "difficulty": "medium",
            "num_questions": 2,
        }

        mock_genai.aio.models.generate_content.side_effect = [
            _gen_response([
                _mcq_question(0, "c1"),
                {
                    "question_text": "Q1?",
                    "question_type": "true_false",
                    "question_index": 1,
                    "correct_answer": "True",
                    "explanation": "...",
                    "concept_id": "c2",
                    "source_chunk_ids": [],
                },
            ]),
            _gen_response([
                {
                    "question_index": 0, "verdict": "accept",
                    "faithfulness_score": 0.9, "clarity_score": 0.9,
                    "difficulty_score": 0.8,
                },
                {
                    "question_index": 1, "verdict": "accept",
                    "faithfulness_score": 0.9, "clarity_score": 0.9,
                    "difficulty_score": 0.8,
                },
            ]),
        ]

        result = await run_quiz_generation_loop(plan)
        indices = [q["question_index"] for q in result]
        assert indices == list(range(len(result)))

    @pytest.mark.asyncio
    async def test_difficulty_ordering(self, mock_genai):
        """True/false (easy) should come before MCQ (medium)."""
        from lecturelink_api.services.quiz_loop import (
            run_quiz_generation_loop,
        )

        plan = {
            "concepts": [
                {
                    "concept": {"id": "c1", "title": "T1", "category": "c"},
                    "grounding_chunks": [
                        {"chunk_id": "ch1", "content": "src"},
                    ],
                },
                {
                    "concept": {"id": "c2", "title": "T2", "category": "c"},
                    "grounding_chunks": [
                        {"chunk_id": "ch2", "content": "src"},
                    ],
                },
            ],
            "difficulty": "medium",
            "num_questions": 2,
        }

        mock_genai.aio.models.generate_content.side_effect = [
            _gen_response([
                _mcq_question(0, "c1"),  # MCQ → medium
                {
                    "question_text": "TF?",
                    "question_type": "true_false",
                    "question_index": 1,
                    "correct_answer": "True",
                    "explanation": "...",
                    "concept_id": "c2",
                    "source_chunk_ids": [],
                },
            ]),
            _gen_response([
                {"question_index": 0, "verdict": "accept",
                 "faithfulness_score": 0.9, "clarity_score": 0.9,
                 "difficulty_score": 0.8},
                {"question_index": 1, "verdict": "accept",
                 "faithfulness_score": 0.9, "clarity_score": 0.9,
                 "difficulty_score": 0.8},
            ]),
        ]

        result = await run_quiz_generation_loop(plan)
        # true_false (easy) should come before mcq (medium)
        assert result[0]["question_type"] == "true_false"
        assert result[1]["question_type"] == "mcq"
