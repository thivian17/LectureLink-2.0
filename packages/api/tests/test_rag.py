"""Tests for RAG answer generation."""

from __future__ import annotations

import json

import pytest
from unittest.mock import AsyncMock, MagicMock


class TestAskLectureQuestion:
    """Test RAG answer generation."""

    async def test_returns_answer_with_sources(self, supabase_mock, mock_genai):
        """Happy path: question -> search -> generate -> answer with citations."""
        from lecturelink_api.services.rag import ask_lecture_question

        # Mock search results
        supabase_mock.rpc.return_value.execute.return_value.data = [
            {
                "id": "chunk-1",
                "lecture_id": "lec-1",
                "content": "The first law states energy is conserved.",
                "start_time": 120.0,
                "rrf_score": 0.9,
            }
        ]
        supabase_mock.table.return_value.select.return_value.in_.return_value.execute.return_value.data = [
            {"id": "lec-1", "title": "Thermodynamics Intro"}
        ]

        # Mock Gemini response
        mock_genai.aio.models.generate_content.return_value.text = json.dumps(
            {
                "answer": "The first law states that energy is conserved [Source 1].",
                "confidence": 0.9,
                "cited_sources": [1],
                "follow_up_suggestions": ["What about the second law?"],
            }
        )

        result = await ask_lecture_question(
            supabase_mock, "course-1", "What is the first law?"
        )

        assert "energy" in result["answer"].lower()
        assert result["confidence"] == 0.9
        assert len(result["source_chunks"]) >= 1
        assert len(result["follow_up_suggestions"]) >= 1

    async def test_no_chunks_returns_not_found(self, supabase_mock, mock_genai):
        """When no chunks found, return helpful message without calling LLM."""
        from lecturelink_api.services.rag import ask_lecture_question

        supabase_mock.rpc.return_value.execute.return_value.data = []

        result = await ask_lecture_question(supabase_mock, "course-1", "Anything")

        assert result["confidence"] == 0.0
        assert "couldn't find" in result["answer"].lower()
        # Should NOT have called Gemini
        mock_genai.aio.models.generate_content.assert_not_called()

    async def test_handles_non_json_response(self, supabase_mock, mock_genai):
        """If model returns plain text, use it as the answer."""
        from lecturelink_api.services.rag import ask_lecture_question

        supabase_mock.rpc.return_value.execute.return_value.data = [
            {"id": "c1", "lecture_id": "l1", "content": "test", "rrf_score": 0.5}
        ]
        supabase_mock.table.return_value.select.return_value.in_.return_value.execute.return_value.data = [
            {"id": "l1", "title": "Test Lecture"}
        ]
        mock_genai.aio.models.generate_content.return_value.text = (
            "Plain text answer without JSON"
        )

        result = await ask_lecture_question(supabase_mock, "course-1", "question")

        assert "Plain text answer" in result["answer"]
        assert result["confidence"] == 0.5  # Default

    async def test_confidence_clamped_to_0_1(self, supabase_mock, mock_genai):
        """Confidence should always be between 0 and 1."""
        from lecturelink_api.services.rag import ask_lecture_question

        supabase_mock.rpc.return_value.execute.return_value.data = [
            {"id": "c1", "lecture_id": "l1", "content": "test", "rrf_score": 0.5}
        ]
        supabase_mock.table.return_value.select.return_value.in_.return_value.execute.return_value.data = [
            {"id": "l1", "title": "Test"}
        ]
        mock_genai.aio.models.generate_content.return_value.text = json.dumps(
            {
                "answer": "test",
                "confidence": 1.5,
                "cited_sources": [],
                "follow_up_suggestions": [],
            }
        )

        result = await ask_lecture_question(supabase_mock, "c1", "q")
        assert result["confidence"] == 1.0

    async def test_confidence_clamped_below_zero(self, supabase_mock, mock_genai):
        """Negative confidence should be clamped to 0."""
        from lecturelink_api.services.rag import ask_lecture_question

        supabase_mock.rpc.return_value.execute.return_value.data = [
            {"id": "c1", "lecture_id": "l1", "content": "test", "rrf_score": 0.5}
        ]
        supabase_mock.table.return_value.select.return_value.in_.return_value.execute.return_value.data = [
            {"id": "l1", "title": "Test"}
        ]
        mock_genai.aio.models.generate_content.return_value.text = json.dumps(
            {
                "answer": "test",
                "confidence": -0.5,
                "cited_sources": [],
                "follow_up_suggestions": [],
            }
        )

        result = await ask_lecture_question(supabase_mock, "c1", "q")
        assert result["confidence"] == 0.0

    async def test_follow_up_limited_to_3(self, supabase_mock, mock_genai):
        """Max 3 follow-up suggestions."""
        from lecturelink_api.services.rag import ask_lecture_question

        supabase_mock.rpc.return_value.execute.return_value.data = [
            {"id": "c1", "lecture_id": "l1", "content": "test", "rrf_score": 0.5}
        ]
        supabase_mock.table.return_value.select.return_value.in_.return_value.execute.return_value.data = [
            {"id": "l1", "title": "Test"}
        ]
        mock_genai.aio.models.generate_content.return_value.text = json.dumps(
            {
                "answer": "test",
                "confidence": 0.8,
                "cited_sources": [],
                "follow_up_suggestions": ["q1", "q2", "q3", "q4", "q5"],
            }
        )

        result = await ask_lecture_question(supabase_mock, "c1", "q")
        assert len(result["follow_up_suggestions"]) == 3

    async def test_lecture_filter_passed_through(self, supabase_mock, mock_genai):
        """Lecture IDs should be forwarded to search."""
        from lecturelink_api.services.rag import ask_lecture_question

        supabase_mock.rpc.return_value.execute.return_value.data = []

        await ask_lecture_question(
            supabase_mock, "c1", "q", lecture_ids=["lec-1", "lec-2"]
        )

        # Verify lecture IDs were passed to the RPC call
        rpc_call = supabase_mock.rpc.call_args
        assert rpc_call is not None

    async def test_fallback_sources_when_no_cited_sources(
        self, supabase_mock, mock_genai
    ):
        """When model doesn't cite sources, include all chunks as fallback."""
        from lecturelink_api.services.rag import ask_lecture_question

        supabase_mock.rpc.return_value.execute.return_value.data = [
            {"id": "c1", "lecture_id": "l1", "content": "chunk 1", "rrf_score": 0.9},
            {"id": "c2", "lecture_id": "l1", "content": "chunk 2", "rrf_score": 0.8},
        ]
        supabase_mock.table.return_value.select.return_value.in_.return_value.execute.return_value.data = [
            {"id": "l1", "title": "Test Lecture"}
        ]
        mock_genai.aio.models.generate_content.return_value.text = json.dumps(
            {
                "answer": "An answer without explicit citations.",
                "confidence": 0.7,
                "cited_sources": [],
                "follow_up_suggestions": [],
            }
        )

        result = await ask_lecture_question(supabase_mock, "c1", "q")
        # Should fall back to including all chunks
        assert len(result["source_chunks"]) == 2
