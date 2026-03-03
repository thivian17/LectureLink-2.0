"""Gamification API routes — XP, streaks, levels, badges, readiness."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, status
from supabase import create_client

from lecturelink_api.auth import get_current_user
from lecturelink_api.config import Settings, get_settings
from lecturelink_api.models.gamification import (
    AssessmentReadiness,
    CourseReadinessSummary,
    GamificationState,
    GradeProjection,
    WeeklyProgress,
)
from lecturelink_api.services.badges import get_user_badges
from lecturelink_api.services.gamification import (
    get_user_gamification,
    get_xp_history,
    use_streak_freeze,
)
from lecturelink_api.services.readiness import (
    get_all_assessment_readiness,
    get_assessment_readiness,
    get_course_readiness_summary,
    get_grade_projection,
)

router = APIRouter(prefix="/api/gamification", tags=["gamification"])


def _sb(user: dict, settings: Settings):
    client = create_client(settings.SUPABASE_URL, settings.SUPABASE_ANON_KEY)
    client.auth.set_session(user["token"], "")
    return client


@router.get("/state", response_model=GamificationState)
async def get_state(
    user: dict = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
):
    """Get complete gamification state for the home screen."""
    sb = _sb(user, settings)
    state = await get_user_gamification(sb, user["id"])

    return GamificationState(
        streak={
            "current_streak": state["streak"]["current"],
            "longest_streak": state["streak"]["longest"],
            "studied_today": state["streak"]["studied_today"],
            "freeze_available": state["streak"]["freeze_available"],
        },
        level={
            "current_level": state["level"]["current"],
            "total_xp": state["level"]["total_xp"],
            "xp_to_next_level": state["level"]["xp_to_next"],
            "progress_percent": state["level"]["progress_percent"],
        },
        today_xp=state["today_xp"],
        badges_count=state["badges_count"],
        recent_badges=state["recent_badges"],
    )


@router.get("/xp/history")
async def xp_history(
    days: int = Query(default=7, ge=1, le=90),
    user: dict = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
):
    """Get XP earned per day for the last N days."""
    sb = _sb(user, settings)
    return await get_xp_history(sb, user["id"], days=days)


@router.post("/streak/freeze")
async def streak_freeze(
    user: dict = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
):
    """Use a streak freeze to prevent streak reset."""
    sb = _sb(user, settings)
    result = await use_streak_freeze(sb, user["id"])
    if not result["success"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No streak freezes available",
        )
    return result


@router.get("/badges")
async def badges(
    user: dict = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
):
    """Get all badges + progress."""
    sb = _sb(user, settings)
    return await get_user_badges(sb, user["id"])


@router.get("/readiness", response_model=list[AssessmentReadiness])
async def readiness(
    course_id: str | None = Query(default=None),
    user: dict = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
):
    """Get readiness scores for all upcoming assessments."""
    sb = _sb(user, settings)
    return await get_all_assessment_readiness(sb, user["id"], course_id=course_id)


@router.get("/readiness/{assessment_id}", response_model=AssessmentReadiness)
async def readiness_detail(
    assessment_id: str,
    user: dict = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
):
    """Get readiness for a single assessment."""
    sb = _sb(user, settings)
    result = await get_assessment_readiness(sb, user["id"], assessment_id)
    if result.get("error") == "not_found":
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Assessment not found",
        )
    return result


@router.get(
    "/courses/{course_id}/readiness", response_model=CourseReadinessSummary
)
async def course_readiness(
    course_id: str,
    user: dict = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
):
    """Get course readiness summary."""
    sb = _sb(user, settings)
    return await get_course_readiness_summary(sb, user["id"], course_id)


@router.get(
    "/courses/{course_id}/grade-projection", response_model=GradeProjection
)
async def grade_projection(
    course_id: str,
    user: dict = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
):
    """Get projected final grade for a course."""
    sb = _sb(user, settings)
    return await get_grade_projection(sb, user["id"], course_id)


@router.get("/weekly-progress", response_model=WeeklyProgress)
async def weekly_progress(
    user: dict = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
):
    """Get weekly progress summary."""
    sb = _sb(user, settings)
    now = datetime.now(UTC)
    week_ago = now - timedelta(days=7)

    # Sessions this week
    sessions_result = (
        sb.table("learn_sessions")
        .select("id, concepts_completed, xp_earned")
        .eq("user_id", user["id"])
        .eq("status", "completed")
        .gte("created_at", week_ago.isoformat())
        .execute()
    )
    sessions = sessions_result.data or []

    sessions_count = len(sessions)
    total_xp = sum(s.get("xp_earned", 0) for s in sessions)
    concepts_improved = sum(
        len(s.get("concepts_completed") or []) for s in sessions
    )

    # XP by day
    xp_by_day = await get_xp_history(sb, user["id"], days=7)

    return WeeklyProgress(
        sessions_count=sessions_count,
        concepts_improved=concepts_improved,
        total_xp=total_xp,
        readiness_changes=[],
        xp_by_day=xp_by_day,
    )
