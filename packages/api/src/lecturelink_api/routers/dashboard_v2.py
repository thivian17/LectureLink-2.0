"""Dashboard V2 API routes — Academic Command Center."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from supabase import create_client

from lecturelink_api.auth import get_current_user
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
)

router = APIRouter(prefix="/api/dashboard", tags=["dashboard-v2"])


def _sb(user: dict, settings: Settings):
    client = create_client(settings.SUPABASE_URL, settings.SUPABASE_ANON_KEY)
    client.auth.set_session(user["token"], "")
    return client


@router.get("/timeline", response_model=DashboardTimelineResponse)
async def timeline(
    days: int = Query(default=14, ge=1, le=30),
    user: dict = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
):
    """Get the academic timeline for the next N days."""
    sb = _sb(user, settings)
    return await get_academic_timeline(sb, user["id"], days)


@router.get("/actions", response_model=DashboardActionsResponse)
async def actions(
    limit: int = Query(default=4, ge=1, le=6),
    user: dict = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
):
    """Get best next actions across all courses."""
    sb = _sb(user, settings)
    return await get_best_next_actions(sb, user["id"], limit)


@router.get("/courses", response_model=DashboardCoursesResponse)
async def courses(
    user: dict = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
):
    """Get readiness intelligence for all enrolled courses."""
    sb = _sb(user, settings)
    result = await get_all_course_readiness(sb, user["id"])
    return DashboardCoursesResponse(courses=result)


@router.get("/readiness/{assessment_id}", response_model=AssessmentReadinessV2)
async def readiness(
    assessment_id: str,
    user: dict = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
):
    """Get full readiness breakdown for a single assessment."""
    sb = _sb(user, settings)
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
    sb = _sb(user, settings)
    return await get_weekly_stats(sb, user["id"])
