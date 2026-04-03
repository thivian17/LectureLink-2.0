"""Routes for assessments: list, priorities, update, delete."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from lecturelink_api.auth import get_authenticated_supabase, get_current_user
from lecturelink_api.config import Settings, get_settings
from lecturelink_api.models.api_models import (
    AssessmentResponse,
    AssessmentResultRequest,
    AssessmentResultResponse,
    AssessmentUpdate,
)

router = APIRouter(tags=["assessments"])




def _verify_course_ownership(sb, course_id: str, user_id: str):
    result = (
        sb.table("courses")
        .select("id")
        .eq("id", course_id)
        .eq("user_id", user_id)
        .execute()
    )
    if not result.data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Course not found")


@router.get(
    "/api/courses/{course_id}/assessments",
    response_model=list[AssessmentResponse],
)
async def list_assessments(
    course_id: str,
    user: dict = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
):
    sb = get_authenticated_supabase(user, settings)
    _verify_course_ownership(sb, course_id, user["id"])
    result = (
        sb.table("assessments")
        .select("*")
        .eq("course_id", course_id)
        .order("due_date", desc=False)
        .execute()
    )
    return result.data


@router.get("/api/courses/{course_id}/assessments/priorities")
async def get_priorities(
    course_id: str,
    user: dict = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
):
    sb = get_authenticated_supabase(user, settings)
    _verify_course_ownership(sb, course_id, user["id"])
    result = sb.rpc("get_study_priorities", {"p_course_id": course_id}).execute()
    return result.data


@router.patch("/api/assessments/{assessment_id}", response_model=AssessmentResponse)
async def update_assessment(
    assessment_id: str,
    body: AssessmentUpdate,
    user: dict = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
):
    sb = get_authenticated_supabase(user, settings)
    # Verify ownership via course join
    existing = (
        sb.table("assessments")
        .select("id, course_id")
        .eq("id", assessment_id)
        .execute()
    )
    if not existing.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Assessment not found"
        )
    _verify_course_ownership(sb, existing.data[0]["course_id"], user["id"])

    payload = body.model_dump(mode="json", exclude_none=True)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="No fields to update"
        )
    result = (
        sb.table("assessments")
        .update(payload)
        .eq("id", assessment_id)
        .execute()
    )
    return result.data[0]


@router.delete("/api/assessments/{assessment_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_assessment(
    assessment_id: str,
    user: dict = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
):
    sb = get_authenticated_supabase(user, settings)
    existing = (
        sb.table("assessments")
        .select("id, course_id")
        .eq("id", assessment_id)
        .execute()
    )
    if not existing.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Assessment not found"
        )
    _verify_course_ownership(sb, existing.data[0]["course_id"], user["id"])
    sb.table("assessments").delete().eq("id", assessment_id).execute()


@router.put(
    "/api/assessments/{assessment_id}/result",
    response_model=AssessmentResultResponse,
)
async def save_assessment_result(
    assessment_id: str,
    body: AssessmentResultRequest,
    user: dict = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
):
    """Save a student's score for a past assessment (used during onboarding)."""
    sb = get_authenticated_supabase(user, settings)

    # Verify the assessment exists
    existing = (
        sb.table("assessments")
        .select("id, course_id")
        .eq("id", assessment_id)
        .execute()
    )
    if not existing.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Assessment not found"
        )

    # Verify course ownership
    _verify_course_ownership(sb, existing.data[0]["course_id"], user["id"])

    # Update student_score
    result = (
        sb.table("assessments")
        .update({"student_score": body.score_percent})
        .eq("id", assessment_id)
        .execute()
    )
    return result.data[0]
