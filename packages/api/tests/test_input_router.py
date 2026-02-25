"""Tests for the input router module."""

from __future__ import annotations

import pytest
from lecturelink_api.agents.input_router import (
    route_input,
)


class TestRouteInputAudioOnly:
    """Audio-only routing scenarios."""

    async def test_mp3(self):
        result = await route_input(["https://storage.example.com/lecture.mp3"])
        assert result.processing_path == "audio_only"
        assert result.audio_url == "https://storage.example.com/lecture.mp3"
        assert result.slides_url is None

    async def test_wav(self):
        result = await route_input(["https://storage.example.com/lecture.wav"])
        assert result.processing_path == "audio_only"
        assert result.audio_url.endswith(".wav")

    async def test_m4a(self):
        result = await route_input(["https://storage.example.com/lecture.m4a"])
        assert result.processing_path == "audio_only"

    async def test_ogg(self):
        result = await route_input(["/local/path/lecture.ogg"])
        assert result.processing_path == "audio_only"

    async def test_webm(self):
        result = await route_input(["/local/path/lecture.webm"])
        assert result.processing_path == "audio_only"

    async def test_flac(self):
        result = await route_input(["/local/path/lecture.flac"])
        assert result.processing_path == "audio_only"


class TestRouteInputSlidesOnly:
    """Slides-only routing scenarios."""

    async def test_pdf(self):
        result = await route_input(["https://storage.example.com/slides.pdf"])
        assert result.processing_path == "slides_only"
        assert result.slides_url == "https://storage.example.com/slides.pdf"
        assert result.audio_url is None

    async def test_pptx(self):
        result = await route_input(["https://storage.example.com/slides.pptx"])
        assert result.processing_path == "slides_only"
        assert result.slides_url.endswith(".pptx")


class TestRouteInputAudioPlusSlides:
    """Combined audio + slides routing."""

    async def test_mp3_and_pdf(self):
        result = await route_input([
            "https://storage.example.com/lecture.mp3",
            "https://storage.example.com/slides.pdf",
        ])
        assert result.processing_path == "audio+slides"
        assert result.audio_url.endswith(".mp3")
        assert result.slides_url.endswith(".pdf")

    async def test_wav_and_pptx(self):
        result = await route_input([
            "/local/lecture.wav",
            "/local/slides.pptx",
        ])
        assert result.processing_path == "audio+slides"
        assert result.audio_url is not None
        assert result.slides_url is not None


class TestRouteInputRejections:
    """Rejection / error scenarios."""

    async def test_empty_list(self):
        with pytest.raises(ValueError, match="No files provided"):
            await route_input([])

    async def test_unsupported_docx(self):
        with pytest.raises(ValueError, match="Unsupported file format"):
            await route_input(["https://example.com/notes.docx"])

    async def test_unsupported_txt(self):
        with pytest.raises(ValueError, match="Unsupported file format"):
            await route_input(["notes.txt"])

    async def test_unsupported_jpg(self):
        with pytest.raises(ValueError, match="Unsupported file format"):
            await route_input(["photo.jpg"])

    async def test_multiple_audio_files(self):
        with pytest.raises(ValueError, match="single audio file"):
            await route_input([
                "https://storage.example.com/part1.mp3",
                "https://storage.example.com/part2.mp3",
            ])

    async def test_multiple_audio_with_slides_still_errors(self):
        with pytest.raises(ValueError, match="single audio file"):
            await route_input([
                "lecture1.mp3",
                "lecture2.wav",
                "slides.pdf",
            ])


class TestRouteInputCaseInsensitive:
    """Extension matching should be case-insensitive."""

    async def test_uppercase_mp3(self):
        result = await route_input(["https://example.com/LECTURE.MP3"])
        assert result.processing_path == "audio_only"

    async def test_mixed_case_pdf(self):
        result = await route_input(["https://example.com/Slides.Pdf"])
        assert result.processing_path == "slides_only"

    async def test_uppercase_pptx(self):
        result = await route_input(["https://example.com/slides.PPTX"])
        assert result.processing_path == "slides_only"


class TestRouteResultModel:
    """Verify the returned object is a proper RouteResult model."""

    async def test_returns_route_result_type(self):
        from lecturelink_api.models.lecture_models import RouteResult

        result = await route_input(["lecture.mp3"])
        assert isinstance(result, RouteResult)

    async def test_estimated_duration_defaults_none(self):
        result = await route_input(["lecture.mp3"])
        assert result.estimated_duration is None
