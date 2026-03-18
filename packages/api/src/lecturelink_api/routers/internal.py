"""Internal endpoints for Cloud Tasks and scheduled jobs.

All endpoints are protected by X-Internal-API-Key header validation.
"""

from __future__ import annotations

import logging
from datetime import date, datetime, timedelta, timezone

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
    """Run daily maintenance: rate-limit cleanup, zombie sweep, reminders."""
    sb = create_client(settings.SUPABASE_URL, settings.SUPABASE_SERVICE_KEY or settings.SUPABASE_ANON_KEY)

    # Clean up old rate limit events
    rate_limit_cleaned = 0
    try:
        cleanup_result = sb.rpc("cleanup_old_rate_limit_events").execute()
        rate_limit_cleaned = cleanup_result.data or 0
        logger.info("Cleaned up %s old rate limit events", rate_limit_cleaned)
    except Exception:
        logger.warning("Rate limit cleanup failed", exc_info=True)

    # Clean up expired ADK sessions
    sessions_cleaned = 0
    try:
        from lecturelink_api.services.session_service import cleanup_expired_sessions

        sessions_cleaned = cleanup_expired_sessions(sb)
    except Exception:
        logger.warning("Session cleanup failed", exc_info=True)

    # Zombie sweep: requeue lectures stuck in "processing" for > 15 minutes
    zombies_requeued = 0
    try:
        zombie_cutoff = (datetime.now(timezone.utc) - timedelta(minutes=15)).isoformat()
        zombie_result = (
            sb.table("lectures")
            .select("id, user_id, course_id")
            .eq("processing_status", "processing")
            .lt("updated_at", zombie_cutoff)
            .execute()
        )
        for zombie in zombie_result.data or []:
            try:
                sb.table("lectures").update({
                    "processing_status": "pending",
                    "processing_stage": None,
                    "processing_progress": 0.0,
                    "processing_error": "Requeued by zombie sweep (worker crash detected)",
                }).eq("id", zombie["id"]).execute()
                zombies_requeued += 1
                logger.warning(
                    "Zombie sweep: requeued lecture %s for user %s",
                    zombie["id"],
                    zombie["user_id"],
                )
            except Exception:
                logger.warning("Zombie sweep failed for lecture %s", zombie["id"], exc_info=True)
    except Exception:
        logger.warning("Zombie sweep query failed", exc_info=True)

    # Assessment deadline reminders (48h window)
    reminders_enqueued = 0
    try:
        tomorrow_48h = (date.today() + timedelta(days=2)).isoformat()
        tomorrow_50h = (date.today() + timedelta(days=3)).isoformat()
        upcoming_assessments = (
            sb.table("assessments")
            .select("id, title, due_date, weight_percent, course_id, user_id")
            .gte("due_date", tomorrow_48h)
            .lt("due_date", tomorrow_50h)
            .execute()
        )
        for assessment in upcoming_assessments.data or []:
            try:
                await task_queue.enqueue_notification(
                    user_id=assessment["user_id"],
                    notification_type="assessment_reminder_48h",
                    message=assessment["id"],
                )
                reminders_enqueued += 1
            except Exception:
                pass
    except Exception:
        logger.warning("Deadline reminder dispatch failed", exc_info=True)

    logger.info(
        "Daily refresh: %d zombies requeued, %d reminder notifications enqueued",
        zombies_requeued,
        reminders_enqueued,
    )

    return {
        "status": "ok",
        "sessions_cleaned": sessions_cleaned,
        "rate_limit_cleaned": rate_limit_cleaned,
        "zombies_requeued": zombies_requeued,
        "reminders_enqueued": reminders_enqueued,
    }


@router.post("/send-notification", dependencies=[Depends(verify_internal_api_key)])
async def send_notification_task(
    body: SendNotificationRequest,
    settings: Settings = Depends(get_settings),
):
    """Send a notification — dispatches to email service based on type."""
    sb = create_client(
        settings.SUPABASE_URL,
        settings.SUPABASE_SERVICE_KEY or settings.SUPABASE_ANON_KEY,
    )

    if body.notification_type == "assessment_reminder_48h":
        from lecturelink_api.services.email import send_assessment_reminder

        # body.message contains the assessment_id
        try:
            assessment_result = (
                sb.table("assessments")
                .select("id, title, due_date, weight_percent, course_id, user_id")
                .eq("id", body.message)
                .single()
                .execute()
            )
        except Exception:
            return {"status": "skipped", "reason": "assessment not found"}

        if not assessment_result.data:
            return {"status": "skipped", "reason": "assessment not found"}

        # Get user email and name
        try:
            user_data = sb.auth.admin.get_user_by_id(body.user_id)
            user_email = user_data.user.email
        except Exception:
            return {"status": "skipped", "reason": "user email unavailable"}

        # Prefer first_name from profiles, fall back to email prefix
        try:
            profile = (
                sb.table("profiles")
                .select("first_name")
                .eq("id", body.user_id)
                .maybe_single()
                .execute()
            )
            user_name = (profile.data or {}).get("first_name") or user_email.split("@")[0].title()
        except Exception:
            user_name = user_email.split("@")[0].title()

        sent = await send_assessment_reminder(
            supabase=sb,
            user_id=body.user_id,
            user_email=user_email,
            user_name=user_name,
            assessment=assessment_result.data,
        )
        return {"status": "sent" if sent else "skipped", "user_id": body.user_id}

    logger.info("Unhandled notification type: %s", body.notification_type)
    return {"status": "skipped", "reason": "unhandled type"}


@router.get("/grading-feedback-report", dependencies=[Depends(verify_internal_api_key)])
async def grading_feedback_report(
    lookback_days: int = 30,
    settings: Settings = Depends(get_settings),
):
    """Aggregate grading accuracy report for tutor calibration."""
    sb = create_client(
        settings.SUPABASE_URL,
        settings.SUPABASE_SERVICE_KEY or settings.SUPABASE_ANON_KEY,
    )
    from lecturelink_api.services.grading_report import get_grading_feedback_report

    return await get_grading_feedback_report(sb, lookback_days=lookback_days)
