"""Tests for the Concept Extractor agent."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from lecturelink_api.agents.concept_extractor import (
    ConceptExtractionError,
    extract_concepts,
    format_content_for_extraction,
    validate_concepts,
)


# ---------------------------------------------------------------------------
# validate_concepts
# ---------------------------------------------------------------------------


class TestValidateConcepts:
    def test_valid_data_passes_through(self):
        concepts = [
            {
                "title": "First Law of Thermodynamics",
                "description": "Energy cannot be created or destroyed",
                "category": "theorem",
                "difficulty_estimate": 0.5,
                "related_concepts": ["Internal Energy"],
            },
            {
                "title": "Heat Transfer",
                "description": "Movement of thermal energy",
                "category": "process",
                "difficulty_estimate": 0.4,
                "related_concepts": [],
            },
        ]
        result = validate_concepts(concepts)
        assert len(result) == 2
        assert result[0]["title"] == "First Law of Thermodynamics"
        assert result[0]["category"] == "theorem"
        assert result[0]["difficulty_estimate"] == 0.5
        assert result[0]["related_concepts"] == ["Internal Energy"]
        assert result[1]["title"] == "Heat Transfer"

    def test_deduplicates_by_title_case_insensitive(self):
        concepts = [
            {"title": "Heat Transfer", "description": "A", "category": "concept"},
            {"title": "heat transfer", "description": "B", "category": "concept"},
            {"title": "HEAT TRANSFER", "description": "C", "category": "concept"},
        ]
        result = validate_concepts(concepts)
        assert len(result) == 1
        assert result[0]["title"] == "Heat Transfer"  # Keeps the first

    def test_rejects_empty_titles(self):
        concepts = [
            {"title": "", "description": "No title", "category": "concept"},
            {"title": "   ", "description": "Whitespace only", "category": "concept"},
            {"title": "Valid", "description": "OK", "category": "concept"},
        ]
        result = validate_concepts(concepts)
        assert len(result) == 1
        assert result[0]["title"] == "Valid"

    def test_clamps_difficulty_to_range(self):
        concepts = [
            {"title": "Too Low", "difficulty_estimate": -0.5, "category": "concept"},
            {"title": "Too High", "difficulty_estimate": 1.5, "category": "concept"},
            {"title": "Just Right", "difficulty_estimate": 0.7, "category": "concept"},
        ]
        result = validate_concepts(concepts)
        assert result[0]["difficulty_estimate"] == 0.0
        assert result[1]["difficulty_estimate"] == 1.0
        assert result[2]["difficulty_estimate"] == 0.7

    def test_normalizes_invalid_categories(self):
        concepts = [
            {"title": "A", "category": "unknown_cat"},
            {"title": "B", "category": "THEOREM"},  # lowercase normalization
            {"title": "C", "category": ""},
            {"title": "D"},  # Missing category entirely
        ]
        result = validate_concepts(concepts)
        assert result[0]["category"] == "concept"  # invalid → default
        assert result[1]["category"] == "theorem"  # THEOREM → theorem
        assert result[2]["category"] == "concept"  # empty → default
        assert result[3]["category"] == "concept"  # missing → default

    def test_defaults_for_missing_fields(self):
        concepts = [{"title": "Minimal"}]
        result = validate_concepts(concepts)
        assert len(result) == 1
        assert result[0]["description"] == ""
        assert result[0]["category"] == "concept"
        assert result[0]["difficulty_estimate"] == 0.5
        assert result[0]["related_concepts"] == []


# ---------------------------------------------------------------------------
# format_content_for_extraction
# ---------------------------------------------------------------------------


class TestFormatContentForExtraction:
    def test_formats_timestamps_and_slide_refs(self):
        segments = [
            {
                "start": 0.0,
                "end": 15.5,
                "text": "Welcome to the lecture.",
                "speaker": "professor",
                "slide_number": 1,
                "source": "aligned",
            },
            {
                "start": 65.0,
                "end": 120.0,
                "text": "Now let us discuss energy.",
                "speaker": "professor",
                "slide_number": 2,
                "source": "aligned",
            },
        ]
        result = format_content_for_extraction(segments)
        assert "[00:00]" in result
        assert "[Slide 1]" in result
        assert "Welcome to the lecture." in result
        assert "[01:05]" in result
        assert "[Slide 2]" in result

    def test_non_professor_speaker_shown(self):
        segments = [
            {
                "start": 10.0,
                "end": 20.0,
                "text": "I have a question.",
                "speaker": "student",
                "slide_number": None,
                "source": "audio",
            },
        ]
        result = format_content_for_extraction(segments)
        assert "(student)" in result

    def test_professor_speaker_omitted(self):
        segments = [
            {
                "start": 0.0,
                "end": 10.0,
                "text": "Hello class.",
                "speaker": "professor",
                "slide_number": None,
                "source": "audio",
            },
        ]
        result = format_content_for_extraction(segments)
        assert "(professor)" not in result

    def test_no_timestamp_when_start_is_none(self):
        segments = [
            {
                "start": None,
                "end": None,
                "text": "Slide-only text.",
                "slide_number": 3,
                "source": "slide",
            },
        ]
        result = format_content_for_extraction(segments)
        assert "[Slide 3]" in result
        assert "Slide-only text." in result
        # No timestamp prefix
        lines = result.strip().split("\n")
        assert not lines[0].startswith("[0")


# ---------------------------------------------------------------------------
# extract_concepts (mocked Gemini)
# ---------------------------------------------------------------------------


class TestExtractConcepts:
    @pytest.mark.asyncio
    async def test_successful_extraction(self):
        mock_concepts = [
            {
                "title": "Entropy",
                "description": "Measure of disorder",
                "category": "concept",
                "difficulty_estimate": 0.6,
                "related_concepts": [],
            },
        ]
        mock_response = MagicMock()
        mock_response.text = json.dumps(mock_concepts)

        mock_client = MagicMock()
        mock_client.aio.models.generate_content = AsyncMock(
            return_value=mock_response
        )

        segments = [
            {"start": 0.0, "end": 10.0, "text": "Entropy is disorder.", "source": "audio"},
        ]

        with patch(
            "lecturelink_api.agents.concept_extractor.genai.Client",
            return_value=mock_client,
        ):
            result = await extract_concepts(segments)

        assert len(result) == 1
        assert result[0]["title"] == "Entropy"

    @pytest.mark.asyncio
    async def test_handles_markdown_wrapped_json(self):
        mock_concepts = [{"title": "Work", "category": "concept"}]
        mock_response = MagicMock()
        mock_response.text = f"```json\n{json.dumps(mock_concepts)}\n```"

        mock_client = MagicMock()
        mock_client.aio.models.generate_content = AsyncMock(
            return_value=mock_response
        )

        segments = [
            {"start": 0.0, "end": 10.0, "text": "Work equals force times distance.", "source": "audio"},
        ]

        with patch(
            "lecturelink_api.agents.concept_extractor.genai.Client",
            return_value=mock_client,
        ):
            result = await extract_concepts(segments)

        assert len(result) == 1
        assert result[0]["title"] == "Work"

    @pytest.mark.asyncio
    async def test_invalid_json_raises_error(self):
        mock_response = MagicMock()
        mock_response.text = "not valid json at all"

        mock_client = MagicMock()
        mock_client.aio.models.generate_content = AsyncMock(
            return_value=mock_response
        )

        segments = [
            {"start": 0.0, "end": 10.0, "text": "Hello.", "source": "audio"},
        ]

        with patch(
            "lecturelink_api.agents.concept_extractor.genai.Client",
            return_value=mock_client,
        ):
            with pytest.raises(ConceptExtractionError, match="Failed to parse"):
                await extract_concepts(segments)

    @pytest.mark.asyncio
    async def test_api_failure_raises_error(self):
        mock_client = MagicMock()
        mock_client.aio.models.generate_content = AsyncMock(
            side_effect=RuntimeError("API down")
        )

        segments = [
            {"start": 0.0, "end": 10.0, "text": "Hello.", "source": "audio"},
        ]

        with patch(
            "lecturelink_api.agents.concept_extractor.genai.Client",
            return_value=mock_client,
        ):
            with pytest.raises(ConceptExtractionError, match="Concept extraction failed"):
                await extract_concepts(segments)
