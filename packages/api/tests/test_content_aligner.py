"""Tests for the content aligner agent."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from lecturelink_api.agents.content_aligner import (
    _heuristic_align,
    _slide_to_text,
    align_content,
    validate_alignment,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

SAMPLE_TRANSCRIPT = [
    {"start": 0.0, "end": 15.5, "text": "Welcome to thermodynamics.", "speaker": "professor"},
    {"start": 15.5, "end": 45.2, "text": "Today we cover energy transfer.", "speaker": "professor"},
    {"start": 45.2, "end": 90.0, "text": "Let's look at this diagram.", "speaker": "professor"},
    {"start": 90.0, "end": 120.0, "text": "Next slide please.", "speaker": "professor"},
]

SAMPLE_SLIDES = [
    {
        "slide_number": 1,
        "title": "Introduction",
        "text_content": "PHYS 201 - Thermodynamics",
        "visual_description": None,
        "has_diagram": False,
        "has_code": False,
        "has_equation": False,
    },
    {
        "slide_number": 2,
        "title": "Energy Transfer",
        "text_content": "Energy can be transferred via heat and work",
        "visual_description": "Diagram of heat engine cycle",
        "has_diagram": True,
        "has_code": False,
        "has_equation": True,
    },
    {
        "slide_number": 3,
        "title": "First Law",
        "text_content": "dU = dQ - dW",
        "visual_description": None,
        "has_diagram": False,
        "has_code": False,
        "has_equation": True,
    },
]

ALIGNED_RESPONSE = [
    {
        "start": 0.0,
        "end": 15.5,
        "text": "Welcome to thermodynamics.",
        "speaker": "professor",
        "slide_number": 1,
        "source": "aligned",
    },
    {
        "start": 15.5,
        "end": 45.2,
        "text": "Today we cover energy transfer.",
        "speaker": "professor",
        "slide_number": 2,
        "source": "aligned",
    },
    {
        "start": 45.2,
        "end": 90.0,
        "text": "Let's look at this diagram.",
        "speaker": "professor",
        "slide_number": 2,
        "source": "aligned",
    },
    {
        "start": 90.0,
        "end": 120.0,
        "text": "Next slide please.",
        "speaker": "professor",
        "slide_number": 3,
        "source": "aligned",
    },
]


# ---------------------------------------------------------------------------
# align_content — three modes
# ---------------------------------------------------------------------------


class TestAlignContent:
    @pytest.mark.asyncio
    async def test_audio_and_slides_calls_gemini(self):
        mock_response = MagicMock()
        mock_response.text = json.dumps(ALIGNED_RESPONSE)

        mock_client = MagicMock()
        mock_client.aio.models.generate_content = AsyncMock(
            return_value=mock_response
        )

        with patch(
            "lecturelink_api.agents.content_aligner.genai.Client",
            return_value=mock_client,
        ):
            result = await align_content(SAMPLE_TRANSCRIPT, SAMPLE_SLIDES)

        assert len(result) == 4
        assert result[0]["slide_number"] == 1
        assert result[0]["source"] == "aligned"
        assert result[3]["slide_number"] == 3
        mock_client.aio.models.generate_content.assert_called_once()

    @pytest.mark.asyncio
    async def test_audio_only_returns_audio_source(self):
        result = await align_content(SAMPLE_TRANSCRIPT, None)

        assert len(result) == 4
        for seg in result:
            assert seg["source"] == "audio"
            assert seg["slide_number"] is None
        assert result[0]["text"] == "Welcome to thermodynamics."
        assert result[0]["start"] == 0.0
        assert result[0]["end"] == 15.5
        assert result[0]["speaker"] == "professor"

    @pytest.mark.asyncio
    async def test_audio_only_with_empty_list(self):
        result = await align_content(SAMPLE_TRANSCRIPT, [])

        assert len(result) == 4
        for seg in result:
            assert seg["source"] == "audio"

    @pytest.mark.asyncio
    async def test_slides_only_returns_slide_source(self):
        result = await align_content(None, SAMPLE_SLIDES)

        assert len(result) == 3
        for seg in result:
            assert seg["source"] == "slide"
            assert seg["start"] is None
            assert seg["end"] is None
        assert result[0]["slide_number"] == 1
        assert "[Slide 1: Introduction]" in result[0]["text"]
        assert result[1]["slide_number"] == 2

    @pytest.mark.asyncio
    async def test_slides_only_with_empty_transcript(self):
        result = await align_content([], SAMPLE_SLIDES)

        assert len(result) == 3
        for seg in result:
            assert seg["source"] == "slide"

    @pytest.mark.asyncio
    async def test_neither_raises_value_error(self):
        with pytest.raises(ValueError, match="No transcript or slide data"):
            await align_content(None, None)

    @pytest.mark.asyncio
    async def test_both_empty_raises_value_error(self):
        with pytest.raises(ValueError, match="No transcript or slide data"):
            await align_content([], [])

    @pytest.mark.asyncio
    async def test_gemini_failure_falls_back_to_heuristic(self):
        mock_client = MagicMock()
        mock_client.aio.models.generate_content = AsyncMock(
            side_effect=RuntimeError("API error")
        )

        with patch(
            "lecturelink_api.agents.content_aligner.genai.Client",
            return_value=mock_client,
        ):
            result = await align_content(SAMPLE_TRANSCRIPT, SAMPLE_SLIDES)

        assert len(result) == 4
        for seg in result:
            assert seg["source"] == "aligned"
            assert seg["slide_number"] is not None

    @pytest.mark.asyncio
    async def test_default_speaker(self):
        """Segments without speaker field default to 'professor'."""
        transcript = [{"start": 0.0, "end": 10.0, "text": "Hello"}]
        result = await align_content(transcript, None)
        assert result[0]["speaker"] == "professor"


# ---------------------------------------------------------------------------
# _heuristic_align
# ---------------------------------------------------------------------------


class TestHeuristicAlign:
    def test_distributes_evenly(self):
        """4 segments over 120s with 3 slides → ~40s per slide."""
        result = _heuristic_align(SAMPLE_TRANSCRIPT, SAMPLE_SLIDES)

        assert len(result) == 4
        # First segment (0.0s) → slide 1
        assert result[0]["slide_number"] == 1
        # Second segment (15.5s) → slide 1 (15.5/40 = 0.38 → idx 0)
        assert result[1]["slide_number"] == 1
        # Third segment (45.2s) → slide 2 (45.2/40 = 1.13 → idx 1)
        assert result[2]["slide_number"] == 2
        # Fourth segment (90.0s) → slide 3 (90/40 = 2.25 → idx 2)
        assert result[3]["slide_number"] == 3

    def test_all_segments_get_aligned_source(self):
        result = _heuristic_align(SAMPLE_TRANSCRIPT, SAMPLE_SLIDES)
        for seg in result:
            assert seg["source"] == "aligned"

    def test_empty_transcript_returns_empty(self):
        assert _heuristic_align([], SAMPLE_SLIDES) == []

    def test_empty_slides_returns_raw_transcript(self):
        """With no slides to align to, returns raw transcript as-is."""
        result = _heuristic_align(SAMPLE_TRANSCRIPT, [])
        assert len(result) == len(SAMPLE_TRANSCRIPT)

    def test_single_slide(self):
        """All segments map to the single slide."""
        one_slide = [SAMPLE_SLIDES[0]]
        result = _heuristic_align(SAMPLE_TRANSCRIPT, one_slide)
        for seg in result:
            assert seg["slide_number"] == 1

    def test_zero_duration_uses_fallback(self):
        """When all segments have start=0, uses 60s default per slide."""
        zero_transcript = [
            {"start": 0, "end": 0, "text": "Test", "speaker": "professor"}
        ]
        result = _heuristic_align(zero_transcript, SAMPLE_SLIDES)
        assert len(result) == 1
        assert result[0]["slide_number"] == 1


# ---------------------------------------------------------------------------
# validate_alignment
# ---------------------------------------------------------------------------


class TestValidateAlignment:
    def test_valid_data_passes_through(self):
        result = validate_alignment(ALIGNED_RESPONSE, total_slides=3)
        assert len(result) == 4
        assert result[0]["slide_number"] == 1
        assert result[3]["slide_number"] == 3

    def test_clamps_slide_number_too_high(self):
        segments = [
            {"start": 0.0, "end": 10.0, "text": "Test", "slide_number": 99}
        ]
        result = validate_alignment(segments, total_slides=5)
        assert result[0]["slide_number"] == 5

    def test_clamps_slide_number_too_low(self):
        segments = [
            {"start": 0.0, "end": 10.0, "text": "Test", "slide_number": 0}
        ]
        result = validate_alignment(segments, total_slides=5)
        assert result[0]["slide_number"] == 1

    def test_clamps_negative_slide_number(self):
        segments = [
            {"start": 0.0, "end": 10.0, "text": "Test", "slide_number": -3}
        ]
        result = validate_alignment(segments, total_slides=5)
        assert result[0]["slide_number"] == 1

    def test_none_slide_number_preserved(self):
        segments = [
            {"start": 0.0, "end": 10.0, "text": "Test", "slide_number": None}
        ]
        result = validate_alignment(segments, total_slides=5)
        assert result[0]["slide_number"] is None

    def test_missing_fields_get_defaults(self):
        segments = [{"text": "Just text"}]
        result = validate_alignment(segments, total_slides=3)
        assert result[0]["start"] is None
        assert result[0]["end"] is None
        assert result[0]["speaker"] == "professor"
        assert result[0]["source"] == "aligned"
        assert result[0]["slide_number"] is None


# ---------------------------------------------------------------------------
# _slide_to_text
# ---------------------------------------------------------------------------


class TestSlideToText:
    def test_full_slide(self):
        slide = {
            "slide_number": 2,
            "title": "Energy Transfer",
            "text_content": "Heat and work are forms of energy transfer",
            "visual_description": "Diagram of heat engine cycle",
        }
        text = _slide_to_text(slide)
        assert "[Slide 2: Energy Transfer]" in text
        assert "Heat and work are forms of energy transfer" in text
        assert "[Visual: Diagram of heat engine cycle]" in text

    def test_slide_without_title(self):
        slide = {
            "slide_number": 5,
            "title": None,
            "text_content": "Some content",
            "visual_description": None,
        }
        text = _slide_to_text(slide)
        assert "[Slide 5:" not in text
        assert "Some content" in text

    def test_slide_without_any_content(self):
        slide = {
            "slide_number": 1,
            "title": None,
            "text_content": "",
            "visual_description": None,
        }
        text = _slide_to_text(slide)
        assert text == "[Slide 1]"

    def test_slide_with_visual_only(self):
        slide = {
            "slide_number": 3,
            "title": None,
            "text_content": "",
            "visual_description": "Complex flowchart",
        }
        text = _slide_to_text(slide)
        assert "[Visual: Complex flowchart]" in text
