"""Tests for the background task runner with retry logic."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

from lecturelink_api.pipeline.background import MAX_RETRIES, run_lecture_processing
from lecturelink_api.pipeline.lecture_processor import LectureProcessingError

_MOD = "lecturelink_api.pipeline.background"

LECTURE_ID = "lec-0001"
COURSE_ID = "course-0001"
USER_ID = "user-0001"
FILE_URLS = ["https://storage.example.com/lecture.mp3"]
SUPABASE_URL = "https://test.supabase.co"
SUPABASE_KEY = "test-anon-key"
USER_TOKEN = "test-jwt-token"


def _mock_create_client():
    """Return a mock create_client that produces a mock Supabase client."""
    sb = MagicMock()
    sb.auth.set_session = MagicMock()
    return patch(f"{_MOD}.create_client", return_value=sb), sb


# ---------------------------------------------------------------------------
# Test: Successful processing
# ---------------------------------------------------------------------------


class TestSuccessfulProcessing:
    def test_returns_result_on_success(self):
        expected = {
            "lecture_id": LECTURE_ID,
            "chunks_stored": 10,
            "concepts_stored": 5,
            "concept_links_created": 3,
            "processing_path": "audio_only",
            "duration_seconds": 12.5,
        }

        patch_cc, _ = _mock_create_client()
        with patch_cc, \
             patch(f"{_MOD}.process_lecture", AsyncMock(return_value=expected)):
            result = run_lecture_processing(
                supabase_url=SUPABASE_URL,
                supabase_key=SUPABASE_KEY,
                user_token=USER_TOKEN,
                lecture_id=LECTURE_ID,
                course_id=COURSE_ID,
                user_id=USER_ID,
                file_urls=FILE_URLS,
            )

        assert result == expected

    def test_calls_process_lecture_with_correct_args(self):
        mock_process = AsyncMock(return_value={"lecture_id": LECTURE_ID})

        patch_cc, sb = _mock_create_client()
        with patch_cc, \
             patch(f"{_MOD}.process_lecture", mock_process):
            run_lecture_processing(
                supabase_url=SUPABASE_URL,
                supabase_key=SUPABASE_KEY,
                user_token=USER_TOKEN,
                lecture_id=LECTURE_ID,
                course_id=COURSE_ID,
                user_id=USER_ID,
                file_urls=FILE_URLS,
                is_reprocess=True,
            )

        mock_process.assert_called_once_with(
            supabase=sb,
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
    def test_retries_on_failure_then_succeeds(self):
        expected = {"lecture_id": LECTURE_ID, "chunks_stored": 5}

        mock_process = AsyncMock(
            side_effect=[
                LectureProcessingError("timeout", "content_processing"),
                expected,
            ]
        )

        patch_cc, _ = _mock_create_client()
        with patch_cc, \
             patch(f"{_MOD}.process_lecture", mock_process), \
             patch(f"{_MOD}.asyncio.sleep", AsyncMock()):
            result = run_lecture_processing(
                supabase_url=SUPABASE_URL,
                supabase_key=SUPABASE_KEY,
                user_token=USER_TOKEN,
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

    def test_all_retries_exhausted_returns_none(self):
        mock_process = AsyncMock(
            side_effect=LectureProcessingError("persistent error", "unknown")
        )

        patch_cc, _ = _mock_create_client()
        with patch_cc, \
             patch(f"{_MOD}.process_lecture", mock_process), \
             patch(f"{_MOD}.asyncio.sleep", AsyncMock()):
            result = run_lecture_processing(
                supabase_url=SUPABASE_URL,
                supabase_key=SUPABASE_KEY,
                user_token=USER_TOKEN,
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
    def test_backoff_durations(self):
        mock_process = AsyncMock(
            side_effect=LectureProcessingError("fail", "unknown")
        )
        sleep_calls = []

        async def mock_sleep(seconds):
            sleep_calls.append(seconds)

        patch_cc, _ = _mock_create_client()
        with patch_cc, \
             patch(f"{_MOD}.process_lecture", mock_process), \
             patch(f"{_MOD}.asyncio.sleep", side_effect=mock_sleep):
            run_lecture_processing(
                supabase_url=SUPABASE_URL,
                supabase_key=SUPABASE_KEY,
                user_token=USER_TOKEN,
                lecture_id=LECTURE_ID,
                course_id=COURSE_ID,
                user_id=USER_ID,
                file_urls=FILE_URLS,
            )

        # Backoff: 2^1=2, 2^2=4, 2^3=8
        assert sleep_calls == [2, 4, 8]

    def test_no_sleep_on_success(self):
        mock_process = AsyncMock(return_value={"lecture_id": LECTURE_ID})
        mock_sleep = AsyncMock()

        patch_cc, _ = _mock_create_client()
        with patch_cc, \
             patch(f"{_MOD}.process_lecture", mock_process), \
             patch(f"{_MOD}.asyncio.sleep", mock_sleep):
            run_lecture_processing(
                supabase_url=SUPABASE_URL,
                supabase_key=SUPABASE_KEY,
                user_token=USER_TOKEN,
                lecture_id=LECTURE_ID,
                course_id=COURSE_ID,
                user_id=USER_ID,
                file_urls=FILE_URLS,
            )

        mock_sleep.assert_not_called()
