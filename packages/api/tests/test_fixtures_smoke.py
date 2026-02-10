"""Smoke test that all fixtures work."""

from __future__ import annotations

import numpy as np

from fixtures.mock_responses import (
    MOCK_CONCEPTS,
    MOCK_QUIZ_QUESTIONS,
    MOCK_RAG_ANSWER,
    MOCK_SLIDE_ANALYSIS,
    MOCK_TRANSCRIPT,
)


class TestFixtures:
    def test_test_user(self, test_user):
        assert "id" in test_user
        assert "email" in test_user

    def test_test_course(self, test_course):
        assert "id" in test_course
        assert "user_id" in test_course
        assert "name" in test_course

    def test_test_lecture(self, test_lecture):
        assert "id" in test_lecture
        assert "course_id" in test_lecture
        assert test_lecture["processing_status"] == "completed"

    def test_test_chunks_count(self, test_chunks):
        assert len(test_chunks) == 20

    def test_test_chunks_embedding_dim(self, test_chunks):
        for chunk in test_chunks:
            assert len(chunk["embedding"]) == 768

    def test_test_chunks_normalized(self, test_chunks):
        for chunk in test_chunks[:3]:
            norm = np.linalg.norm(chunk["embedding"])
            assert abs(norm - 1.0) < 1e-5, f"Embedding not normalized: norm={norm}"

    def test_test_concepts_count(self, test_concepts):
        assert len(test_concepts) == 5

    def test_test_concepts_fields(self, test_concepts):
        for concept in test_concepts:
            assert "title" in concept
            assert "description" in concept
            assert "category" in concept
            assert "difficulty_estimate" in concept
            assert "embedding" in concept

    def test_mock_supabase_table(self, mock_supabase):
        assert mock_supabase.table is not None

    def test_mock_gemini_client(self, mock_gemini_client):
        assert mock_gemini_client.models.embed_content is not None
        assert mock_gemini_client.models.generate_content is not None


class TestMockResponses:
    def test_transcript_count(self):
        assert len(MOCK_TRANSCRIPT) >= 5

    def test_slide_analysis_count(self):
        assert len(MOCK_SLIDE_ANALYSIS) >= 3

    def test_concepts_count(self):
        assert len(MOCK_CONCEPTS) >= 3

    def test_rag_answer_fields(self):
        assert "answer" in MOCK_RAG_ANSWER
        assert "confidence" in MOCK_RAG_ANSWER
        assert "source_chunks" in MOCK_RAG_ANSWER

    def test_quiz_questions(self):
        assert len(MOCK_QUIZ_QUESTIONS) >= 2
        assert MOCK_QUIZ_QUESTIONS[0]["question_type"] in ("mcq", "true_false", "short_answer")
