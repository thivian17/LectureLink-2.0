"""Tests for the background task runner with retry logic."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from lecturelink_api.pipeline.background import MAX_RETRIES, run_lecture_processing
from lecturelink_api.pipeline.lecture_processor import LectureProcessingError

_MOD = "lecturelink_api.pipeline.background"

LECTURE_ID = "lec-0001"
COURSE_ID = "course-0001"
USER_ID = "user-0001"
FILE_URLS = ["https://storage.example.com/lecture.mp3"]


# ---------------------------------------------------------------------------
# Test: Successful processing
# ---------------------------------------------------------------------------


class TestSuccessfulProcessing:
    @pytest.mark.asyncio
    async def test_returns_result_on_success(self):
        expected = {
            "lecture_id": LECTURE_ID,
            "chunks_stored": 10,
            "concepts_stored": 5,
            "concept_links_created": 3,
            "processing_path": "audio_only",
            "duration_seconds": 12.5,
        }

        with patch(f"{_MOD}.process_lecture", AsyncMock(return_value=expected)):
            result = await run_lecture_processing(
                supabase=None,
                lecture_id=LECTURE_ID,
                course_id=COURSE_ID,
                user_id=USER_ID,
                file_urls=FILE_URLS,
            )

        assert result == expected

    @pytest.mark.asyncio
    async def test_calls_process_lecture_with_correct_args(self):
        mock_process = AsyncMock(return_value={"lecture_id": LECTURE_ID})

        with patch(f"{_MOD}.process_lecture", mock_process):
            await run_lecture_processing(
                supabase="sb_client",
                lecture_id=LECTURE_ID,
                course_id=COURSE_ID,
                user_id=USER_ID,
                file_urls=FILE_URLS,
                is_reprocess=True,
            )

        mock_process.assert_called_once_with(
            supabase="sb_client",
            lecture_id=LECTURE_ID,
            course_id=COURSE_ID,
            user_id=USER_ID,
            file_urls=FILE_URLS,
            is_reprocess=True,
        )


# ---------------------------------------------------------------------------
# Test: Retry on failure
# ---------------------------------------------------------------------------


class TestRetryBehavior:
    @pytest.mark.asyncio
    async def test_retries_on_failure_then_succeeds(self):
        expected = {"lecture_id": LECTURE_ID, "chunks_stored": 5}

        mock_process = AsyncMock(
            side_effect=[
                LectureProcessingError("timeout", "content_processing"),
                expected,
            ]
        )

        with patch(f"{_MOD}.process_lecture", mock_process), \
             patch(f"{_MOD}.asyncio.sleep", AsyncMock()):
            result = await run_lecture_processing(
                supabase=None,
                lecture_id=LECTURE_ID,
                course_id=COURSE_ID,
                user_id=USER_ID,
                file_urls=FILE_URLS,
            )

        assert result == expected
        assert mock_process.call_count == 2

        # Second call should have is_reprocess=True (retry_count > 0)
        second_call = mock_process.call_args_list[1]
        assert second_call[1]["is_reprocess"] is True

    @pytest.mark.asyncio
    async def test_all_retries_exhausted_returns_none(self):
        mock_process = AsyncMock(
            side_effect=LectureProcessingError("persistent error", "unknown")
        )

        with patch(f"{_MOD}.process_lecture", mock_process), \
             patch(f"{_MOD}.asyncio.sleep", AsyncMock()):
            result = await run_lecture_processing(
                supabase=None,
                lecture_id=LECTURE_ID,
                course_id=COURSE_ID,
                user_id=USER_ID,
                file_urls=FILE_URLS,
            )

        assert result is None
        # 1 initial + MAX_RETRIES retries = MAX_RETRIES + 1 calls
        assert mock_process.call_count == MAX_RETRIES + 1


# ---------------------------------------------------------------------------
# Test: Exponential backoff
# ---------------------------------------------------------------------------


class TestExponentialBackoff:
    @pytest.mark.asyncio
    async def test_backoff_durations(self):
        mock_process = AsyncMock(
            side_effect=LectureProcessingError("fail", "unknown")
        )
        sleep_calls = []

        async def mock_sleep(seconds):
            sleep_calls.append(seconds)

        with patch(f"{_MOD}.process_lecture", mock_process), \
             patch(f"{_MOD}.asyncio.sleep", side_effect=mock_sleep):
            await run_lecture_processing(
                supabase=None,
                lecture_id=LECTURE_ID,
                course_id=COURSE_ID,
                user_id=USER_ID,
                file_urls=FILE_URLS,
            )

        # Backoff: 2^1=2, 2^2=4, 2^3=8
        assert sleep_calls == [2, 4, 8]

    @pytest.mark.asyncio
    async def test_no_sleep_on_success(self):
        mock_process = AsyncMock(return_value={"lecture_id": LECTURE_ID})
        mock_sleep = AsyncMock()

        with patch(f"{_MOD}.process_lecture", mock_process), \
             patch(f"{_MOD}.asyncio.sleep", mock_sleep):
            await run_lecture_processing(
                supabase=None,
                lecture_id=LECTURE_ID,
                course_id=COURSE_ID,
                user_id=USER_ID,
                file_urls=FILE_URLS,
            )

        mock_sleep.assert_not_called()
