"""Tests for the audio transcriber module."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, AsyncMock, patch

import pytest
from lecturelink_api.agents.audio_transcriber import (
    MIME_MAP,
    TranscriptionError,
    _strip_markdown_fences,
    get_audio_mime_type,
    transcribe_audio,
    validate_transcript,
)


# ---------------------------------------------------------------------------
# validate_transcript
# ---------------------------------------------------------------------------


class TestValidateTranscript:
    """Tests for the validate_transcript helper."""

    def test_valid_segments_returned(self):
        segments = [
            {"start": 0.0, "end": 10.0, "text": "Hello world", "speaker": "professor"},
            {"start": 10.0, "end": 25.0, "text": "Second segment", "speaker": "professor"},
        ]
        result = validate_transcript(segments)
        assert len(result) == 2
        assert result[0]["text"] == "Hello world"
        assert result[1]["start"] == 10.0

    def test_missing_fields_skipped(self):
        segments = [
            {"start": 0.0, "end": 10.0, "text": "Valid"},
            {"start": 10.0, "text": "Missing end"},  # missing 'end'
            {"end": 20.0, "text": "Missing start"},  # missing 'start'
            {"start": 20.0, "end": 30.0},  # missing 'text'
        ]
        result = validate_transcript(segments)
        assert len(result) == 1
        assert result[0]["text"] == "Valid"

    def test_overlapping_timestamps_fixed(self):
        segments = [
            {"start": 0.0, "end": 15.0, "text": "First"},
            {"start": 10.0, "end": 25.0, "text": "Overlaps first"},  # start < prev end
        ]
        result = validate_transcript(segments)
        assert len(result) == 2
        # Second segment start should be bumped to first segment's end
        assert result[1]["start"] == 15.0
        assert result[1]["end"] == 25.0

    def test_empty_text_filtered(self):
        segments = [
            {"start": 0.0, "end": 10.0, "text": "   "},
            {"start": 10.0, "end": 20.0, "text": ""},
            {"start": 20.0, "end": 30.0, "text": "Real text"},
        ]
        result = validate_transcript(segments)
        assert len(result) == 1
        assert result[0]["text"] == "Real text"

    def test_end_before_start_fixed(self):
        segments = [
            {"start": 10.0, "end": 5.0, "text": "End before start"},
        ]
        result = validate_transcript(segments)
        assert len(result) == 1
        assert result[0]["end"] == result[0]["start"] + 1.0

    def test_default_speaker(self):
        segments = [
            {"start": 0.0, "end": 10.0, "text": "No speaker field"},
        ]
        result = validate_transcript(segments)
        assert result[0]["speaker"] == "professor"

    def test_non_dict_segments_skipped(self):
        segments = [
            "not a dict",
            42,
            {"start": 0.0, "end": 10.0, "text": "Valid segment"},
        ]
        result = validate_transcript(segments)
        assert len(result) == 1

    def test_non_numeric_timestamps_skipped(self):
        segments = [
            {"start": "abc", "end": 10.0, "text": "Bad start"},
            {"start": 0.0, "end": "xyz", "text": "Bad end"},
            {"start": 0.0, "end": 10.0, "text": "Good"},
        ]
        result = validate_transcript(segments)
        assert len(result) == 1
        assert result[0]["text"] == "Good"

    def test_empty_input(self):
        assert validate_transcript([]) == []

    def test_monotonically_decreasing_timestamps(self):
        """Segments with decreasing starts should be fixed via overlap correction."""
        segments = [
            {"start": 50.0, "end": 60.0, "text": "First"},
            {"start": 30.0, "end": 40.0, "text": "Goes backward"},
            {"start": 20.0, "end": 25.0, "text": "Even further back"},
        ]
        result = validate_transcript(segments)
        assert len(result) == 3
        # Each subsequent segment should start at or after the previous end
        for i in range(1, len(result)):
            assert result[i]["start"] >= result[i - 1]["end"]


# ---------------------------------------------------------------------------
# get_audio_mime_type
# ---------------------------------------------------------------------------


class TestGetAudioMimeType:
    """MIME type detection for all supported formats."""

    @pytest.mark.parametrize(
        "ext,expected_mime",
        [
            (".mp3", "audio/mpeg"),
            (".wav", "audio/wav"),
            (".m4a", "audio/mp4"),
            (".ogg", "audio/ogg"),
            (".webm", "audio/webm"),
            (".flac", "audio/flac"),
        ],
    )
    def test_known_formats(self, ext, expected_mime):
        assert get_audio_mime_type(f"/path/to/file{ext}") == expected_mime

    def test_unknown_extension_defaults_to_mpeg(self):
        assert get_audio_mime_type("/path/to/file.xyz") == "audio/mpeg"

    def test_case_insensitive(self):
        assert get_audio_mime_type("/path/to/file.MP3") == "audio/mpeg"

    def test_url_path(self):
        assert get_audio_mime_type("https://storage.example.com/audio.flac") == "audio/flac"


# ---------------------------------------------------------------------------
# _strip_markdown_fences
# ---------------------------------------------------------------------------


class TestStripMarkdownFences:
    """Removing markdown code fences from Gemini responses."""

    def test_no_fences(self):
        assert _strip_markdown_fences('[{"start": 0}]') == '[{"start": 0}]'

    def test_json_fences(self):
        text = '```json\n[{"start": 0}]\n```'
        assert _strip_markdown_fences(text) == '[{"start": 0}]'

    def test_plain_fences(self):
        text = '```\n[{"start": 0}]\n```'
        assert _strip_markdown_fences(text) == '[{"start": 0}]'

    def test_whitespace_padding(self):
        text = '  ```json\n[{"start": 0}]\n```  '
        assert _strip_markdown_fences(text) == '[{"start": 0}]'


# ---------------------------------------------------------------------------
# transcribe_audio (mocked Gemini)
# ---------------------------------------------------------------------------


def _make_mock_client(response_text: str) -> MagicMock:
    """Create a mock genai.Client that returns the given text."""
    client = MagicMock()
    mock_response = MagicMock()
    mock_response.text = response_text
    client.models.generate_content.return_value = mock_response
    client.files.upload.return_value = MagicMock(uri="gs://fake/uploaded")
    return client


class TestTranscribeAudio:
    """Integration-style tests with a mocked Gemini client."""

    async def test_successful_transcription(self, tmp_path):
        audio_file = tmp_path / "lecture.mp3"
        audio_file.write_bytes(b"\x00" * 100)

        transcript_data = [
            {"start": 0.0, "end": 10.0, "text": "Welcome to the lecture.", "speaker": "professor"},
            {"start": 10.0, "end": 25.0, "text": "Today's topic is AI.", "speaker": "professor"},
        ]
        client = _make_mock_client(json.dumps(transcript_data))

        result = await transcribe_audio(str(audio_file), client=client)

        assert len(result) == 2
        assert result[0]["text"] == "Welcome to the lecture."
        client.models.generate_content.assert_called_once()

    async def test_markdown_wrapped_json(self, tmp_path):
        audio_file = tmp_path / "lecture.wav"
        audio_file.write_bytes(b"\x00" * 100)

        transcript_data = [
            {"start": 0.0, "end": 15.0, "text": "Hello class.", "speaker": "professor"},
        ]
        wrapped = f"```json\n{json.dumps(transcript_data)}\n```"
        client = _make_mock_client(wrapped)

        result = await transcribe_audio(str(audio_file), client=client)
        assert len(result) == 1
        assert result[0]["text"] == "Hello class."

    async def test_invalid_json_raises_error(self, tmp_path):
        audio_file = tmp_path / "lecture.mp3"
        audio_file.write_bytes(b"\x00" * 100)

        client = _make_mock_client("This is not JSON at all")

        with pytest.raises(TranscriptionError, match="Failed to parse transcript JSON"):
            await transcribe_audio(str(audio_file), client=client)

    async def test_file_not_found_raises_error(self):
        with pytest.raises(TranscriptionError, match="Audio file not found"):
            await transcribe_audio("/nonexistent/path/audio.mp3", client=MagicMock())

    async def test_retry_on_transient_failure(self, tmp_path):
        audio_file = tmp_path / "lecture.mp3"
        audio_file.write_bytes(b"\x00" * 100)

        transcript_data = [
            {"start": 0.0, "end": 10.0, "text": "Success after retry.", "speaker": "professor"},
        ]

        client = MagicMock()
        client.files.upload.return_value = MagicMock(uri="gs://fake/uploaded")

        # First call raises, second succeeds
        mock_success = MagicMock()
        mock_success.text = json.dumps(transcript_data)
        client.models.generate_content.side_effect = [
            RuntimeError("Transient Gemini error"),
            mock_success,
        ]

        with patch("lecturelink_api.agents.audio_transcriber.asyncio.sleep", new_callable=AsyncMock):
            result = await transcribe_audio(str(audio_file), client=client)

        assert len(result) == 1
        assert result[0]["text"] == "Success after retry."
        assert client.models.generate_content.call_count == 2

    async def test_all_retries_exhausted(self, tmp_path):
        audio_file = tmp_path / "lecture.mp3"
        audio_file.write_bytes(b"\x00" * 100)

        client = MagicMock()
        client.files.upload.return_value = MagicMock(uri="gs://fake/uploaded")
        client.models.generate_content.side_effect = RuntimeError("Persistent failure")

        with patch("lecturelink_api.agents.audio_transcriber.asyncio.sleep", new_callable=AsyncMock):
            with pytest.raises(TranscriptionError, match="Audio transcription failed"):
                await transcribe_audio(str(audio_file), client=client)

        assert client.models.generate_content.call_count == 3

    async def test_large_file_uses_file_api(self, tmp_path):
        audio_file = tmp_path / "lecture.flac"
        # Write > 20MB to trigger File API upload
        audio_file.write_bytes(b"\x00" * (21 * 1024 * 1024))

        transcript_data = [
            {"start": 0.0, "end": 10.0, "text": "Large file test.", "speaker": "professor"},
        ]
        client = _make_mock_client(json.dumps(transcript_data))

        result = await transcribe_audio(str(audio_file), client=client)
        assert len(result) == 1
        client.files.upload.assert_called_once()

    async def test_small_file_uses_inline_bytes(self, tmp_path):
        audio_file = tmp_path / "lecture.mp3"
        audio_file.write_bytes(b"\x00" * 100)

        transcript_data = [
            {"start": 0.0, "end": 10.0, "text": "Small file.", "speaker": "professor"},
        ]
        client = _make_mock_client(json.dumps(transcript_data))

        result = await transcribe_audio(str(audio_file), client=client)
        assert len(result) == 1
        # File API should NOT be called for small files
        client.files.upload.assert_not_called()


# ---------------------------------------------------------------------------
# Processing status helper
# ---------------------------------------------------------------------------


class TestUpdateProcessingStatus:
    """Tests for the processing status updater."""

    def test_basic_status_update(self, mock_supabase):
        from lecturelink_api.services.processing import update_processing_status

        update_processing_status(mock_supabase, "lecture-123", "processing")

        mock_supabase.table.assert_called_with("lectures")
        mock_supabase.table.return_value.update.assert_called_once()
        call_args = mock_supabase.table.return_value.update.call_args[0][0]
        assert call_args["processing_status"] == "processing"

    def test_status_with_stage_and_progress(self, mock_supabase):
        from lecturelink_api.services.processing import update_processing_status

        update_processing_status(
            mock_supabase,
            "lecture-123",
            "processing",
            stage="transcribing",
            progress=0.15,
        )

        call_args = mock_supabase.table.return_value.update.call_args[0][0]
        assert call_args["processing_status"] == "processing"
        assert call_args["processing_stage"] == "transcribing"
        assert call_args["processing_progress"] == 0.15

    def test_failed_status_with_error(self, mock_supabase):
        from lecturelink_api.services.processing import update_processing_status

        update_processing_status(
            mock_supabase,
            "lecture-123",
            "failed",
            error="Transcription timed out",
        )

        call_args = mock_supabase.table.return_value.update.call_args[0][0]
        assert call_args["processing_status"] == "failed"
        assert call_args["processing_error"] == "Transcription timed out"

    def test_omitted_optional_fields_not_included(self, mock_supabase):
        from lecturelink_api.services.processing import update_processing_status

        update_processing_status(mock_supabase, "lecture-123", "pending")

        call_args = mock_supabase.table.return_value.update.call_args[0][0]
        assert "processing_stage" not in call_args
        assert "processing_progress" not in call_args
        assert "processing_error" not in call_args
