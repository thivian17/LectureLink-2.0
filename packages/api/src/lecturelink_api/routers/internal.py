"""Internal endpoints for Cloud Tasks and scheduled jobs.

All endpoints are protected by X-Internal-API-Key header validation.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel
from supabase import create_client

from lecturelink_api.config import Settings, get_settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/internal", tags=["internal"])


# ---------------------------------------------------------------------------
# Security dependency
# ---------------------------------------------------------------------------


async def verify_internal_api_key(
    request: Request,
    settings: Settings = Depends(get_settings),
) -> None:
    """Verify the X-Internal-API-Key header matches the configured secret."""
    expected = settings.INTERNAL_API_KEY
    if not expected:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Internal API key not configured",
        )

    provided = request.headers.get("X-Internal-API-Key", "")
    if provided != expected:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid or missing internal API key",
        )


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------


class ProcessLectureRequest(BaseModel):
    lecture_id: str
    course_id: str
    user_id: str
    file_urls: list[str]
    is_reprocess: bool = False


class SendNotificationRequest(BaseModel):
    user_id: str
    notification_type: str
    message: str


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post("/process-lecture", dependencies=[Depends(verify_internal_api_key)])
async def process_lecture_task(
    body: ProcessLectureRequest,
    settings: Settings = Depends(get_settings),
):
    """Process a lecture — enqueues to arq worker."""
    from lecturelink_api.services.task_queue import get_task_queue

    task_queue = get_task_queue()
    await task_queue.enqueue_lecture_processing(
        lecture_id=body.lecture_id,
        course_id=body.course_id,
        user_id=body.user_id,
        file_urls=body.file_urls,
        supabase_url=settings.SUPABASE_URL,
        supabase_key=settings.SUPABASE_ANON_KEY,
        user_token="",
        is_reprocess=body.is_reprocess,
    )

    logger.info("Enqueued lecture processing for %s via internal endpoint", body.lecture_id)
    return {"status": "processing", "lecture_id": body.lecture_id}


@router.post("/daily-refresh", dependencies=[Depends(verify_internal_api_key)])
async def daily_refresh_task(
    settings: Settings = Depends(get_settings),
):
    """Refresh study actions for all active users — fans out one arq job per user."""
    sb = create_client(settings.SUPABASE_URL, settings.SUPABASE_SERVICE_KEY or settings.SUPABASE_ANON_KEY)

    # Fetch all users with at least one course
    result = sb.table("courses").select("user_id").execute()
    user_ids = list({row["user_id"] for row in (result.data or [])})

    logger.info("Daily refresh: found %d active users", len(user_ids))

    # Fan out: enqueue one arq job per user
    from lecturelink_api.services.task_queue import get_task_queue

    task_queue = get_task_queue()
    enqueued = 0
    for user_id in user_ids:
        try:
            await task_queue.enqueue_user_refresh(user_id)
            enqueued += 1
        except Exception:
            logger.warning("Failed to enqueue refresh for user %s", user_id, exc_info=True)

    # Clean up expired ADK sessions
    sessions_cleaned = 0
    try:
        from lecturelink_api.services.session_service import cleanup_expired_sessions

        sessions_cleaned = cleanup_expired_sessions(sb)
    except Exception:
        logger.warning("Session cleanup failed", exc_info=True)

    return {
        "status": "ok",
        "users_enqueued": enqueued,
        "users_total": len(user_ids),
        "sessions_cleaned": sessions_cleaned,
    }


@router.post("/send-notification", dependencies=[Depends(verify_internal_api_key)])
async def send_notification_task(body: SendNotificationRequest):
    """Send a single notification — called by Cloud Tasks in production."""
    # Placeholder: actual notification sending (email, push, etc.) would go here.
    logger.info(
        "Notification [%s] to user %s: %s",
        body.notification_type,
        body.user_id,
        body.message,
    )
    return {"status": "sent", "user_id": body.user_id}
