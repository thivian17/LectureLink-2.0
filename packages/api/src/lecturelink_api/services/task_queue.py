"""Task queue service — arq (Redis) for all environments.

Enqueues jobs to be picked up by the arq worker process. Falls back
to direct execution if Redis is unavailable (e.g. local dev without
Redis running).

Jobs are routed to two queues:
- **fast** (``arq:fast``) — syllabus processing, notifications, user refresh
- **slow** (``arq:slow``) — lecture processing, quiz generation, material processing

This prevents long-running lecture jobs from blocking quick syllabus extractions.
"""

from __future__ import annotations

import logging

from redis.asyncio import Redis

logger = logging.getLogger(__name__)

# Queue names for routing jobs to the correct worker.
# Always use named queues — workers are configured to listen on the right one.
FAST_QUEUE = "arq:fast"
SLOW_QUEUE = "arq:slow"


class TaskQueueService:
    """Async task queue backed by arq / Redis.

    All ``enqueue_*`` methods are async and push jobs onto the arq queue.
    If Redis is unavailable, lecture processing falls back to a background
    thread (same as the old dev-mode behaviour).
    """

    def __init__(self, redis: Redis | None = None) -> None:
        self._redis = redis

    async def _enqueue(
        self, func_name: str, *, _queue_name: str | None = None, **kwargs,
    ) -> str | None:
        """Enqueue a job via arq. Returns the job ID or None on failure."""
        if self._redis is None:
            logger.warning("Redis unavailable — cannot enqueue %s", func_name)
            return None

        from arq.connections import ArqRedis

        pool = ArqRedis(pool_or_conn=self._redis.connection_pool)
        job = await pool.enqueue_job(
            func_name, _job_id=None, _queue_name=_queue_name, **kwargs,
        )
        if job is None:
            logger.warning("Job %s was not enqueued (duplicate?)", func_name)
            return None
        logger.info("Enqueued %s → job %s (queue=%s)", func_name, job.job_id, _queue_name)
        return job.job_id

    async def enqueue_lecture_processing(
        self,
        lecture_id: str,
        course_id: str,
        user_id: str,
        file_urls: list[str],
        *,
        supabase_url: str = "",
        supabase_key: str = "",
        user_token: str = "",
        is_reprocess: bool = False,
    ) -> None:
        """Enqueue lecture processing via arq."""
        job_id = await self._enqueue(
            "task_process_lecture",
            _queue_name=SLOW_QUEUE,
            lecture_id=lecture_id,
            course_id=course_id,
            user_id=user_id,
            file_urls=file_urls,
            supabase_url=supabase_url,
            supabase_key=supabase_key,
            user_token=user_token,
            is_reprocess=is_reprocess,
        )
        if job_id is None:
            # Fallback: run in a thread (dev without Redis)
            self._fallback_lecture_processing(
                supabase_url=supabase_url,
                supabase_key=supabase_key,
                user_token=user_token,
                lecture_id=lecture_id,
                course_id=course_id,
                user_id=user_id,
                file_urls=file_urls,
                is_reprocess=is_reprocess,
            )

    @staticmethod
    def _fallback_lecture_processing(**kwargs) -> None:
        """Fallback: run lecture processing in a daemon thread."""
        import threading

        from lecturelink_api.pipeline.background import run_lecture_processing

        thread = threading.Thread(
            target=run_lecture_processing,
            kwargs=kwargs,
            daemon=True,
        )
        thread.start()
        logger.info(
            "Fallback: started lecture processing thread for %s",
            kwargs.get("lecture_id"),
        )

    async def enqueue_quiz_generation(
        self,
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
        """Enqueue quiz generation via arq."""
        job_id = await self._enqueue(
            "task_generate_quiz",
            _queue_name=SLOW_QUEUE,
            supabase_url=supabase_url,
            supabase_key=supabase_key,
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
        if job_id is None:
            # Fallback: run in a thread
            self._fallback_quiz_generation(
                supabase_url=supabase_url,
                supabase_key=supabase_key,
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

    @staticmethod
    def _fallback_quiz_generation(**kwargs) -> None:
        """Fallback: run quiz generation in a daemon thread."""
        import threading

        from lecturelink_api.services.quiz import run_quiz_generation

        thread = threading.Thread(
            target=run_quiz_generation,
            kwargs=kwargs,
            daemon=True,
        )
        thread.start()
        logger.info(
            "Fallback: started quiz generation thread for %s",
            kwargs.get("quiz_id"),
        )

    async def enqueue_syllabus_processing(
        self,
        *,
        syllabus_id: str,
        file_bytes: bytes,
        file_name: str,
        mime_type: str,
        course_id: str,
        user_id: str,
        supabase_url: str = "",
        supabase_key: str = "",
        user_token: str = "",
    ) -> None:
        """Enqueue syllabus processing via arq."""
        job_id = await self._enqueue(
            "task_process_syllabus",
            _queue_name=FAST_QUEUE,
            syllabus_id=syllabus_id,
            file_bytes_hex=file_bytes.hex(),
            file_name=file_name,
            mime_type=mime_type,
            course_id=course_id,
            user_id=user_id,
            supabase_url=supabase_url,
            supabase_key=supabase_key,
            user_token=user_token,
        )
        if job_id is None:
            self._fallback_syllabus_processing(
                syllabus_id=syllabus_id,
                file_bytes=file_bytes,
                file_name=file_name,
                mime_type=mime_type,
                course_id=course_id,
                user_id=user_id,
                supabase_url=supabase_url,
                supabase_key=supabase_key,
                user_token=user_token,
            )

    @staticmethod
    def _fallback_syllabus_processing(
        *,
        syllabus_id: str,
        file_bytes: bytes,
        file_name: str,
        mime_type: str,
        course_id: str,
        user_id: str,
        supabase_url: str,
        supabase_key: str,
        user_token: str,
    ) -> None:
        """Fallback: run syllabus processing in a daemon thread."""
        import asyncio
        import threading

        def _run():
            from supabase import create_client

            from lecturelink_api.services.syllabus_service import process_syllabus

            sb = create_client(supabase_url, supabase_key)
            if user_token:
                sb.auth.set_session(user_token, "")
            loop = asyncio.new_event_loop()
            try:
                loop.run_until_complete(
                    process_syllabus(
                        syllabus_id=syllabus_id,
                        file_bytes=file_bytes,
                        file_name=file_name,
                        mime_type=mime_type,
                        course_id=course_id,
                        user_id=user_id,
                        supabase=sb,
                    )
                )
            except Exception:
                logger.exception("Fallback syllabus processing failed for %s", syllabus_id)
            finally:
                loop.close()

        thread = threading.Thread(target=_run, daemon=True)
        thread.start()
        logger.info(
            "Fallback: started syllabus processing thread for %s",
            syllabus_id,
        )

    async def enqueue_material_processing(
        self,
        material_id: str,
        course_id: str,
        user_id: str,
        file_url: str,
        file_name: str,
        material_type: str,
        *,
        title: str | None = None,
        supabase_url: str = "",
        supabase_key: str = "",
        user_token: str = "",
        is_reprocess: bool = False,
    ) -> None:
        """Enqueue material processing via arq."""
        job_id = await self._enqueue(
            "task_process_material",
            _queue_name=SLOW_QUEUE,
            material_id=material_id,
            course_id=course_id,
            user_id=user_id,
            file_url=file_url,
            file_name=file_name,
            material_type=material_type,
            title=title,
            supabase_url=supabase_url,
            supabase_key=supabase_key,
            user_token=user_token,
            is_reprocess=is_reprocess,
        )
        if job_id is None:
            self._fallback_material_processing(
                supabase_url=supabase_url,
                supabase_key=supabase_key,
                user_token=user_token,
                material_id=material_id,
                course_id=course_id,
                user_id=user_id,
                file_url=file_url,
                file_name=file_name,
                material_type=material_type,
                title=title,
                is_reprocess=is_reprocess,
            )

    @staticmethod
    def _fallback_material_processing(**kwargs) -> None:
        """Fallback: run material processing in a daemon thread."""
        import threading

        from lecturelink_api.pipeline.material_background import run_material_processing

        thread = threading.Thread(
            target=run_material_processing,
            kwargs=kwargs,
            daemon=True,
        )
        thread.start()
        logger.info(
            "Fallback: started material processing thread for %s",
            kwargs.get("material_id"),
        )

    async def enqueue_notification(
        self,
        user_id: str,
        notification_type: str,
        message: str,
    ) -> None:
        """Enqueue a notification delivery via arq."""
        job_id = await self._enqueue(
            "task_send_notification",
            _queue_name=FAST_QUEUE,
            user_id=user_id,
            notification_type=notification_type,
            message=message,
        )
        if job_id is None:
            logger.info(
                "Notification [%s] to user %s: %s (not enqueued — logged only)",
                notification_type,
                user_id,
                message,
            )

    async def enqueue_user_refresh(self, user_id: str) -> None:
        """Enqueue a single-user study actions refresh."""
        await self._enqueue("task_refresh_user", _queue_name=FAST_QUEUE, user_id=user_id)

    async def enqueue_daily_refresh(self) -> None:
        """Enqueue the daily study actions refresh (fans out per-user)."""
        # The daily-refresh endpoint now fans out — see internal router.
        logger.info("Daily refresh enqueued via arq")


def get_task_queue() -> TaskQueueService:
    """Dependency-injectable factory for the task queue service."""
    from lecturelink_api.services.redis_client import get_redis

    return TaskQueueService(redis=get_redis())
