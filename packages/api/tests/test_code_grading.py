"""Tests for the AI code grading service."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from lecturelink_api.services.code_grading import (
    calculate_weighted_score,
    grade_code_answer,
    is_code_question,
)

# ──────────────────────────────────────────────────────────────────────
# is_code_question
# ──────────────────────────────────────────────────────────────────────


class TestIsCodeQuestion:
    """Tests for is_code_question()."""

    @pytest.mark.parametrize(
        "question_type",
        ["code_writing", "code_fix", "code_explain"],
    )
    def test_returns_true_for_code_types(self, question_type: str):
        assert is_code_question({"question_type": question_type}) is True

    @pytest.mark.parametrize(
        "question_type",
        ["mcq", "true_false", "short_answer"],
    )
    def test_returns_false_for_non_code_types(self, question_type: str):
        assert is_code_question({"question_type": question_type}) is False

    def test_returns_false_for_missing_type(self):
        assert is_code_question({}) is False

    def test_returns_false_for_none_type(self):
        assert is_code_question({"question_type": None}) is False


# ──────────────────────────────────────────────────────────────────────
# calculate_weighted_score
# ──────────────────────────────────────────────────────────────────────


class TestCalculateWeightedScore:
    """Tests for calculate_weighted_score()."""

    def test_basic_weighted_average(self):
        rubric_scores = {
            "correctness": {"score": 0.8, "max_weight": 3, "feedback": "Good"},
            "style": {"score": 1.0, "max_weight": 1, "feedback": "Perfect"},
            "efficiency": {"score": 0.6, "max_weight": 2, "feedback": "Okay"},
        }
        # (0.8*3 + 1.0*1 + 0.6*2) / (3+1+2) = 4.6/6
        result = calculate_weighted_score(rubric_scores)
        assert abs(result - 4.6 / 6) < 1e-9

    def test_empty_rubric(self):
        assert calculate_weighted_score({}) == 0.0

    def test_single_criterion(self):
        rubric_scores = {
            "correctness": {"score": 0.9, "max_weight": 5, "feedback": "Great"},
        }
        assert calculate_weighted_score(rubric_scores) == 0.9

    def test_all_perfect_scores(self):
        rubric_scores = {
            "a": {"score": 1.0, "max_weight": 2, "feedback": ""},
            "b": {"score": 1.0, "max_weight": 3, "feedback": ""},
        }
        assert calculate_weighted_score(rubric_scores) == 1.0

    def test_all_zero_scores(self):
        rubric_scores = {
            "a": {"score": 0.0, "max_weight": 2, "feedback": ""},
            "b": {"score": 0.0, "max_weight": 3, "feedback": ""},
        }
        assert calculate_weighted_score(rubric_scores) == 0.0

    def test_zero_weight_criteria(self):
        rubric_scores = {
            "a": {"score": 0.5, "max_weight": 0, "feedback": ""},
            "b": {"score": 0.5, "max_weight": 0, "feedback": ""},
        }
        assert calculate_weighted_score(rubric_scores) == 0.0


# ──────────────────────────────────────────────────────────────────────
# grade_code_answer
# ──────────────────────────────────────────────────────────────────────

SAMPLE_QUESTION = {
    "question_type": "code_writing",
    "question_text": "Write a function that returns the sum of two numbers.",
    "code_metadata": {
        "language": "python",
        "starter_code": "def add(a, b):\n    pass",
        "reference_solution": "def add(a, b):\n    return a + b",
        "grading_rubric": {
            "correctness": {"max_weight": 3, "description": "Returns the correct sum"},
            "style": {"max_weight": 1, "description": "Clean, readable code"},
        },
        "common_mistakes": [
            "Forgetting to return the value",
            "Using print instead of return",
        ],
    },
}

SAMPLE_GRADING_RESPONSE = {
    "overall_score": 0.85,
    "is_correct": True,
    "rubric_scores": {
        "correctness": {
            "score": 0.9,
            "max_weight": 3,
            "feedback": "Correctly returns the sum of two numbers.",
        },
        "style": {
            "score": 0.7,
            "max_weight": 1,
            "feedback": "Consider adding a docstring.",
        },
    },
    "line_feedback": [
        {"line": 2, "type": "suggestion", "message": "Add a docstring."},
    ],
    "overall_feedback": "Good implementation. Consider adding documentation.",
    "suggested_improvement": None,
    "concepts_demonstrated": ["function definition", "arithmetic operators"],
    "concepts_lacking": ["documentation"],
}


class TestGradeCodeAnswer:
    """Tests for grade_code_answer()."""

    @pytest.mark.asyncio
    async def test_successful_grading(self):
        mock_client = MagicMock()
        mock_client.aio.models.generate_content = AsyncMock(
            return_value=MagicMock(text=json.dumps(SAMPLE_GRADING_RESPONSE))
        )

        with patch(
            "lecturelink_api.services.code_grading._get_client",
            return_value=mock_client,
        ):
            result = await grade_code_answer(
                SAMPLE_QUESTION,
                "def add(a, b):\n    return a + b",
            )

        assert result["is_correct"] is True
        assert "rubric_scores" in result
        assert "correctness" in result["rubric_scores"]
        assert "style" in result["rubric_scores"]
        # overall_score is recalculated from rubric
        expected = (0.9 * 3 + 0.7 * 1) / (3 + 1)
        assert abs(result["overall_score"] - expected) < 1e-9

    @pytest.mark.asyncio
    async def test_grading_with_previous_attempt(self):
        mock_client = MagicMock()
        mock_client.aio.models.generate_content = AsyncMock(
            return_value=MagicMock(text=json.dumps(SAMPLE_GRADING_RESPONSE))
        )

        attempt_context = {
            "attempt_number": 2,
            "hints_used": 1,
            "previous_code": "def add(a, b):\n    print(a + b)",
            "previous_feedback": "You used print instead of return.",
        }

        with patch(
            "lecturelink_api.services.code_grading._get_client",
            return_value=mock_client,
        ):
            result = await grade_code_answer(
                SAMPLE_QUESTION,
                "def add(a, b):\n    return a + b",
                attempt_context,
            )

        assert result["is_correct"] is True
        # Verify the prompt includes previous attempt context
        call_args = mock_client.aio.models.generate_content.call_args
        prompt = call_args.kwargs.get("contents") or call_args[1].get("contents")
        assert "Previous Attempt" in prompt
        assert "Previous Feedback" in prompt

    @pytest.mark.asyncio
    async def test_fallback_on_malformed_json(self):
        mock_client = MagicMock()
        mock_client.aio.models.generate_content = AsyncMock(
            return_value=MagicMock(text="not valid json {{")
        )

        with patch(
            "lecturelink_api.services.code_grading._get_client",
            return_value=mock_client,
        ):
            result = await grade_code_answer(
                SAMPLE_QUESTION,
                "def add(a, b):\n    return a + b",
            )

        assert result["overall_score"] == 0.0
        assert result["is_correct"] is False
        assert result["overall_feedback"] == "Grading failed. Please try again."
        assert "error" in result

    @pytest.mark.asyncio
    async def test_fallback_on_api_error(self):
        mock_client = MagicMock()
        mock_client.aio.models.generate_content = AsyncMock(
            side_effect=RuntimeError("API down")
        )

        with patch(
            "lecturelink_api.services.code_grading._get_client",
            return_value=mock_client,
        ):
            result = await grade_code_answer(
                SAMPLE_QUESTION,
                "def add(a, b):\n    return a + b",
            )

        assert result["overall_score"] == 0.0
        assert result["is_correct"] is False
        assert "error" in result
        assert "API down" in result["error"]

    @pytest.mark.asyncio
    async def test_missing_code_metadata(self):
        """Grading should still work with empty code_metadata."""
        mock_client = MagicMock()
        mock_client.aio.models.generate_content = AsyncMock(
            return_value=MagicMock(text=json.dumps(SAMPLE_GRADING_RESPONSE))
        )

        question = {
            "question_type": "code_writing",
            "question_text": "Write hello world.",
        }

        with patch(
            "lecturelink_api.services.code_grading._get_client",
            return_value=mock_client,
        ):
            result = await grade_code_answer(question, "print('hello world')")

        assert result["is_correct"] is True


# ──────────────────────────────────────────────────────────────────────
# score_quiz integration
# ──────────────────────────────────────────────────────────────────────


class TestScoreQuizCodeRouting:
    """Tests that score_quiz routes code questions to the AI grader."""

    @pytest.mark.asyncio
    async def test_code_question_routed_to_ai_grader(self):
        from lecturelink_api.services.quiz import score_quiz

        code_question = {
            "id": "q1",
            "question_type": "code_writing",
            "question_text": "Write add(a, b).",
            "code_metadata": {
                "reference_solution": "def add(a, b): return a+b",
                "grading_rubric": {},
                "common_mistakes": [],
            },
            "correct_answer": "",
            "explanation": "Basic addition.",
            "user_id": "user-1",
            "options": [],
            "source_chunk_ids": [],
            "concept_id": None,
        }

        grading_result = {
            "overall_score": 0.9,
            "is_correct": True,
            "rubric_scores": {},
            "line_feedback": [],
            "overall_feedback": "Great work!",
            "suggested_improvement": None,
            "concepts_demonstrated": ["functions"],
            "concepts_lacking": [],
        }

        # Build mock supabase chains
        mock_supabase = MagicMock()

        # quiz_questions query chain
        questions_chain = MagicMock()
        questions_chain.select.return_value = questions_chain
        questions_chain.eq.return_value = questions_chain
        questions_chain.order.return_value = questions_chain
        questions_chain.execute.return_value = MagicMock(data=[code_question])

        # quiz_attempts previous attempts chain
        prev_chain = MagicMock()
        prev_chain.select.return_value = prev_chain
        prev_chain.eq.return_value = prev_chain
        prev_chain.order.return_value = prev_chain
        prev_chain.limit.return_value = prev_chain
        prev_chain.execute.return_value = MagicMock(data=[])

        # quiz_attempts insert chain
        insert_chain = MagicMock()
        insert_chain.insert.return_value = insert_chain
        insert_chain.execute.return_value = MagicMock(data=[])

        # quizzes update chain
        update_chain = MagicMock()
        update_chain.select.return_value = update_chain
        update_chain.eq.return_value = update_chain
        update_chain.execute.return_value = MagicMock(
            data=[{"best_score": 0, "attempt_count": 0}]
        )
        update_chain.update.return_value = update_chain

        call_count = {"n": 0}

        def table_side_effect(name):
            call_count["n"] += 1
            if name == "quiz_questions":
                return questions_chain
            if name == "quiz_attempts":
                if call_count["n"] <= 3:
                    return prev_chain
                return insert_chain
            return update_chain

        mock_supabase.table.side_effect = table_side_effect

        with patch(
            "lecturelink_api.services.code_grading.grade_code_answer",
            new_callable=AsyncMock,
            return_value=grading_result,
        ) as mock_grade, patch(
            "lecturelink_api.services.quiz_service.check_answer",
        ) as mock_check:
            result = await score_quiz(
                supabase=mock_supabase,
                quiz_id="quiz-1",
                answers=[
                    {
                        "question_id": "q1",
                        "student_answer": "def add(a, b): return a+b",
                        "time_spent_seconds": 120,
                    }
                ],
            )

        # grade_code_answer was called, check_answer was NOT
        mock_grade.assert_called_once()
        mock_check.assert_not_called()
        assert result["correct_count"] == 1
        assert result["results"][0]["is_correct"] is True
        assert result["results"][0]["code_grading_result"] == grading_result

    @pytest.mark.asyncio
    async def test_mcq_question_uses_check_answer(self):
        from lecturelink_api.services.quiz import score_quiz

        mcq_question = {
            "id": "q2",
            "question_type": "mcq",
            "question_text": "What is 2+2?",
            "correct_answer": "A",
            "explanation": "Basic math.",
            "user_id": "user-1",
            "options": [
                {"label": "A", "text": "4", "is_correct": True},
                {"label": "B", "text": "5", "is_correct": False},
            ],
            "source_chunk_ids": [],
            "concept_id": None,
        }

        mock_supabase = MagicMock()

        questions_chain = MagicMock()
        questions_chain.select.return_value = questions_chain
        questions_chain.eq.return_value = questions_chain
        questions_chain.order.return_value = questions_chain
        questions_chain.execute.return_value = MagicMock(data=[mcq_question])

        insert_chain = MagicMock()
        insert_chain.insert.return_value = insert_chain
        insert_chain.execute.return_value = MagicMock(data=[])

        update_chain = MagicMock()
        update_chain.select.return_value = update_chain
        update_chain.eq.return_value = update_chain
        update_chain.execute.return_value = MagicMock(
            data=[{"best_score": 0, "attempt_count": 0}]
        )
        update_chain.update.return_value = update_chain

        def table_side_effect(name):
            if name == "quiz_questions":
                return questions_chain
            if name == "quiz_attempts":
                return insert_chain
            return update_chain

        mock_supabase.table.side_effect = table_side_effect

        with patch(
            "lecturelink_api.services.code_grading.grade_code_answer",
            new_callable=AsyncMock,
        ) as mock_grade, patch(
            "lecturelink_api.services.quiz_service.check_answer",
            return_value=True,
        ) as mock_check:
            result = await score_quiz(
                supabase=mock_supabase,
                quiz_id="quiz-1",
                answers=[
                    {
                        "question_id": "q2",
                        "student_answer": "A",
                        "time_spent_seconds": 10,
                    }
                ],
            )

        # check_answer was called, grade_code_answer was NOT
        mock_check.assert_called_once()
        mock_grade.assert_not_called()
        assert result["correct_count"] == 1
        assert "code_grading_result" not in result["results"][0]
