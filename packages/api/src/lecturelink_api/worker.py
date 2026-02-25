"""arq worker — async task execution for background jobs.

Run with: ``arq lecturelink_api.worker.WorkerSettings``
"""

from __future__ import annotations

import logging
import os

from arq.connections import RedisSettings

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Worker lifecycle hooks
# ---------------------------------------------------------------------------


async def on_startup(ctx: dict) -> None:
    """Create shared resources (Supabase client) once per worker process."""
    from supabase import create_client

    from lecturelink_api.config import get_settings

    settings = get_settings()
    ctx["supabase"] = create_client(
        settings.SUPABASE_URL,
        settings.SUPABASE_SERVICE_KEY or settings.SUPABASE_ANON_KEY,
    )
    ctx["settings"] = settings
    logger.info("arq worker started")


async def on_shutdown(ctx: dict) -> None:
    logger.info("arq worker shutting down")


# ---------------------------------------------------------------------------
# Task functions
# ---------------------------------------------------------------------------


async def task_process_lecture(
    ctx: dict,
    *,
    lecture_id: str,
    course_id: str,
    user_id: str,
    file_urls: list[str],
    supabase_url: str = "",
    supabase_key: str = "",
    user_token: str = "",
    is_reprocess: bool = False,
) -> dict | None:
    """Process a lecture through the full pipeline."""
    from lecturelink_api.pipeline.background import run_lecture_processing_async

    logger.info("Processing lecture %s", lecture_id)
    return await run_lecture_processing_async(
        supabase_url=supabase_url or ctx["settings"].SUPABASE_URL,
        supabase_key=supabase_key or ctx["settings"].SUPABASE_ANON_KEY,
        user_token=user_token,
        lecture_id=lecture_id,
        course_id=course_id,
        user_id=user_id,
        file_urls=file_urls,
        is_reprocess=is_reprocess,
    )


async def task_generate_quiz(
    ctx: dict,
    *,
    supabase_url: str = "",
    supabase_key: str = "",
    user_token: str = "",
    quiz_id: str,
    course_id: str,
    user_id: str,
    target_assessment_id: str | None = None,
    lecture_ids: list[str] | None = None,
    num_questions: int = 10,
    difficulty: str = "mixed",
    include_coding: bool = False,
    coding_ratio: float = 0.3,
    coding_language: str = "python",
    coding_only: bool = False,
) -> None:
    """Generate quiz questions via the generator-critic loop."""
    from lecturelink_api.services.quiz import run_quiz_generation_async

    logger.info("Generating quiz %s", quiz_id)
    await run_quiz_generation_async(
        supabase_url=supabase_url or ctx["settings"].SUPABASE_URL,
        supabase_key=supabase_key or ctx["settings"].SUPABASE_ANON_KEY,
        user_token=user_token,
        quiz_id=quiz_id,
        course_id=course_id,
        user_id=user_id,
        target_assessment_id=target_assessment_id,
        lecture_ids=lecture_ids,
        num_questions=num_questions,
        difficulty=difficulty,
        include_coding=include_coding,
        coding_ratio=coding_ratio,
        coding_language=coding_language,
        coding_only=coding_only,
    )


async def task_process_syllabus(
    ctx: dict,
    *,
    syllabus_id: str,
    file_bytes_hex: str,
    file_name: str,
    mime_type: str,
    course_id: str,
    user_id: str,
    supabase_url: str = "",
    supabase_key: str = "",
    user_token: str = "",
) -> None:
    """Process a syllabus upload."""
    from supabase import create_client

    from lecturelink_api.services.syllabus_service import process_syllabus

    logger.info("Processing syllabus %s", syllabus_id)
    sb_url = supabase_url or ctx["settings"].SUPABASE_URL
    sb_key = supabase_key or ctx["settings"].SUPABASE_ANON_KEY
    sb = create_client(sb_url, sb_key)
    if user_token:
        sb.auth.set_session(user_token, "")

    await process_syllabus(
        syllabus_id=syllabus_id,
        file_bytes=bytes.fromhex(file_bytes_hex),
        file_name=file_name,
        mime_type=mime_type,
        course_id=course_id,
        user_id=user_id,
        supabase=sb,
    )


async def task_refresh_user(
    ctx: dict,
    *,
    user_id: str,
) -> None:
    """Refresh study actions for a single user."""
    from lecturelink_api.services.study_actions import get_study_actions

    logger.info("Refreshing study actions for user %s", user_id)
    await get_study_actions(ctx["supabase"], user_id)


async def task_send_notification(
    ctx: dict,
    *,
    user_id: str,
    notification_type: str,
    message: str,
) -> None:
    """Deliver a notification."""
    logger.info(
        "Notification [%s] to user %s: %s",
        notification_type,
        user_id,
        message,
    )


# ---------------------------------------------------------------------------
# Worker settings
# ---------------------------------------------------------------------------


def _redis_settings() -> RedisSettings:
    """Parse REDIS_URL into arq RedisSettings."""
    url = os.environ.get("REDIS_URL", "redis://localhost:6379")
    # arq expects host/port/database — parse from URL
    from urllib.parse import urlparse

    parsed = urlparse(url)
    return RedisSettings(
        host=parsed.hostname or "localhost",
        port=parsed.port or 6379,
        database=int(parsed.path.lstrip("/") or 0),
        password=parsed.password,
    )


class WorkerSettings:
    """arq worker configuration."""

    functions = [
        task_process_lecture,
        task_generate_quiz,
        task_process_syllabus,
        task_refresh_user,
        task_send_notification,
    ]
    on_startup = on_startup
    on_shutdown = on_shutdown
    redis_settings = _redis_settings()
    max_jobs = 10
    job_timeout = 600  # 10 minutes
