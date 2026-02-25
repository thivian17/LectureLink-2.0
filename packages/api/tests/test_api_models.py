"""Test that all Pydantic models validate correctly."""

from __future__ import annotations

import pytest
from lecturelink_api.models.api_models import (
    ConceptResponse,
    LectureResponse,
    LectureStatusResponse,
    QAResponse,
    QuizQuestionResponse,
    QuizResponse,
    QuizSubmissionResult,
    SearchResult,
)
from pydantic import ValidationError


class TestLectureResponse:
    def test_valid(self):
        lr = LectureResponse(
            id="l1",
            course_id="c1",
            title="Lecture 1",
            processing_status="pending",
            processing_progress=0.5,
            created_at="2026-01-01T00:00:00",
        )
        assert lr.id == "l1"
        assert lr.processing_progress == 0.5

    def test_optional_fields_default_none(self):
        lr = LectureResponse(
            id="l1",
            course_id="c1",
            title="Lecture 1",
            processing_status="pending",
            processing_progress=0.0,
            created_at="2026-01-01T00:00:00",
        )
        assert lr.lecture_number is None
        assert lr.lecture_date is None
        assert lr.processing_stage is None
        assert lr.summary is None
        assert lr.duration_seconds is None

    def test_missing_required_field(self):
        with pytest.raises(ValidationError):
            LectureResponse(id="l1", course_id="c1")


class TestLectureStatusResponse:
    def test_valid(self):
        ls = LectureStatusResponse(
            processing_status="processing", processing_progress=0.3
        )
        assert ls.processing_error is None

    @pytest.mark.parametrize(
        "status", ["pending", "processing", "completed", "error"]
    )
    def test_all_states(self, status):
        ls = LectureStatusResponse(
            processing_status=status, processing_progress=0.0
        )
        assert ls.processing_status == status

    def test_with_error(self):
        ls = LectureStatusResponse(
            processing_status="error",
            processing_progress=0.0,
            processing_error="Out of memory",
        )
        assert ls.processing_error == "Out of memory"


class TestSearchResult:
    def test_valid(self):
        sr = SearchResult(
            chunk_id="c1",
            lecture_id="l1",
            lecture_title="Lec 1",
            content="text",
            score=0.9,
        )
        assert sr.highlight is None
        assert sr.start_time is None

    def test_with_all_optional(self):
        sr = SearchResult(
            chunk_id="c1",
            lecture_id="l1",
            lecture_title="Lec 1",
            content="text",
            score=0.9,
            start_time=10.0,
            end_time=20.0,
            slide_number=3,
            highlight="<b>text</b>",
        )
        assert sr.highlight == "<b>text</b>"
        assert sr.slide_number == 3

    def test_missing_required(self):
        with pytest.raises(ValidationError):
            SearchResult(chunk_id="c1")


class TestQAResponse:
    def test_valid(self):
        qa = QAResponse(
            answer="The answer is 42",
            confidence=0.95,
            source_chunks=[{"chunk_id": "c1", "content": "..."}],
            follow_up_suggestions=["What about 43?"],
        )
        assert qa.confidence == 0.95
        assert len(qa.source_chunks) == 1
        assert len(qa.follow_up_suggestions) == 1

    def test_empty_lists(self):
        qa = QAResponse(
            answer="test",
            confidence=0.9,
            source_chunks=[],
            follow_up_suggestions=[],
        )
        assert qa.source_chunks == []


class TestQuizResponse:
    def test_valid(self):
        qr = QuizResponse(
            id="q1",
            title="Quiz",
            status="ready",
            question_count=5,
            difficulty="medium",
            attempt_count=0,
            created_at="2026-01-15T10:00:00Z",
        )
        assert qr.best_score is None

    def test_with_best_score(self):
        qr = QuizResponse(
            id="q1",
            title="Quiz",
            status="completed",
            question_count=5,
            difficulty="hard",
            best_score=0.8,
            attempt_count=3,
            created_at="2026-01-15T10:00:00Z",
        )
        assert qr.best_score == 0.8


class TestQuizQuestionResponse:
    def test_valid(self):
        qqr = QuizQuestionResponse(
            id="qq1",
            question_index=0,
            question_type="mcq",
            question_text="What is 2+2?",
        )
        assert qqr.options is None

    def test_includes_correct_answer_and_explanation(self):
        """QuizQuestionResponse includes correct_answer and explanation for feedback."""
        qqr = QuizQuestionResponse(
            id="qq1",
            question_index=0,
            question_type="mcq",
            question_text="What is 2+2?",
            correct_answer="4",
            explanation="Basic arithmetic.",
        )
        assert qqr.correct_answer == "4"
        assert qqr.explanation == "Basic arithmetic."

    def test_correct_option_index(self):
        qqr = QuizQuestionResponse(
            id="qq1",
            question_index=0,
            question_type="mcq",
            question_text="What is 2+2?",
            options=["3", "4", "5", "6"],
            correct_answer="4",
            correct_option_index=1,
        )
        assert qqr.correct_option_index == 1

    def test_correct_option_index_defaults_none(self):
        qqr = QuizQuestionResponse(
            id="qq1",
            question_index=0,
            question_type="short_answer",
            question_text="What is 2+2?",
        )
        assert qqr.correct_option_index is None

    def test_with_options(self):
        qqr = QuizQuestionResponse(
            id="qq1",
            question_index=0,
            question_type="mcq",
            question_text="What is 2+2?",
            options=["4", "5", "3", "6"],
        )
        assert len(qqr.options) == 4


class TestQuizSubmissionResult:
    def test_valid(self):
        qsr = QuizSubmissionResult(
            score=0.8, total_questions=5, correct_count=4, results=[]
        )
        assert qsr.score == 0.8

    def test_with_results(self):
        qsr = QuizSubmissionResult(
            score=1.0,
            total_questions=2,
            correct_count=2,
            results=[
                {"question_id": "q1", "is_correct": True},
                {"question_id": "q2", "is_correct": True},
            ],
        )
        assert len(qsr.results) == 2


class TestConceptResponse:
    def test_valid(self):
        cr = ConceptResponse(
            id="c1",
            title="Thermodynamics",
            difficulty_estimate=0.5,
            linked_assessments=[],
            lecture_title="Lecture 1",
        )
        assert cr.description is None
        assert cr.category is None

    def test_with_all_fields(self):
        cr = ConceptResponse(
            id="c1",
            title="Thermodynamics",
            description="Study of heat",
            category="definition",
            difficulty_estimate=0.7,
            linked_assessments=[{"assessment_id": "a1", "title": "Midterm"}],
            lecture_title="Lecture 1",
        )
        assert cr.description == "Study of heat"
        assert len(cr.linked_assessments) == 1
