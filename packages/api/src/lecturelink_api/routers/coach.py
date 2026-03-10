"""Routes for the Study Coach chat."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from supabase import create_client

from lecturelink_api.auth import get_current_user
from lecturelink_api.config import Settings, get_settings
from lecturelink_api.middleware.rate_limit import check_rate_limit

router = APIRouter(prefix="/api", tags=["coach"])


class CoachChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=2000)
    conversation_history: list[dict] | None = None


class CoachRecommendation(BaseModel):
    concept: str
    action: str
    priority: str


class CoachChatResponse(BaseModel):
    message: str
    recommendations: list[CoachRecommendation] = []
    suggested_quiz: dict | None = None


def _sb(user: dict, settings: Settings):
    client = create_client(settings.SUPABASE_URL, settings.SUPABASE_ANON_KEY)
    client.auth.set_session(user["token"], "")
    return client


@router.post(
    "/courses/{course_id}/study-coach/chat",
    response_model=CoachChatResponse,
)
async def study_coach_chat(
    course_id: str,
    body: CoachChatRequest,
    user: dict = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
):
    """Chat with the AI Study Coach."""
    sb = _sb(user, settings)

    check_rate_limit(sb, user["id"], "study_coach")

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

    from lecturelink_api.services.coach import chat_with_coach

    result = await chat_with_coach(
        supabase=sb,
        course_id=course_id,
        user_id=user["id"],
        message=body.message,
        conversation_history=body.conversation_history,
    )

    return CoachChatResponse(**result)


@router.post("/courses/{course_id}/study-coach/chat/stream")
async def stream_coach_chat(
    course_id: str,
    body: CoachChatRequest,
    user: dict = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
):
    """Streaming version of study coach chat.

    Returns text/event-stream with chunks as they arrive from Gemini.
    """
    sb = _sb(user, settings)

    check_rate_limit(sb, user["id"], "study_coach")

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

    from lecturelink_api.services.coach import stream_coach_response

    return StreamingResponse(
        stream_coach_response(
            supabase=sb,
            course_id=course_id,
            user_id=user["id"],
            message=body.message,
            conversation_history=body.conversation_history,
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/courses/{course_id}/performance")
async def get_course_performance(
    course_id: str,
    user: dict = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
):
    """Get performance analytics for a student in a course."""
    sb = _sb(user, settings)

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

    from lecturelink_api.services.performance import get_performance

    return await get_performance(sb, course_id, user["id"])
