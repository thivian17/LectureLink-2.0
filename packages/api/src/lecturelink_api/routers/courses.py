"""CRUD routes for courses."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from supabase import create_client

from lecturelink_api.auth import get_current_user
from lecturelink_api.config import Settings, get_settings
from lecturelink_api.models.api_models import (
    CourseCreate,
    CourseCreateResponse,
    CourseResponse,
    CourseUpdate,
)

router = APIRouter(prefix="/api/courses", tags=["courses"])


def _sb(user: dict, settings: Settings):
    """Build a Supabase client authenticated with the user's token."""
    client = create_client(settings.SUPABASE_URL, settings.SUPABASE_ANON_KEY)
    client.auth.set_session(user["token"], "")
    return client


@router.post("", response_model=CourseCreateResponse, status_code=status.HTTP_201_CREATED)
async def create_course(
    body: CourseCreate,
    user: dict = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
):
    sb = _sb(user, settings)
    payload = body.model_dump(mode="json", exclude_none=True)
    payload["user_id"] = user["id"]
    result = sb.table("courses").insert(payload).execute()
    course = result.data[0]

    # Check if this is the user's first course
    existing_courses = (
        sb.table("courses")
        .select("id")
        .eq("user_id", user["id"])
        .execute()
    )
    is_first_course = len(existing_courses.data) <= 1

    return {
        **course,
        "needs_onboarding": True,
        "is_first_course": is_first_course,
        "onboarding_completed_at": course.get("onboarding_completed_at"),
    }


@router.get("", response_model=list[CourseResponse])
async def list_courses(
    user: dict = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
):
    sb = _sb(user, settings)
    result = (
        sb.table("courses")
        .select("*")
        .eq("user_id", user["id"])
        .order("created_at", desc=True)
        .execute()
    )
    return result.data


@router.get("/{course_id}", response_model=CourseResponse)
async def get_course(
    course_id: str,
    user: dict = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
):
    sb = _sb(user, settings)
    result = (
        sb.table("courses")
        .select("*")
        .eq("id", course_id)
        .eq("user_id", user["id"])
        .execute()
    )
    if not result.data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Course not found")
    return result.data[0]


@router.patch("/{course_id}", response_model=CourseResponse)
async def update_course(
    course_id: str,
    body: CourseUpdate,
    user: dict = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
):
    sb = _sb(user, settings)
    payload = body.model_dump(mode="json", exclude_none=True)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="No fields to update"
        )
    result = (
        sb.table("courses")
        .update(payload)
        .eq("id", course_id)
        .eq("user_id", user["id"])
        .execute()
    )
    if not result.data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Course not found")
    return result.data[0]


@router.delete("/{course_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_course(
    course_id: str,
    user: dict = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
):
    sb = _sb(user, settings)
    result = (
        sb.table("courses")
        .delete()
        .eq("id", course_id)
        .eq("user_id", user["id"])
        .execute()
    )
    if not result.data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Course not found")


@router.get("/{course_id}/performance")
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
