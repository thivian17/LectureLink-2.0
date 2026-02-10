"""Tests for quiz service (storage + scoring)."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest


@pytest.fixture
def supabase_mock():
    """Mock Supabase client."""
    client = MagicMock()
    client.table.return_value.insert.return_value.execute.return_value = MagicMock(
        data=[{"id": "quiz-1", "status": "ready"}]
    )
    client.table.return_value.select.return_value.eq.return_value.execute.return_value = (
        MagicMock(data=[])
    )
    client.table.return_value.select.return_value.eq.return_value.order.return_value.execute.return_value = (
        MagicMock(data=[])
    )
    client.table.return_value.update.return_value.eq.return_value.execute.return_value = (
        MagicMock(data=[])
    )
    return client


class TestSaveQuiz:
    def test_creates_quiz_and_questions(self, supabase_mock):
        """Should create quiz record and insert all questions."""
        from lecturelink_api.services.quiz_service import save_quiz

        questions = [
            {
                "question_index": 0, "question_text": "Q1?",
                "question_type": "mcq", "options": [],
                "correct_answer": "A", "explanation": "...",
                "source_chunk_ids": ["c1"], "concept_id": "c1",
            },
            {
                "question_index": 1, "question_text": "Q2?",
                "question_type": "true_false",
                "correct_answer": "True", "explanation": "...",
                "source_chunk_ids": ["c2"], "concept_id": "c2",
            },
        ]

        result = save_quiz(
            supabase_mock, "course-1", "user-1", "Test Quiz", questions,
        )
        assert result["id"] == "quiz-1"
        # insert called for quiz + questions
        assert supabase_mock.table.return_value.insert.call_count == 2

    def test_handles_empty_questions(self, supabase_mock):
        """Should create quiz but skip question insert."""
        from lecturelink_api.services.quiz_service import save_quiz

        result = save_quiz(
            supabase_mock, "course-1", "user-1", "Empty Quiz", [],
        )
        assert result["id"] == "quiz-1"
        # Only quiz insert, no question insert
        assert supabase_mock.table.return_value.insert.call_count == 1


class TestGetQuizWithQuestions:
    def test_returns_quiz_with_questions(self, supabase_mock):
        """Should return quiz dict with nested questions."""
        from lecturelink_api.services.quiz_service import (
            get_quiz_with_questions,
        )

        quiz_chain = MagicMock()
        quiz_chain.select.return_value = quiz_chain
        quiz_chain.eq.return_value = quiz_chain
        quiz_chain.execute.return_value = MagicMock(data=[
            {"id": "quiz-1", "status": "ready"},
        ])

        questions_chain = MagicMock()
        questions_chain.select.return_value = questions_chain
        questions_chain.eq.return_value = questions_chain
        questions_chain.order.return_value = questions_chain
        questions_chain.execute.return_value = MagicMock(data=[
            {"id": "q1", "question_index": 0, "question_text": "Q1?"},
        ])

        call_count = [0]

        def table_side_effect(name):
            nonlocal call_count
            call_count[0] += 1
            if call_count[0] == 1:
                return quiz_chain
            return questions_chain

        supabase_mock.table.side_effect = table_side_effect

        result = get_quiz_with_questions(supabase_mock, "quiz-1")
        assert result is not None
        assert result["id"] == "quiz-1"
        assert len(result["questions"]) == 1

    def test_returns_none_if_not_found(self, supabase_mock):
        """Should return None when quiz doesn't exist."""
        from lecturelink_api.services.quiz_service import (
            get_quiz_with_questions,
        )

        chain = MagicMock()
        chain.select.return_value = chain
        chain.eq.return_value = chain
        chain.execute.return_value = MagicMock(data=[])
        supabase_mock.table.return_value = chain

        result = get_quiz_with_questions(supabase_mock, "nonexistent")
        assert result is None


