"""Analytics ingestion endpoints — event tracking, bug reports, feedback."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, Field
from supabase import create_client

from lecturelink_api.auth import get_current_user
from lecturelink_api.config import Settings, get_settings

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/analytics", tags=["analytics"])


def _sb_admin(settings: Settings):
    """Service-role client that bypasses RLS — use only for trusted backend writes."""
    return create_client(settings.SUPABASE_URL, settings.SUPABASE_SERVICE_KEY)


class AnalyticsEventPayload(BaseModel):
    event_type: str = Field(..., min_length=1, max_length=100)
    event_category: str = Field(
        ..., pattern="^(engagement|feature|navigation|performance|error)$"
    )
    properties: dict = Field(default_factory=dict)
    page_path: str | None = None
    device_type: str | None = None


class BatchEventsRequest(BaseModel):
    events: list[AnalyticsEventPayload] = Field(..., max_length=50)
    session_id: str | None = None


class BugReportRequest(BaseModel):
    title: str = Field(..., min_length=3, max_length=200)
    description: str = Field(..., min_length=10, max_length=5000)
    severity: str = Field(default="medium", pattern="^(critical|high|medium|low)$")
    page_path: str | None = None
    browser_info: dict = Field(default_factory=dict)
    console_errors: list = Field(default_factory=list)


class FeedbackRequest(BaseModel):
    feedback_type: str = Field(..., pattern="^(nps|feature|general|churn)$")
    rating: int | None = Field(default=None, ge=1, le=10)
    message: str | None = Field(default=None, max_length=2000)
    feature_tag: str | None = Field(
        default=None,
        pattern="^(tutor|quiz|coach|learn|general)$",
    )


@router.post("/events", status_code=status.HTTP_204_NO_CONTENT)
async def ingest_events(
    body: BatchEventsRequest,
    user: dict = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
):
    """Batch ingest analytics events from the frontend."""
    sb = _sb_admin(settings)
    rows = [
        {
            "user_id": user["id"],
            "session_id": body.session_id,
            "event_type": ev.event_type,
            "event_category": ev.event_category,
            "properties": ev.properties,
            "page_path": ev.page_path,
            "device_type": ev.device_type,
        }
        for ev in body.events
    ]
    try:
        sb.table("analytics_events").insert(rows).execute()
    except Exception:
        logger.exception("Failed to ingest analytics events")
        # Swallow silently — analytics must never crash the app


@router.post("/bug-report", status_code=status.HTTP_201_CREATED)
async def submit_bug_report(
    body: BugReportRequest,
    user: dict = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
):
    """Submit a bug report from the in-app reporter."""
    sb = _sb_admin(settings)
    result = (
        sb.table("bug_reports")
        .insert(
            {
                "user_id": user["id"],
                "title": body.title,
                "description": body.description,
                "severity": body.severity,
                "page_path": body.page_path,
                "browser_info": body.browser_info,
                "console_errors": body.console_errors[:20],
            }
        )
        .execute()
    )
    return {"id": result.data[0]["id"]}


@router.post("/feedback", status_code=status.HTTP_201_CREATED)
async def submit_feedback(
    body: FeedbackRequest,
    user: dict = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
):
    """Submit user NPS or feature feedback."""
    sb = _sb_admin(settings)
    result = (
        sb.table("user_feedback")
        .insert(
            {
                "user_id": user["id"],
                "feedback_type": body.feedback_type,
                "rating": body.rating,
                "message": body.message,
                "feature_tag": body.feature_tag,
            }
        )
        .execute()
    )
    return {"id": result.data[0]["id"]}
