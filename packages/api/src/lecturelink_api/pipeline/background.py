"""Background task runner for lecture processing with retry logic.

Provides both sync (thread-based) and async entry points:
- ``run_lecture_processing`` — sync, for thread-pool fallback when Redis is unavailable
- ``run_lecture_processing_async`` — async, called directly by arq workers
"""

from __future__ import annotations

import asyncio
import logging

from supabase import create_client

from ..services.lecture_storage import cleanup_lecture_data
from .lecture_processor import LectureProcessingError, process_lecture

logger = logging.getLogger(__name__)

MAX_RETRIES = 3


async def run_lecture_processing_async(
    supabase_url: str,
    supabase_key: str,
    user_token: str,
    lecture_id: str,
    course_id: str,
    user_id: str,
    file_urls: list[str],
    is_reprocess: bool = False,
) -> dict | None:
    """Async entry point for lecture processing (used by arq worker).

    The arq worker already has an event loop — no need for manual
    ``asyncio.new_event_loop()`` gymnastics.
    """
    sb = create_client(supabase_url, supabase_key)
    if user_token:
        sb.auth.set_session(user_token, "")

    return await _processing_loop(
        sb, lecture_id, course_id, user_id, file_urls, is_reprocess,
    )


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
    """Sync fallback for lecture processing (runs in a daemon thread).

    Creates a private event loop for the async pipeline stages.
    Used when Redis/arq is unavailable.
    """
    loop = asyncio.new_event_loop()
    try:
        sb = create_client(supabase_url, supabase_key)
        if user_token:
            sb.auth.set_session(user_token, "")

        return loop.run_until_complete(
            _processing_loop(
                sb, lecture_id, course_id, user_id,
                file_urls, is_reprocess,
            )
        )
    except Exception:
        logger.exception(
            "Lecture %s: daemon thread crashed", lecture_id,
        )
        # Clean up the failed lecture so it doesn't stay in the user's list
        try:
            sb_fallback = create_client(supabase_url, supabase_key)
            _delete_failed_lecture(sb_fallback, lecture_id)
        except Exception:
            logger.exception(
                "Lecture %s: also failed to clean up after crash",
                lecture_id,
            )
        return None
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
    """Async retry loop with exponential backoff."""
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
            # If the lecture was deleted, retrying is pointless
            if e.stage == "pre_check":
                logger.warning(
                    "Lecture %s was deleted — skipping retries", lecture_id,
                )
                return None

            retry_count += 1
            if retry_count > MAX_RETRIES:
                logger.error(
                    "Lecture %s failed after %d retries: %s",
                    lecture_id, MAX_RETRIES, e,
                )
                _delete_failed_lecture(supabase, lecture_id)
                return None

            backoff = 2 ** retry_count  # 2, 4, 8 seconds
            logger.warning(
                "Lecture %s failed (attempt %d), retrying in %ds: %s",
                lecture_id, retry_count, backoff, e,
            )
            await asyncio.sleep(backoff)

        except Exception:
            # Unexpected error — don't retry, clean up and let it propagate.
            logger.exception(
                "Lecture %s: unexpected error in processing loop", lecture_id,
            )
            _delete_failed_lecture(supabase, lecture_id)
            raise

    return None


def _delete_failed_lecture(supabase, lecture_id: str) -> None:
    """Remove a permanently-failed lecture and its associated data.

    Cleans up chunks/concepts, storage files, and the lecture row itself
    so the user isn't left with a dead entry in their lectures list.
    """
    try:
        # 1. Clean up chunks and concepts
        cleanup_lecture_data(supabase, lecture_id)

        # 2. Fetch storage paths before deleting the row
        lecture_row = (
            supabase.table("lectures")
            .select("audio_url, slides_url")
            .eq("id", lecture_id)
            .execute()
        )
        storage_paths = []
        if lecture_row.data:
            for key in ("audio_url", "slides_url"):
                path = lecture_row.data[0].get(key)
                if path:
                    storage_paths.append(path)

        # 3. Delete the lecture row
        supabase.table("lectures").delete().eq("id", lecture_id).execute()

        # 4. Clean up storage files (best-effort)
        for path in storage_paths:
            try:
                supabase.storage.from_("lectures").remove([path])
            except Exception:
                logger.warning(
                    "Failed to remove storage file %s for lecture %s",
                    path, lecture_id,
                )

        logger.info(
            "Deleted permanently-failed lecture %s and its storage files",
            lecture_id,
        )
    except Exception:
        logger.exception(
            "Failed to clean up lecture %s after permanent failure",
            lecture_id,
        )
