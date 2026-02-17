"""Routes for study action recommendations."""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from supabase import create_client

from lecturelink_api.auth import get_current_user
from lecturelink_api.config import Settings, get_settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["study-actions"])


class StudyActionResponse(BaseModel):
    action_type: str
    priority: float
    course_id: str
    course_name: str
    course_code: str | None = None
    title: str
    description: str
    cta_label: str
    cta_url: str
    metadata: dict = Field(default_factory=dict)


class StudyActionsListResponse(BaseModel):
    actions: list[StudyActionResponse]
    generated_at: str


def _sb(user: dict, settings: Settings):
    client = create_client(settings.SUPABASE_URL, settings.SUPABASE_ANON_KEY)
    client.auth.set_session(user["token"], "")
    return client


@router.get("/study-actions", response_model=StudyActionsListResponse)
async def get_all_study_actions(
    user: dict = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
):
    """Get prioritized study actions across all courses."""
    sb = _sb(user, settings)

    from lecturelink_api.services.study_actions_llm import get_study_actions_llm

    try:
        actions = await get_study_actions_llm(sb, user["id"])
    except Exception:
        logger.exception("Failed to compute study actions for user %s", user["id"])
        actions = []

    return StudyActionsListResponse(
        actions=[StudyActionResponse(**a.model_dump()) for a in actions],
        generated_at=datetime.now(timezone.utc).isoformat(),
    )


@router.get(
    "/courses/{course_id}/study-actions",
    response_model=StudyActionsListResponse,
)
async def get_course_study_actions(
    course_id: str,
    user: dict = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
):
    """Get prioritized study actions for a single course."""
    sb = _sb(user, settings)

    # Verify course ownership
    course = (
        sb.table("courses")
        .select("id")
        .eq("id", course_id)
        .eq("user_id", user["id"])
        .execute()
    )
    if not course.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Course not found"
        )

    from lecturelink_api.services.study_actions_llm import get_study_actions_llm

    try:
        actions = await get_study_actions_llm(sb, user["id"], course_id=course_id)
    except Exception:
        logger.exception(
            "Failed to compute study actions for course %s", course_id
        )
        actions = []

    return StudyActionsListResponse(
        actions=[StudyActionResponse(**a.model_dump()) for a in actions],
        generated_at=datetime.now(timezone.utc).isoformat(),
    )
