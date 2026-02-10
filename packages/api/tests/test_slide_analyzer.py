"""Tests for the slide analyzer agent."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from google.genai import types

from lecturelink_api.agents.slide_analyzer import (
    SlideAnalysisError,
    analyze_slides,
    get_slide_mime_type,
    validate_slide_analysis,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

VALID_SLIDE_RESPONSE = [
    {
        "slide_number": 1,
        "title": "Introduction to Thermodynamics",
        "text_content": "PHYS 201 - Lecture 1\nDr. Smith",
        "visual_description": None,
        "has_diagram": False,
        "has_code": False,
        "has_equation": False,
    },
    {
        "slide_number": 2,
        "title": "What is Energy?",
        "text_content": "Energy is the capacity to do work",
        "visual_description": "Diagram showing potential vs kinetic energy",
        "has_diagram": True,
        "has_code": False,
        "has_equation": True,
    },
    {
        "slide_number": 3,
        "title": None,
        "text_content": "def heat_transfer(q, m, c):\n    return q / (m * c)",
        "visual_description": None,
        "has_diagram": False,
        "has_code": True,
        "has_equation": False,
    },
]


# ---------------------------------------------------------------------------
# validate_slide_analysis
# ---------------------------------------------------------------------------


class TestValidateSlideAnalysis:
    def test_valid_data_passes_through(self):
        result = validate_slide_analysis(VALID_SLIDE_RESPONSE)
        assert len(result) == 3
        assert result[0]["slide_number"] == 1
        assert result[0]["title"] == "Introduction to Thermodynamics"
        assert result[1]["has_diagram"] is True
        assert result[2]["has_code"] is True

    def test_missing_fields_get_defaults(self):
        incomplete = [
            {"slide_number": 1},
            {"text_content": "Some text"},
            {},
        ]
        result = validate_slide_analysis(incomplete)

        assert len(result) == 3
        # First slide: has slide_number, defaults for the rest
        assert result[0]["slide_number"] == 1
        assert result[0]["text_content"] == ""
        assert result[0]["title"] is None
        assert result[0]["visual_description"] is None
        assert result[0]["has_diagram"] is False
        assert result[0]["has_code"] is False
        assert result[0]["has_equation"] is False

        # Second slide: missing slide_number defaults to index+1
        assert result[1]["slide_number"] == 2
        assert result[1]["text_content"] == "Some text"

        # Third slide: all defaults
        assert result[2]["slide_number"] == 3
        assert result[2]["text_content"] == ""

    def test_boolean_fields_coerced(self):
        slides = [
            {
                "slide_number": 1,
                "has_diagram": 1,
                "has_code": 0,
                "has_equation": "yes",
            }
        ]
        result = validate_slide_analysis(slides)
        assert result[0]["has_diagram"] is True
        assert result[0]["has_code"] is False
        assert result[0]["has_equation"] is True

    def test_empty_list(self):
        assert validate_slide_analysis([]) == []


# ---------------------------------------------------------------------------
# get_slide_mime_type
# ---------------------------------------------------------------------------


class TestGetSlideMimeType:
    def test_pdf(self):
        assert get_slide_mime_type("lecture.pdf") == "application/pdf"
        assert get_slide_mime_type("/path/to/Slides.PDF") == "application/pdf"

    def test_pptx(self):
        result = get_slide_mime_type("presentation.pptx")
        assert "presentationml.presentation" in result

    def test_unknown_defaults_to_pdf(self):
        assert get_slide_mime_type("file.docx") == "application/pdf"
        assert get_slide_mime_type("file.txt") == "application/pdf"


# ---------------------------------------------------------------------------
# analyze_slides — mock Gemini
# ---------------------------------------------------------------------------


class TestAnalyzeSlides:
    """Tests mock _call_gemini to avoid real I/O and API calls."""

    @pytest.mark.asyncio
    async def test_successful_pdf_analysis(self):
        with patch(
            "lecturelink_api.agents.slide_analyzer._call_gemini",
            new_callable=AsyncMock,
            return_value=VALID_SLIDE_RESPONSE,
        ):
            result = await analyze_slides("lecture.pdf")

        assert len(result) == 3
        assert result[0]["title"] == "Introduction to Thermodynamics"
        assert result[1]["has_diagram"] is True

    @pytest.mark.asyncio
    async def test_transient_failure_retries_then_succeeds(self):
        """Retries on transient errors, succeeds on second attempt."""
        call_gemini = AsyncMock(
            side_effect=[
                RuntimeError("Transient API error"),
                VALID_SLIDE_RESPONSE,
            ]
        )

        with patch(
            "lecturelink_api.agents.slide_analyzer._call_gemini",
            call_gemini,
        ), patch(
            "lecturelink_api.agents.slide_analyzer.asyncio.sleep",
            new_callable=AsyncMock,
        ):
            result = await analyze_slides("lecture.pdf")

        assert len(result) == 3
        assert call_gemini.call_count == 2

    @pytest.mark.asyncio
    async def test_all_retries_exhausted_raises_error(self):
        """Raises SlideAnalysisError after all retries fail."""
        with patch(
            "lecturelink_api.agents.slide_analyzer._call_gemini",
            new_callable=AsyncMock,
            side_effect=RuntimeError("Persistent failure"),
        ), patch(
            "lecturelink_api.agents.slide_analyzer.asyncio.sleep",
            new_callable=AsyncMock,
        ):
            with pytest.raises(SlideAnalysisError, match="after 3 retries"):
                await analyze_slides("lecture.pdf")

    @pytest.mark.asyncio
    async def test_slide_analysis_error_not_retried(self):
        """SlideAnalysisError is raised immediately, not retried."""
        with patch(
            "lecturelink_api.agents.slide_analyzer._call_gemini",
            new_callable=AsyncMock,
            side_effect=SlideAnalysisError("Bad JSON"),
        ):
            with pytest.raises(SlideAnalysisError, match="Bad JSON"):
                await analyze_slides("lecture.pdf")


class TestCallGemini:
    """Tests for _call_gemini parsing logic with mocked genai.Client + _file_part."""

    def _mock_gemini(self, response_text):
        """Return (mock_client, _file_part_mock) pair for _call_gemini tests."""
        mock_response = MagicMock()
        mock_response.text = response_text

        mock_client = MagicMock()
        mock_client.aio.models.generate_content = AsyncMock(
            return_value=mock_response
        )
        return mock_client

    @pytest.mark.asyncio
    async def test_parses_valid_json(self):
        from lecturelink_api.agents.slide_analyzer import _call_gemini

        mock_client = self._mock_gemini(json.dumps(VALID_SLIDE_RESPONSE))

        with patch(
            "lecturelink_api.agents.slide_analyzer.genai.Client",
            return_value=mock_client,
        ), patch(
            "lecturelink_api.agents.slide_analyzer._file_part",
            return_value=MagicMock(spec=types.Part),
        ):
            result = await _call_gemini("lecture.pdf")

        assert len(result) == 3
        assert result[0]["title"] == "Introduction to Thermodynamics"

    @pytest.mark.asyncio
    async def test_strips_markdown_code_fences(self):
        from lecturelink_api.agents.slide_analyzer import _call_gemini

        fenced = "```json\n" + json.dumps(VALID_SLIDE_RESPONSE) + "\n```"
        mock_client = self._mock_gemini(fenced)

        with patch(
            "lecturelink_api.agents.slide_analyzer.genai.Client",
            return_value=mock_client,
        ), patch(
            "lecturelink_api.agents.slide_analyzer._file_part",
            return_value=MagicMock(spec=types.Part),
        ):
            result = await _call_gemini("lecture.pdf")

        assert len(result) == 3

    @pytest.mark.asyncio
    async def test_invalid_json_raises_error(self):
        from lecturelink_api.agents.slide_analyzer import _call_gemini

        mock_client = self._mock_gemini("This is not JSON at all")

        with patch(
            "lecturelink_api.agents.slide_analyzer.genai.Client",
            return_value=mock_client,
        ), patch(
            "lecturelink_api.agents.slide_analyzer._file_part",
            return_value=MagicMock(spec=types.Part),
        ):
            with pytest.raises(SlideAnalysisError, match="Failed to parse"):
                await _call_gemini("lecture.pdf")

    @pytest.mark.asyncio
    async def test_non_array_raises_error(self):
        from lecturelink_api.agents.slide_analyzer import _call_gemini

        mock_client = self._mock_gemini('{"not": "an array"}')

        with patch(
            "lecturelink_api.agents.slide_analyzer.genai.Client",
            return_value=mock_client,
        ), patch(
            "lecturelink_api.agents.slide_analyzer._file_part",
            return_value=MagicMock(spec=types.Part),
        ):
            with pytest.raises(SlideAnalysisError, match="did not return"):
                await _call_gemini("lecture.pdf")
