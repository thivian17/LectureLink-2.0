"""Tests for the quiz planner service."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.fixture
def supabase_mock():
    """Mock Supabase client with chainable API."""
    client = MagicMock()

    # Default: chainable .table().select().eq().execute() etc.
    def _chain():
        m = MagicMock()
        m.select.return_value = m
        m.eq.return_value = m
        m.in_.return_value = m
        m.order.return_value = m
        m.limit.return_value = m
        m.execute.return_value = MagicMock(data=[])
        return m

    client.table.side_effect = lambda name: _chain()
    client.rpc.return_value.execute.return_value = MagicMock(data=[])
    return client


@pytest.fixture
def mock_genai():
    """Patch embed_query used by search_lectures."""
    with patch(
        "lecturelink_api.services.search.embed_query",
        new_callable=AsyncMock,
        return_value=[0.1] * 768,
    ):
        yield


class TestPlanQuiz:
    @pytest.mark.asyncio
    async def test_selects_concepts_for_assessment(
        self, supabase_mock, mock_genai,
    ):
        """When target_assessment_id provided, selects linked concepts."""
        from lecturelink_api.services.quiz_planner import plan_quiz

        # Mock concept_assessment_links query
        links_chain = MagicMock()
        links_chain.select.return_value = links_chain
        links_chain.eq.return_value = links_chain
        links_chain.order.return_value = links_chain
        links_chain.limit.return_value = links_chain
        links_chain.execute.return_value = MagicMock(data=[
            {"concept_id": "c1", "relevance_score": 0.9},
            {"concept_id": "c2", "relevance_score": 0.8},
        ])

        # Mock concepts query
        concepts_chain = MagicMock()
        concepts_chain.select.return_value = concepts_chain
        concepts_chain.in_.return_value = concepts_chain
        concepts_chain.execute.return_value = MagicMock(data=[
            {
                "id": "c1", "title": "Entropy",
                "description": "Measure of disorder",
                "category": "concept",
                "difficulty_estimate": 0.5, "lecture_id": "l1",
            },
            {
                "id": "c2", "title": "Enthalpy",
                "description": "Heat content",
                "category": "concept",
                "difficulty_estimate": 0.4, "lecture_id": "l1",
            },
        ])


        def table_side_effect(name):
            if name == "concept_assessment_links":
                return links_chain
            elif name == "concepts":
                return concepts_chain
            # lectures table for title enrichment
            lectures_chain = MagicMock()
            lectures_chain.select.return_value = lectures_chain
            lectures_chain.in_.return_value = lectures_chain
            lectures_chain.execute.return_value = MagicMock(
                data=[{"id": "l1", "title": "L1"}]
            )
            return lectures_chain

        supabase_mock.table.side_effect = table_side_effect

        # Mock hybrid_search RPC to return chunks
        supabase_mock.rpc.return_value.execute.return_value = MagicMock(data=[
            {
                "id": "chunk1", "lecture_id": "l1",
                "content": "test content", "rrf_score": 0.5,
                "start_time": 0, "end_time": 150,
                "slide_number": 1,
            },
        ])

        result = await plan_quiz(
            supabase_mock, "course-1", "user-1",
            target_assessment_id="assess-1", num_questions=2,
        )
        assert len(result["concepts"]) >= 1
        assert result["difficulty"] == "medium"

    @pytest.mark.asyncio
    async def test_raises_if_no_concepts(self, supabase_mock, mock_genai):
        """Should raise ValueError when no concepts found."""
        from lecturelink_api.services.quiz_planner import plan_quiz

        links_chain = MagicMock()
        links_chain.select.return_value = links_chain
        links_chain.eq.return_value = links_chain
        links_chain.order.return_value = links_chain
        links_chain.limit.return_value = links_chain
        links_chain.execute.return_value = MagicMock(data=[])
        supabase_mock.table.side_effect = None
        supabase_mock.table.return_value = links_chain

        with pytest.raises(ValueError, match="No concepts found"):
            await plan_quiz(
                supabase_mock, "course-1", "user-1",
                target_assessment_id="assess-1",
            )

    @pytest.mark.asyncio
    async def test_difficulty_filtering(self, supabase_mock, mock_genai):
        """Easy difficulty should prefer low difficulty_estimate concepts."""
        from lecturelink_api.services.quiz_planner import plan_quiz

        concepts_chain = MagicMock()
        concepts_chain.select.return_value = concepts_chain
        concepts_chain.eq.return_value = concepts_chain
        concepts_chain.execute.return_value = MagicMock(data=[
            {
                "id": "c1", "title": "Easy Concept",
                "difficulty_estimate": 0.2,
                "lecture_id": "l1", "description": "",
                "category": "concept",
            },
            {
                "id": "c2", "title": "Hard Concept",
                "difficulty_estimate": 0.8,
                "lecture_id": "l1", "description": "",
                "category": "concept",
            },
        ])

        # lectures table
        lectures_chain = MagicMock()
        lectures_chain.select.return_value = lectures_chain
        lectures_chain.in_.return_value = lectures_chain
        lectures_chain.execute.return_value = MagicMock(
            data=[{"id": "l1", "title": "L1"}]
        )

        def table_side_effect(name):
            if name == "concepts":
                return concepts_chain
            return lectures_chain

        supabase_mock.table.side_effect = table_side_effect

        supabase_mock.rpc.return_value.execute.return_value = MagicMock(data=[
            {
                "id": "chunk1", "lecture_id": "l1",
                "content": "test", "rrf_score": 0.5,
            },
        ])

        result = await plan_quiz(
            supabase_mock, "course-1", "user-1",
            difficulty="easy", num_questions=2,
        )
        # Easy concept should come first
        assert result["concepts"][0]["concept"]["title"] == "Easy Concept"

    @pytest.mark.asyncio
    async def test_skips_concepts_without_chunks(
        self, supabase_mock, mock_genai,
    ):
        """Concepts with no grounding chunks should be excluded."""
        from lecturelink_api.services.quiz_planner import plan_quiz

        concepts_chain = MagicMock()
        concepts_chain.select.return_value = concepts_chain
        concepts_chain.eq.return_value = concepts_chain
        concepts_chain.execute.return_value = MagicMock(data=[
            {
                "id": "c1", "title": "Orphan",
                "difficulty_estimate": 0.5,
                "lecture_id": "l1", "description": "",
                "category": "concept",
            },
        ])

        lectures_chain = MagicMock()
        lectures_chain.select.return_value = lectures_chain
        lectures_chain.in_.return_value = lectures_chain
        lectures_chain.execute.return_value = MagicMock(data=[])

        def table_side_effect(name):
            if name == "concepts":
                return concepts_chain
            return lectures_chain

        supabase_mock.table.side_effect = table_side_effect

        # Return no chunks from hybrid search
        supabase_mock.rpc.return_value.execute.return_value = MagicMock(data=[])

        with pytest.raises(ValueError, match="Could not find grounding"):
            await plan_quiz(supabase_mock, "course-1", "user-1")
