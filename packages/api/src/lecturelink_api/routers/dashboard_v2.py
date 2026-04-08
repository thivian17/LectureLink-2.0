"""Dashboard V2 API routes — Academic Command Center."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from lecturelink_api.auth import get_authenticated_supabase, get_current_user
from lecturelink_api.config import Settings, get_settings
from lecturelink_api.models.readiness_v2 import (
    AssessmentReadinessV2,
    DashboardActionsResponse,
    DashboardCoursesResponse,
    DashboardTimelineResponse,
    StatsRow,
)
from lecturelink_api.services.dashboard_actions import (
    get_academic_timeline,
    get_best_next_actions,
    get_weekly_stats,
)
from lecturelink_api.services.readiness_v2 import (
    compute_assessment_readiness,
    get_all_course_readiness,
    get_course_assessment_readiness,
)

router = APIRouter(prefix="/api/dashboard", tags=["dashboard-v2"])




@router.get("/timeline", response_model=DashboardTimelineResponse)
async def timeline(
    days: int = Query(default=14, ge=1, le=30),
    user: dict = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
):
    """Get the academic timeline for the next N days."""
    sb = get_authenticated_supabase(user, settings)
    return await get_academic_timeline(sb, user["id"], days)


@router.get("/actions", response_model=DashboardActionsResponse)
async def actions(
    limit: int = Query(default=4, ge=1, le=6),
    user: dict = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
):
    """Get best next actions across all courses."""
    sb = get_authenticated_supabase(user, settings)
    return await get_best_next_actions(sb, user["id"], limit)


@router.get("/courses", response_model=DashboardCoursesResponse)
async def courses(
    user: dict = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
):
    """Get readiness intelligence for all enrolled courses."""
    sb = get_authenticated_supabase(user, settings)
    result = await get_all_course_readiness(sb, user["id"])
    return DashboardCoursesResponse(courses=result)


@router.get(
    "/courses/{course_id}/readiness",
    response_model=list[AssessmentReadinessV2],
)
async def course_readiness_v2(
    course_id: str,
    user: dict = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
):
    """Get V2 readiness for all exam-type assessments in a course."""
    sb = get_authenticated_supabase(user, settings)
    return await get_course_assessment_readiness(sb, user["id"], course_id)


@router.get("/readiness/{assessment_id}", response_model=AssessmentReadinessV2)
async def readiness(
    assessment_id: str,
    user: dict = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
):
    """Get full readiness breakdown for a single assessment."""
    sb = get_authenticated_supabase(user, settings)
    try:
        return await compute_assessment_readiness(sb, user["id"], assessment_id)
    except (KeyError, IndexError):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Assessment not found",
        )


@router.get("/stats", response_model=StatsRow)
async def stats(
    user: dict = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
):
    """Get compact weekly stats for the command center header."""
    sb = get_authenticated_supabase(user, settings)
    return await get_weekly_stats(sb, user["id"])
