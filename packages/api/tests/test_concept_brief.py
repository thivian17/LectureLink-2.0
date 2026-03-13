"""Tests for the concept brief generator service."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


def _mock_execute(data):
    resp = MagicMock()
    resp.data = data
    resp.count = 0
    return resp


def _mock_chain(final_data):
    chain = MagicMock()
    chain.execute.return_value = _mock_execute(final_data)
    for method in ("select", "eq", "in_", "order", "limit", "single"):
        getattr(chain, method).return_value = chain
    return chain


SAMPLE_BRIEF_RESPONSE = {
    "what_is_this": "Entropy is a measure of disorder in a system.",
    "why_it_matters": (
        "**For this course:** Entropy connects thermodynamics to statistical mechanics.\n"
        "**For the real world:** Engineers use entropy to design efficient engines."
    ),
    "key_relationship": "dS = dQ/T — entropy change equals heat transfer divided by temperature.",
    "gut_check": {
        "question_text": "What does entropy measure?",
        "options": ["Disorder", "Energy", "Temperature", "Pressure"],
        "correct_index": 0,
        "explanation": "Entropy is fundamentally a measure of disorder or randomness.",
    },
}


class TestMasteryTier:
    def test_novice_tier(self):
        from lecturelink_api.services.concept_brief import _mastery_tier

        assert _mastery_tier(0.0) == "novice"
        assert _mastery_tier(0.1) == "novice"
        assert _mastery_tier(0.29) == "novice"

    def test_developing_tier(self):
        from lecturelink_api.services.concept_brief import _mastery_tier

        assert _mastery_tier(0.3) == "developing"
        assert _mastery_tier(0.5) == "developing"
        assert _mastery_tier(0.59) == "developing"

    def test_proficient_tier(self):
        from lecturelink_api.services.concept_brief import _mastery_tier

        assert _mastery_tier(0.6) == "proficient"
        assert _mastery_tier(0.7) == "proficient"
        assert _mastery_tier(0.79) == "proficient"

    def test_advanced_tier(self):
        from lecturelink_api.services.concept_brief import _mastery_tier

        assert _mastery_tier(0.8) == "advanced"
        assert _mastery_tier(0.9) == "advanced"
        assert _mastery_tier(1.0) == "advanced"


class TestGenerateConceptBrief:
    @pytest.mark.asyncio
    async def test_includes_all_sections_and_gut_check(self):
        from lecturelink_api.services.concept_brief import generate_concept_brief

        sb = MagicMock()

        concept = {
            "id": "c1",
            "title": "Entropy",
            "description": "Measure of disorder",
            "course_id": "course1",
        }

        def table_side_effect(name):
            if name == "concepts":
                return _mock_chain(concept)
            if name == "courses":
                return _mock_chain({"name": "PHYS 201"})
            if name == "concept_assessment_links":
                return _mock_chain([])
            if name == "assessments":
                return _mock_chain([])
            return _mock_chain([])

        sb.table.side_effect = table_side_effect

        mock_response = MagicMock()
        mock_response.text = json.dumps(SAMPLE_BRIEF_RESPONSE)

        mock_client = MagicMock()
        mock_client.aio.models.generate_content = AsyncMock(return_value=mock_response)

        with (
            patch(
                "lecturelink_api.services.concept_brief._get_client",
                return_value=mock_client,
            ),
            patch(
                "lecturelink_api.services.concept_brief.fetch_concept_chunks",
                new_callable=AsyncMock,
                return_value=[
                    {
                        "chunk_id": "ch1",
                        "content": "Entropy explained",
                        "lecture_title": "Lecture 3",
                        "start_time": 120.0,
                    }
                ],
            ),
        ):
            result = await generate_concept_brief(
                sb, user_id="u1", concept_id="c1", course_id="course1", mastery_score=0.4
            )

        # All three sections present
        assert "what_is_this" in result["sections"]
        assert "why_it_matters" in result["sections"]
        assert "key_relationship" in result["sections"]

        # Gut-check present
        assert "question_text" in result["gut_check"]
        assert "options" in result["gut_check"]
        assert "correct_index" in result["gut_check"]
        assert "explanation" in result["gut_check"]

        # Metadata
        assert result["concept_id"] == "c1"
        assert result["mastery_tier"] == "developing"
        assert len(result["sources"]) >= 1

    @pytest.mark.asyncio
    async def test_prompt_uses_real_world_framing_not_exam(self):
        """CRITICAL: Concept brief must frame 'why it matters' as real-world relevance."""
        from lecturelink_api.services.concept_brief import CONCEPT_BRIEF_PROMPT

        # Assert the prompt contains real-world framing
        assert "REAL WORLD" in CONCEPT_BRIEF_PROMPT
        assert "Practical applications" in CONCEPT_BRIEF_PROMPT
        assert "career relevance" in CONCEPT_BRIEF_PROMPT

        # Assert it explicitly forbids exam framing
        assert 'NOT frame this as "for your exam"' in CONCEPT_BRIEF_PROMPT

    @pytest.mark.asyncio
    async def test_source_chunks_retrieved_via_search(self):
        from lecturelink_api.services.concept_brief import generate_concept_brief

        sb = MagicMock()

        def table_side_effect(name):
            if name == "concepts":
                return _mock_chain({"id": "c1", "title": "X", "description": ""})
            if name == "courses":
                return _mock_chain({"name": "CS 101"})
            if name == "concept_assessment_links":
                return _mock_chain([])
            return _mock_chain([])

        sb.table.side_effect = table_side_effect

        mock_response = MagicMock()
        mock_response.text = json.dumps(SAMPLE_BRIEF_RESPONSE)

        mock_client = MagicMock()
        mock_client.aio.models.generate_content = AsyncMock(return_value=mock_response)

        mock_fetch = AsyncMock(return_value=[
            {"chunk_id": "ch1", "content": "Source content", "lecture_title": "L1", "start_time": 60.0},
        ])

        with (
            patch("lecturelink_api.services.concept_brief._get_client", return_value=mock_client),
            patch("lecturelink_api.services.concept_brief.fetch_concept_chunks", mock_fetch),
        ):
            result = await generate_concept_brief(
                sb, user_id="u1", concept_id="c1", course_id="course1"
            )

        mock_fetch.assert_called_once()
        assert result["sources"][0]["lecture_title"] == "L1"

    @pytest.mark.asyncio
    async def test_json_parse_fallback_on_malformed_response(self):
        from lecturelink_api.services.concept_brief import generate_concept_brief

        sb = MagicMock()

        def table_side_effect(name):
            if name == "concepts":
                return _mock_chain({"id": "c1", "title": "X", "description": ""})
            if name == "courses":
                return _mock_chain({"name": "CS 101"})
            if name == "concept_assessment_links":
                return _mock_chain([])
            return _mock_chain([])

        sb.table.side_effect = table_side_effect

        # Return invalid JSON
        mock_response = MagicMock()
        mock_response.text = "This is not JSON at all {{{}"

        mock_client = MagicMock()
        mock_client.aio.models.generate_content = AsyncMock(return_value=mock_response)

        with (
            patch("lecturelink_api.services.concept_brief._get_client", return_value=mock_client),
            patch(
                "lecturelink_api.services.concept_brief.fetch_concept_chunks",
                new_callable=AsyncMock,
                return_value=[],
            ),
        ):
            result = await generate_concept_brief(
                sb, user_id="u1", concept_id="c1", course_id="course1"
            )

        # Should return a fallback instead of crashing
        assert "sections" in result
        assert "gut_check" in result

    @pytest.mark.asyncio
    async def test_mastery_tier_included_in_result(self):
        from lecturelink_api.services.concept_brief import generate_concept_brief

        sb = MagicMock()

        def table_side_effect(name):
            if name == "concepts":
                return _mock_chain({"id": "c1", "title": "X", "description": ""})
            if name == "courses":
                return _mock_chain({"name": "CS 101"})
            if name == "concept_assessment_links":
                return _mock_chain([])
            return _mock_chain([])

        sb.table.side_effect = table_side_effect

        mock_response = MagicMock()
        mock_response.text = json.dumps(SAMPLE_BRIEF_RESPONSE)

        mock_client = MagicMock()
        mock_client.aio.models.generate_content = AsyncMock(return_value=mock_response)

        with (
            patch("lecturelink_api.services.concept_brief._get_client", return_value=mock_client),
            patch(
                "lecturelink_api.services.concept_brief.fetch_concept_chunks",
                new_callable=AsyncMock,
                return_value=[],
            ),
        ):
            result = await generate_concept_brief(
                sb, user_id="u1", concept_id="c1", course_id="course1", mastery_score=0.85
            )

        assert result["mastery_tier"] == "advanced"


class TestExpandedClarification:
    @pytest.mark.asyncio
    async def test_generates_clarification(self):
        from lecturelink_api.services.concept_brief import generate_expanded_clarification

        mock_response = MagicMock()
        mock_response.text = "Actually, entropy measures disorder, not energy."

        mock_client = MagicMock()
        mock_client.aio.models.generate_content = AsyncMock(return_value=mock_response)

        with patch(
            "lecturelink_api.services.concept_brief._get_client",
            return_value=mock_client,
        ):
            result = await generate_expanded_clarification(
                concept_title="Entropy",
                question_text="What does entropy measure?",
                correct_answer="Disorder",
                student_answer="Energy",
                source_chunks=["Entropy is a measure of disorder"],
            )

        assert "entropy" in result.lower() or "disorder" in result.lower()

    @pytest.mark.asyncio
    async def test_fallback_on_failure(self):
        from lecturelink_api.services.concept_brief import generate_expanded_clarification

        mock_client = MagicMock()
        mock_client.aio.models.generate_content = AsyncMock(
            side_effect=Exception("API error")
        )

        with patch(
            "lecturelink_api.services.concept_brief._get_client",
            return_value=mock_client,
        ):
            result = await generate_expanded_clarification(
                concept_title="Entropy",
                question_text="What?",
                correct_answer="Disorder",
                student_answer="Energy",
                source_chunks=[],
            )

        assert "Disorder" in result


class TestParseJsonResponse:
    def test_plain_json(self):
        from lecturelink_api.services.concept_brief import _parse_json_response

        result = _parse_json_response('{"key": "value"}')
        assert result == {"key": "value"}

    def test_markdown_fenced_json(self):
        from lecturelink_api.services.concept_brief import _parse_json_response

        text = '```json\n{"key": "value"}\n```'
        result = _parse_json_response(text)
        assert result == {"key": "value"}

    def test_markdown_fenced_no_language(self):
        from lecturelink_api.services.concept_brief import _parse_json_response

        text = '```\n{"key": "value"}\n```'
        result = _parse_json_response(text)
        assert result == {"key": "value"}