class TestScoreQuiz:
    def test_scores_correctly(self, supabase_mock):
        """Should calculate correct score."""
        from lecturelink_api.services.quiz_service import score_quiz

        quiz_chain = MagicMock()
        quiz_chain.select.return_value = quiz_chain
        quiz_chain.eq.return_value = quiz_chain
        quiz_chain.execute.return_value = MagicMock(data=[
            {"id": "quiz-1", "status": "ready"},
        ])

        questions_chain = MagicMock()
        questions_chain.select.return_value = questions_chain
        questions_chain.eq.return_value = questions_chain
        questions_chain.order.return_value = questions_chain
        questions_chain.execute.return_value = MagicMock(data=[
            {
                "id": "q1", "question_type": "mcq",
                "correct_answer": "A", "explanation": "...",
                "options": [
                    {"label": "A", "text": "yes", "is_correct": True},
                ],
                "source_chunk_ids": [], "concept_id": "c1",
            },
            {
                "id": "q2", "question_type": "true_false",
                "correct_answer": "True", "explanation": "...",
                "options": None,
                "source_chunk_ids": [], "concept_id": "c2",
            },
        ])

        update_chain = MagicMock()
        update_chain.update.return_value = update_chain
        update_chain.eq.return_value = update_chain
        update_chain.execute.return_value = MagicMock(data=[])

        call_count = [0]

        def table_side_effect(name):
            nonlocal call_count
            call_count[0] += 1
            if call_count[0] == 1:
                return quiz_chain
            elif call_count[0] == 2:
                return questions_chain
            return update_chain

        supabase_mock.table.side_effect = table_side_effect

        answers = [
            {"question_id": "q1", "student_answer": "A"},
            {"question_id": "q2", "student_answer": "False"},
        ]

        result = score_quiz(supabase_mock, "quiz-1", "user-1", answers)
        assert result["total_questions"] == 2
        assert result["correct_count"] == 1
        assert result["score"] == 0.5


class TestCheckAnswer:
    def test_mcq_correct_by_label(self):
        from lecturelink_api.services.quiz_service import check_answer

        q = {
            "question_type": "mcq", "correct_answer": "B",
            "options": [
                {"label": "A", "text": "wrong", "is_correct": False},
                {"label": "B", "text": "right", "is_correct": True},
            ],
        }
        assert check_answer(q, "B") is True
        assert check_answer(q, "A") is False

    def test_mcq_correct_by_text(self):
        from lecturelink_api.services.quiz_service import check_answer

        q = {
            "question_type": "mcq", "correct_answer": "B",
            "options": [
                {"label": "A", "text": "wrong", "is_correct": False},
                {"label": "B", "text": "right", "is_correct": True},
            ],
        }
        assert check_answer(q, "right") is True

    def test_mcq_case_insensitive_label(self):
        from lecturelink_api.services.quiz_service import check_answer

        q = {
            "question_type": "mcq", "correct_answer": "B",
            "options": [
                {"label": "B", "text": "right", "is_correct": True},
            ],
        }
        assert check_answer(q, "b") is True

    def test_true_false_true(self):
        from lecturelink_api.services.quiz_service import check_answer

        q = {"question_type": "true_false", "correct_answer": "True"}
        assert check_answer(q, "True") is True
        assert check_answer(q, "true") is True
        assert check_answer(q, "t") is True
        assert check_answer(q, "False") is False

    def test_true_false_false(self):
        from lecturelink_api.services.quiz_service import check_answer

        q = {"question_type": "true_false", "correct_answer": "False"}
        assert check_answer(q, "False") is True
        assert check_answer(q, "false") is True
        assert check_answer(q, "f") is True
        assert check_answer(q, "True") is False

    def test_short_answer_case_insensitive(self):
        from lecturelink_api.services.quiz_service import check_answer

        q = {"question_type": "short_answer", "correct_answer": "Entropy"}
        assert check_answer(q, "entropy") is True
        assert check_answer(q, "  Entropy  ") is True
        assert check_answer(q, "enthalpy") is False

    def test_unknown_type_returns_false(self):
        from lecturelink_api.services.quiz_service import check_answer

        q = {"question_type": "essay", "correct_answer": "anything"}
        assert check_answer(q, "anything") is False
