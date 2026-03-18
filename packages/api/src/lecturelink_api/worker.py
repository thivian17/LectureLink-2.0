"""arq worker — async task execution for background jobs.

Run with: ``arq lecturelink_api.worker.WorkerSettings``
"""

from __future__ import annotations

import logging
import os
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from lecturelink_api.services.session_service import DatabaseSessionService

from arq.connections import RedisSettings

logger = logging.getLogger(__name__)

# Module-level singleton — set during on_startup, importable by agents
_session_service: "DatabaseSessionService | None" = None


def get_session_service() -> "DatabaseSessionService":
    """Return the worker's DatabaseSessionService singleton.

    Raises RuntimeError if called before on_startup has run.
    """
    if _session_service is None:
        raise RuntimeError("Session service not initialized — worker not started yet")
    return _session_service


# ---------------------------------------------------------------------------
# Stale job recovery
# ---------------------------------------------------------------------------

_STALE_THRESHOLD_MINUTES = 15


def _recover_stale_jobs(supabase) -> None:
    """Reset lectures and materials stuck in 'processing' from a crashed worker.

    If a row has been in 'processing' for longer than the threshold without
    an update, the previous worker was killed mid-flight. Reset to 'failed'
    so the user can retry.
    """
    from datetime import datetime, timedelta, timezone

    cutoff = (
        datetime.now(timezone.utc) - timedelta(minutes=_STALE_THRESHOLD_MINUTES)
    ).isoformat()

    for table in ("lectures", "course_materials"):
        try:
            result = (
                supabase.table(table)
                .update({
                    "processing_status": "failed",
                    "processing_error": "Processing interrupted — worker was restarted. Please retry.",
                })
                .eq("processing_status", "processing")
                .lt("updated_at", cutoff)
                .execute()
            )
            count = len(result.data) if result.data else 0
            if count:
                logger.info("Recovered %d stale %s jobs", count, table)
        except Exception:
            logger.warning("Failed to recover stale %s jobs", table, exc_info=True)


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

    # Initialize persistent ADK session service and clean up expired sessions
    from lecturelink_api.services.session_service import (
        DatabaseSessionService,
        cleanup_expired_sessions,
    )

    session_service = DatabaseSessionService(ctx["supabase"])
    ctx["session_service"] = session_service
    # Make available as module-level singleton for agent imports
    global _session_service
    _session_service = session_service

    try:
        cleanup_expired_sessions(ctx["supabase"])
    except Exception:
        logger.warning("Failed to clean up expired ADK sessions", exc_info=True)

    # Reset lectures/materials stuck in "processing" from a previous worker crash.
    # If updated_at is >15 min ago and still "processing", the old worker died.
    try:
        _recover_stale_jobs(ctx["supabase"])
    except Exception:
        logger.warning("Failed to recover stale jobs", exc_info=True)

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
    """Process a lecture through the full pipeline.

    Uses the service-role Supabase client (from worker startup) instead of
    the user's JWT token. User JWTs expire after a few minutes, which causes
    ``PGRST303 JWT expired`` errors on long-running lecture processing.
    """
    from lecturelink_api.pipeline.background import run_lecture_processing_async

    logger.info("Processing lecture %s", lecture_id)
    return await run_lecture_processing_async(
        supabase_url=ctx["settings"].SUPABASE_URL,
        supabase_key=ctx["settings"].SUPABASE_SERVICE_KEY or ctx["settings"].SUPABASE_ANON_KEY,
        user_token="",  # Use service role — user JWTs expire during long processing
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
        supabase_url=ctx["settings"].SUPABASE_URL,
        supabase_key=ctx["settings"].SUPABASE_SERVICE_KEY or ctx["settings"].SUPABASE_ANON_KEY,
        user_token="",  # Use service role — user JWTs expire during long processing
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
    sb = create_client(
        ctx["settings"].SUPABASE_URL,
        ctx["settings"].SUPABASE_SERVICE_KEY or ctx["settings"].SUPABASE_ANON_KEY,
    )

    await process_syllabus(
        syllabus_id=syllabus_id,
        file_bytes=bytes.fromhex(file_bytes_hex),
        file_name=file_name,
        mime_type=mime_type,
        course_id=course_id,
        user_id=user_id,
        supabase=sb,
    )


async def task_process_material(
    ctx: dict,
    *,
    material_id: str,
    course_id: str,
    user_id: str,
    file_url: str,
    file_name: str,
    material_type: str,
    title: str | None = None,
    supabase_url: str = "",
    supabase_key: str = "",
    user_token: str = "",
    is_reprocess: bool = False,
) -> dict | None:
    """Process a course material through the extraction pipeline."""
    from lecturelink_api.pipeline.material_background import run_material_processing_async

    logger.info("Processing material %s", material_id)
    return await run_material_processing_async(
        supabase_url=ctx["settings"].SUPABASE_URL,
        supabase_key=ctx["settings"].SUPABASE_SERVICE_KEY or ctx["settings"].SUPABASE_ANON_KEY,
        user_token="",  # Use service role — user JWTs expire during long processing
        material_id=material_id,
        course_id=course_id,
        user_id=user_id,
        file_url=file_url,
        file_name=file_name,
        material_type=material_type,
        title=title,
        is_reprocess=is_reprocess,
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


# Queue names — used by both worker settings and the enqueue side
FAST_QUEUE = "arq:fast"
SLOW_QUEUE = "arq:slow"


class WorkerSettings:
    """arq worker — handles ALL queues (single-worker fallback).

    Use this when running a single worker process that must handle
    everything. For production, prefer FastWorkerSettings + SlowWorkerSettings.
    """

    functions = [
        task_process_lecture,
        task_generate_quiz,
        task_process_syllabus,
        task_process_material,
        task_refresh_user,
        task_send_notification,
    ]
    on_startup = on_startup
    on_shutdown = on_shutdown
    redis_settings = _redis_settings()
    max_jobs = 3
    job_timeout = 600  # 10 minutes


class FastWorkerSettings:
    """arq worker — fast queue only (syllabus, notifications, user refresh).

    These jobs complete in under a minute and should never be blocked
    by long-running lecture or quiz processing.
    """

    functions = [
        task_process_syllabus,
        task_refresh_user,
        task_send_notification,
    ]
    on_startup = on_startup
    on_shutdown = on_shutdown
    redis_settings = _redis_settings()
    queue_name = FAST_QUEUE
    max_jobs = 3
    job_timeout = 300  # 5 minutes


class SlowWorkerSettings:
    """arq worker — slow queue only (lectures, quizzes, materials).

    These jobs can take several minutes. Runs separately so they
    don't block fast syllabus processing.
    """

    functions = [
        task_process_lecture,
        task_generate_quiz,
        task_process_material,
    ]
    on_startup = on_startup
    on_shutdown = on_shutdown
    redis_settings = _redis_settings()
    queue_name = SLOW_QUEUE
    max_jobs = 3
    job_timeout = 600  # 10 minutes
