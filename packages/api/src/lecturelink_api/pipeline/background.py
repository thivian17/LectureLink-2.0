"""Background task runner for lecture processing with retry logic."""

from __future__ import annotations

import asyncio
import logging

from .lecture_processor import LectureProcessingError, process_lecture

logger = logging.getLogger(__name__)

MAX_RETRIES = 3


async def run_lecture_processing(
    supabase,
    lecture_id: str,
    course_id: str,
    user_id: str,
    file_urls: list[str],
    is_reprocess: bool = False,
) -> dict | None:
    """Background task for lecture processing with exponential backoff retries.

    Called by FastAPI's BackgroundTasks or an async task queue.

    Args:
        supabase: Supabase client.
        lecture_id: The lecture UUID.
        course_id: The course UUID.
        user_id: The owner user UUID.
        file_urls: List of uploaded file URLs.
        is_reprocess: If True, clean up existing data first.

    Returns:
        Result dict on success, None if all retries exhausted.
    """
    retry_count = 0

    while retry_count <= MAX_RETRIES:
        try:
            result = await process_lecture(
                supabase=supabase,
                lecture_id=lecture_id,
                course_id=course_id,
                user_id=user_id,
                file_urls=file_urls,
                is_reprocess=is_reprocess or (retry_count > 0),
            )
            logger.info("Lecture %s processed successfully: %s", lecture_id, result)
            return result

        except LectureProcessingError as e:
            retry_count += 1
            if retry_count > MAX_RETRIES:
                logger.error(
                    "Lecture %s failed after %d retries: %s",
                    lecture_id, MAX_RETRIES, e,
                )
                return None

            backoff = 2 ** retry_count  # 2, 4, 8 seconds
            logger.warning(
                "Lecture %s failed (attempt %d), retrying in %ds: %s",
                lecture_id, retry_count, backoff, e,
            )
            await asyncio.sleep(backoff)

    return None
