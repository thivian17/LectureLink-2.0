"""Background task runner for lecture processing with retry logic.

IMPORTANT: ``run_lecture_processing`` is a **sync** function so that
FastAPI's ``BackgroundTasks`` runs it in a thread-pool instead of the
main async event loop.  The processing pipeline mixes truly-async calls
(Gemini API, httpx downloads) with sync calls (supabase-py DB/storage),
and the sync calls would block the event loop and freeze the entire
server if run on it directly.  By running in a thread with its own
event loop we keep the main loop free to serve HTTP requests.
"""

from __future__ import annotations

import asyncio
import logging
import time

from supabase import create_client

from .lecture_processor import LectureProcessingError, process_lecture

logger = logging.getLogger(__name__)

MAX_RETRIES = 3


def run_lecture_processing(
    supabase_url: str,
    supabase_key: str,
    user_token: str,
    lecture_id: str,
    course_id: str,
    user_id: str,
    file_urls: list[str],
    is_reprocess: bool = False,
) -> dict | None:
    """Background task for lecture processing with exponential backoff retries.

    This is a **sync** function on purpose — FastAPI will run it in a
    thread-pool worker, keeping the main event loop responsive.  A
    private event loop is created for the async pipeline stages.

    Args:
        supabase_url: Supabase project URL.
        supabase_key: Supabase anon key.
        user_token: JWT access token for the requesting user.
        lecture_id: The lecture UUID.
        course_id: The course UUID.
        user_id: The owner user UUID.
        file_urls: List of uploaded file URLs.
        is_reprocess: If True, clean up existing data first.

    Returns:
        Result dict on success, None if all retries exhausted.
    """
    # Create a fresh Supabase client for this thread
    sb = create_client(supabase_url, supabase_key)
    sb.auth.set_session(user_token, "")

    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(
            _processing_loop(
                sb, lecture_id, course_id, user_id,
                file_urls, is_reprocess,
            )
        )
    finally:
        loop.close()


async def _processing_loop(
    supabase,
    lecture_id: str,
    course_id: str,
    user_id: str,
    file_urls: list[str],
    is_reprocess: bool,
) -> dict | None:
    """Async retry loop executed inside the background thread's event loop."""
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
