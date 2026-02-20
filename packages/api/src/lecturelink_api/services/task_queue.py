"""Task queue service — Google Cloud Tasks in production, direct execution in dev."""

from __future__ import annotations

import json
import logging
import os

logger = logging.getLogger(__name__)


def _is_production() -> bool:
    return os.environ.get("ENVIRONMENT", "development") == "production"


def _get_project_id() -> str:
    return os.environ.get("GOOGLE_CLOUD_PROJECT", "")


def _get_service_url() -> str:
    """Base URL for internal HTTP task targets (Cloud Run service URL)."""
    return os.environ.get("CLOUD_RUN_SERVICE_URL", "http://localhost:8000")


_REGION = "us-central1"


class TaskQueueService:
    """Environment-aware task queue.

    In production: creates HTTP tasks via Google Cloud Tasks SDK.
    In development: calls processing functions directly.
    """

    def _create_cloud_task(
        self, queue_name: str, endpoint: str, payload: dict
    ) -> str:
        """Create an HTTP task in Google Cloud Tasks."""
        from google.cloud import tasks_v2

        client = tasks_v2.CloudTasksClient()
        project = _get_project_id()
        parent = client.queue_path(project, _REGION, queue_name)
        service_url = _get_service_url()

        from lecturelink_api.config.secrets import get_secret

        api_key = get_secret("INTERNAL_API_KEY")

        task = tasks_v2.Task(
            http_request=tasks_v2.HttpRequest(
                http_method=tasks_v2.HttpMethod.POST,
                url=f"{service_url}{endpoint}",
                headers={
                    "Content-Type": "application/json",
                    "X-Internal-API-Key": api_key,
                },
                body=json.dumps(payload).encode(),
            )
        )

        response = client.create_task(
            request=tasks_v2.CreateTaskRequest(parent=parent, task=task)
        )
        logger.info("Created Cloud Task: %s", response.name)
        return response.name

    def enqueue_lecture_processing(
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
        """Enqueue lecture processing.

        In production: creates a Cloud Task targeting /internal/process-lecture.
        In development: runs processing directly in a background thread.
        """
        if _is_production():
            self._create_cloud_task(
                queue_name="lecture-processing",
                endpoint="/internal/process-lecture",
                payload={
                    "lecture_id": lecture_id,
                    "course_id": course_id,
                    "user_id": user_id,
                    "file_urls": file_urls,
                    "is_reprocess": is_reprocess,
                },
            )
        else:
            from lecturelink_api.pipeline.background import run_lecture_processing

            import threading

            thread = threading.Thread(
                target=run_lecture_processing,
                kwargs={
                    "supabase_url": supabase_url,
                    "supabase_key": supabase_key,
                    "user_token": user_token,
                    "lecture_id": lecture_id,
                    "course_id": course_id,
                    "user_id": user_id,
                    "file_urls": file_urls,
                    "is_reprocess": is_reprocess,
                },
                daemon=True,
            )
            thread.start()
            logger.info(
                "Started dev lecture processing thread for %s", lecture_id
            )

    def enqueue_notification(
        self,
        user_id: str,
        notification_type: str,
        message: str,
    ) -> None:
        """Enqueue a notification delivery.

        In production: creates a Cloud Task targeting /internal/send-notification.
        In development: logs the notification (no email service in dev).
        """
        if _is_production():
            self._create_cloud_task(
                queue_name="notification-delivery",
                endpoint="/internal/send-notification",
                payload={
                    "user_id": user_id,
                    "notification_type": notification_type,
                    "message": message,
                },
            )
        else:
            logger.info(
                "Dev notification [%s] to user %s: %s",
                notification_type,
                user_id,
                message,
            )

    def enqueue_daily_refresh(self) -> None:
        """Enqueue the daily study actions refresh.

        In production: creates a Cloud Task targeting /internal/daily-refresh.
        In development: logs a message (daily refresh is on-demand in dev).
        """
        if _is_production():
            self._create_cloud_task(
                queue_name="daily-refresh",
                endpoint="/internal/daily-refresh",
                payload={},
            )
        else:
            logger.info("Dev daily refresh enqueued (no-op in development)")


def get_task_queue() -> TaskQueueService:
    """Dependency-injectable factory for the task queue service."""
    return TaskQueueService()
