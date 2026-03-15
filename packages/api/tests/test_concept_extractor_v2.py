"""Tests for the Concept Extractor V2 functions."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from lecturelink_api.agents.concept_extractor import (
    META_PATTERNS,
    ConceptExtractionError,
    _is_meta_concept,
    extract_concepts_v2,
    format_existing_concepts_for_prompt,
    validate_concepts_v2,
)


# ===================================================================
# validate_concepts_v2
# ===================================================================


class TestValidateConceptsV2:
    def test_valid_flat_concepts_pass_through(self):
        concepts = [
            {
                "title": "Newton's Second Law",
                "description": "F = ma",
                "category": "formula",
                "difficulty_estimate": 0.4,
                "related_concepts": ["Force"],
                "key_terms": ["force", "mass", "acceleration"],
            },
            {
                "title": "Kinetic Energy",
                "description": "Energy of motion",
                "category": "definition",
                "difficulty_estimate": 0.3,
                "related_concepts": [],
                "key_terms": ["kinetic", "energy"],
            },
        ]
        result = validate_concepts_v2(concepts)
        assert len(result) == 2
        assert result[0]["title"] == "Newton's Second Law"
        assert result[0]["key_terms"] == ["force", "mass", "acceleration"]
        assert result[1]["title"] == "Kinetic Energy"

    def test_deduplicates_case_insensitive(self):
        concepts = [
            {"title": "Heat Transfer", "category": "concept"},
            {"title": "heat transfer", "category": "concept"},
            {"title": "HEAT TRANSFER", "category": "concept"},
        ]
        result = validate_concepts_v2(concepts)
        assert len(result) == 1
        assert result[0]["title"] == "Heat Transfer"

    def test_deduplicates_plurals(self):
        concepts = [
            {"title": "Binary Variable", "category": "concept"},
            {"title": "Binary Variables", "category": "concept"},
        ]
        result = validate_concepts_v2(concepts)
        assert len(result) == 1

    def test_deduplicates_quotes(self):
        concepts = [
            {"title": "Binary Variable", "category": "concept"},
            {"title": "'Binary Variable'", "category": "concept"},
            {"title": '"Binary Variable"', "category": "concept"},
        ]
        result = validate_concepts_v2(concepts)
        assert len(result) == 1

    def test_filters_meta_concepts(self):
        concepts = [
            {"title": "Lecture Overview", "category": "concept"},
            {"title": "Homework Reminder", "category": "concept"},
            {"title": "Thermodynamic System", "category": "definition"},
        ]
        result = validate_concepts_v2(concepts)
        assert len(result) == 1
        assert result[0]["title"] == "Thermodynamic System"

    def test_rejects_empty_titles(self):
        concepts = [
            {"title": "", "description": "No title"},
            {"title": "   ", "description": "Whitespace"},
            {"title": "Valid Concept", "description": "OK"},
        ]
        result = validate_concepts_v2(concepts)
        assert len(result) == 1
        assert result[0]["title"] == "Valid Concept"

    def test_clamps_difficulty(self):
        concepts = [
            {"title": "Too Low", "difficulty_estimate": -0.5},
            {"title": "Too High", "difficulty_estimate": 1.5},
            {"title": "Normal", "difficulty_estimate": 0.7},
        ]
        result = validate_concepts_v2(concepts)
        assert result[0]["difficulty_estimate"] == 0.0
        assert result[1]["difficulty_estimate"] == 1.0
        assert result[2]["difficulty_estimate"] == 0.7

    def test_normalizes_invalid_categories(self):
        concepts = [
            {"title": "A", "category": "unknown_cat"},
            {"title": "B", "category": "THEOREM"},
            {"title": "C", "category": ""},
            {"title": "D"},
        ]
        result = validate_concepts_v2(concepts)
        assert result[0]["category"] == "concept"
        assert result[1]["category"] == "theorem"
        assert result[2]["category"] == "concept"
        assert result[3]["category"] == "concept"

    def test_preserves_key_terms(self):
        concepts = [
            {
                "title": "Ohm's Law",
                "key_terms": ["voltage", "current", "resistance"],
            },
        ]
        result = validate_concepts_v2(concepts)
        assert result[0]["key_terms"] == ["voltage", "current", "resistance"]

    def test_key_terms_defaults_to_empty_list(self):
        concepts = [{"title": "Minimal Concept"}]
        result = validate_concepts_v2(concepts)
        assert result[0]["key_terms"] == []

    def test_no_subconcepts_in_output(self):
        concepts = [
            {
                "title": "Parent",
                "subconcepts": [
                    {"title": "Child 1"},
                    {"title": "Child 2"},
                ],
            },
        ]
        result = validate_concepts_v2(concepts)
        assert len(result) == 1
        assert "subconcepts" not in result[0]

    def test_defaults_for_missing_fields(self):
        concepts = [{"title": "Minimal"}]
        result = validate_concepts_v2(concepts)
        assert result[0]["description"] == ""
        assert result[0]["category"] == "concept"
        assert result[0]["difficulty_estimate"] == 0.5
        assert result[0]["related_concepts"] == []
        assert result[0]["key_terms"] == []


# ===================================================================
# _is_meta_concept
# ===================================================================


class TestIsMetaConcept:
    @pytest.mark.parametrize("pattern", list(META_PATTERNS))
    def test_matches_all_meta_patterns(self, pattern):
        # Title containing the pattern
        assert _is_meta_concept(pattern)

    @pytest.mark.parametrize("pattern", list(META_PATTERNS))
    def test_matches_with_extra_text(self, pattern):
        assert _is_meta_concept(f"Today's {pattern} notes")

    @pytest.mark.parametrize("pattern", list(META_PATTERNS))
    def test_case_insensitive(self, pattern):
        assert _is_meta_concept(pattern.upper())

    def test_real_concepts_not_filtered(self):
        assert not _is_meta_concept("Thermodynamic System")
        assert not _is_meta_concept("Newton's Second Law")
        assert not _is_meta_concept("Binary Search Algorithm")
        assert not _is_meta_concept("Pivot Column Selection Rule")

    def test_whitespace_stripped(self):
        assert _is_meta_concept("  lecture overview  ")


# ===================================================================
# format_existing_concepts_for_prompt
# ===================================================================


class TestFormatExistingConceptsForPrompt:
    def test_empty_list_returns_none_yet(self):
        result = format_existing_concepts_for_prompt([])
        assert result == "None yet — this is the first lecture."

    def test_formats_concepts(self):
        data = [
            {"title": "Force", "description": "A push or pull on an object"},
            {"title": "Mass", "description": "Amount of matter"},
        ]
        result = format_existing_concepts_for_prompt(data)
        assert "- Force: A push or pull on an object" in result
        assert "- Mass: Amount of matter" in result

    def test_caps_at_50_concepts(self):
        data = [{"title": f"Concept {i}", "description": f"Desc {i}"} for i in range(100)]
        result = format_existing_concepts_for_prompt(data)
        lines = result.strip().split("\n")
        assert len(lines) == 50

    def test_truncates_descriptions_at_100_chars(self):
        long_desc = "A" * 200
        data = [{"title": "Long", "description": long_desc}]
        result = format_existing_concepts_for_prompt(data)
        # "- Long: " + 100 chars
        assert len(result.split(": ", 1)[1]) == 100

    def test_handles_none_description(self):
        data = [{"title": "NoDesc", "description": None}]
        result = format_existing_concepts_for_prompt(data)
        assert "- NoDesc: " in result


# ===================================================================
# extract_concepts_v2 (mocked Gemini)
# ===================================================================


class TestExtractConceptsV2:
    @pytest.mark.asyncio
    async def test_successful_extraction(self):
        mock_concepts = [
            {
                "title": "Entropy",
                "description": "Measure of disorder",
                "category": "concept",
                "difficulty_estimate": 0.6,
                "related_concepts": [],
                "key_terms": ["entropy", "disorder"],
            },
        ]
        mock_response = MagicMock()
        mock_response.text = json.dumps(mock_concepts)

        mock_client = MagicMock()
        mock_client.aio.models.generate_content = AsyncMock(
            return_value=mock_response,
        )

        segments = [
            {"start": 0.0, "end": 10.0, "text": "Entropy is disorder.", "source": "audio"},
        ]

        with patch(
            "lecturelink_api.agents.concept_extractor._get_client",
            return_value=mock_client,
        ):
            result = await extract_concepts_v2(segments)

        assert len(result) == 1
        assert result[0]["title"] == "Entropy"
        assert result[0]["key_terms"] == ["entropy", "disorder"]

    @pytest.mark.asyncio
    async def test_passes_existing_concepts_context(self):
        mock_response = MagicMock()
        mock_response.text = json.dumps([
            {"title": "New Concept", "category": "concept"},
        ])

        mock_client = MagicMock()
        mock_client.aio.models.generate_content = AsyncMock(
            return_value=mock_response,
        )

        segments = [
            {"start": 0.0, "end": 10.0, "text": "Some content.", "source": "audio"},
        ]

        context = "- Force: A push or pull\n- Mass: Amount of matter"

        with patch(
            "lecturelink_api.agents.concept_extractor._get_client",
            return_value=mock_client,
        ):
            result = await extract_concepts_v2(segments, existing_concepts_context=context)

        # Verify the prompt included the context
        call_args = mock_client.aio.models.generate_content.call_args
        prompt_text = call_args.kwargs["contents"][0].parts[0].text
        assert "- Force: A push or pull" in prompt_text
        assert "- Mass: Amount of matter" in prompt_text

        assert len(result) == 1

    @pytest.mark.asyncio
    async def test_json_parse_failure_raises_error(self):
        mock_response = MagicMock()
        mock_response.text = "not valid json"

        mock_client = MagicMock()
        mock_client.aio.models.generate_content = AsyncMock(
            return_value=mock_response,
        )

        segments = [
            {"start": 0.0, "end": 10.0, "text": "Hello.", "source": "audio"},
        ]

        with patch(
            "lecturelink_api.agents.concept_extractor._get_client",
            return_value=mock_client,
        ), pytest.raises(ConceptExtractionError, match="Failed to parse"):
            await extract_concepts_v2(segments)

    @pytest.mark.asyncio
    async def test_api_failure_raises_error(self):
        mock_client = MagicMock()
        mock_client.aio.models.generate_content = AsyncMock(
            side_effect=RuntimeError("API down"),
        )

        segments = [
            {"start": 0.0, "end": 10.0, "text": "Hello.", "source": "audio"},
        ]

        with patch(
            "lecturelink_api.agents.concept_extractor._get_client",
            return_value=mock_client,
        ), pytest.raises(ConceptExtractionError, match="Concept extraction V2 failed"):
            await extract_concepts_v2(segments)

    @pytest.mark.asyncio
    async def test_handles_markdown_wrapped_json(self):
        mock_concepts = [{"title": "Work", "category": "concept", "key_terms": ["work"]}]
        mock_response = MagicMock()
        mock_response.text = f"```json\n{json.dumps(mock_concepts)}\n```"

        mock_client = MagicMock()
        mock_client.aio.models.generate_content = AsyncMock(
            return_value=mock_response,
        )

        segments = [
            {"start": 0.0, "end": 10.0, "text": "Work equals force times distance.", "source": "audio"},
        ]

        with patch(
            "lecturelink_api.agents.concept_extractor._get_client",
            return_value=mock_client,
        ):
            result = await extract_concepts_v2(segments)

        assert len(result) == 1
        assert result[0]["title"] == "Work"

    @pytest.mark.asyncio
    async def test_filters_meta_concepts_from_llm_output(self):
        mock_concepts = [
            {"title": "Lecture Overview", "category": "concept"},
            {"title": "Real Concept", "category": "definition"},
        ]
        mock_response = MagicMock()
        mock_response.text = json.dumps(mock_concepts)

        mock_client = MagicMock()
        mock_client.aio.models.generate_content = AsyncMock(
            return_value=mock_response,
        )

        segments = [
            {"start": 0.0, "end": 10.0, "text": "Content.", "source": "audio"},
        ]

        with patch(
            "lecturelink_api.agents.concept_extractor._get_client",
            return_value=mock_client,
        ):
            result = await extract_concepts_v2(segments)

        assert len(result) == 1
        assert result[0]["title"] == "Real Concept"
