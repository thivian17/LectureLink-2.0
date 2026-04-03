"""Routes for syllabus upload, status checking, and review."""

from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from supabase import create_client

from lecturelink_api.auth import get_authenticated_supabase, get_current_user
from lecturelink_api.config import Settings, get_settings
from lecturelink_api.models.api_models import (
    SyllabusResponse,
    SyllabusReviewRequest,
    SyllabusStatusResponse,
    SyllabusUploadResponse,
)
from lecturelink_api.services.task_queue import TaskQueueService, get_task_queue

router = APIRouter(prefix="/api/syllabi", tags=["syllabi"])

_ALLOWED_TYPES = {
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}




def _sb_admin(settings: Settings):
    """Service-role client for storage operations (bypasses RLS)."""
    return create_client(settings.SUPABASE_URL, settings.SUPABASE_SERVICE_KEY)


@router.post("/upload", response_model=SyllabusUploadResponse, status_code=status.HTTP_201_CREATED)
async def upload_syllabus(
    course_id: str = Form(...),
    file: UploadFile = File(...),
    user: dict = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
    task_queue: TaskQueueService = Depends(get_task_queue),
):
    if file.content_type not in _ALLOWED_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported file type: {file.content_type}. Only PDF and DOCX are accepted.",
        )

    sb = get_authenticated_supabase(user, settings)

    # Verify course belongs to user
    course = (
        sb.table("courses")
        .select("id")
        .eq("id", course_id)
        .eq("user_id", user["id"])
        .execute()
    )
    if not course.data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Course not found")

    # Reject upload if a confirmed syllabus already exists for this course
    existing_syllabus = (
        sb.table("syllabi")
        .select("id, needs_review, reviewed_at")
        .eq("course_id", course_id)
        .execute()
    )
    if existing_syllabus.data:
        syl = existing_syllabus.data[0]
        if not syl.get("needs_review", True) or syl.get("reviewed_at"):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="This course already has a confirmed syllabus. "
                       "To upload a new syllabus, please delete the course and create a new one.",
            )

    file_bytes = await file.read()
    file_name = file.filename or "syllabus"
    storage_path = f"{user['id']}/{course_id}/{file_name}"

    # Clean up old data for this course before re-upload (blank slate).
    # lectures CASCADE → lecture_chunks, concepts → concept_assessment_links, concept_bkt_state
    sb.table("lectures").delete().eq("course_id", course_id).execute()
    sb.table("assessments").delete().eq("course_id", course_id).execute()
    sb.table("syllabi").delete().eq("course_id", course_id).execute()

    # Upload to Supabase Storage (service role bypasses storage RLS)
    sb_admin = _sb_admin(settings)
    sb_admin.storage.from_("syllabi").upload(
        storage_path,
        file_bytes,
        {"upsert": "true", "content-type": file.content_type or "application/pdf"},
    )
    file_url = storage_path  # Store the path; frontend creates signed URLs

    # Create syllabi record
    result = (
        sb.table("syllabi")
        .insert({
            "course_id": course_id,
            "user_id": user["id"],
            "file_url": file_url,
            "file_name": file_name,
            "status": "processing",
        })
        .execute()
    )
    syllabus_id = result.data[0]["id"]

    # Trigger background processing via arq
    await task_queue.enqueue_syllabus_processing(
        syllabus_id=syllabus_id,
        file_bytes=file_bytes,
        file_name=file_name,
        mime_type=file.content_type,
        course_id=course_id,
        user_id=user["id"],
        supabase_url=settings.SUPABASE_URL,
        supabase_key=settings.SUPABASE_ANON_KEY,
        user_token=user["token"],
    )

    return SyllabusUploadResponse(syllabus_id=syllabus_id, status="processing")


@router.get("/{syllabus_id}", response_model=SyllabusResponse)
async def get_syllabus(
    syllabus_id: str,
    user: dict = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
):
    sb = get_authenticated_supabase(user, settings)
    result = (
        sb.table("syllabi")
        .select("*")
        .eq("id", syllabus_id)
        .eq("user_id", user["id"])
        .execute()
    )
    if not result.data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Syllabus not found")
    return result.data[0]


@router.get("/{syllabus_id}/status", response_model=SyllabusStatusResponse)
async def get_syllabus_status(
    syllabus_id: str,
    user: dict = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
):
    sb = get_authenticated_supabase(user, settings)
    result = (
        sb.table("syllabi")
        .select("id, status, needs_review")
        .eq("id", syllabus_id)
        .eq("user_id", user["id"])
        .execute()
    )
    if not result.data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Syllabus not found")

    row = result.data[0]
    db_status = row.get("status", "pending")
    needs_review = row.get("needs_review", True)

    # Map DB status to API status
    status_map = {"processed": "complete", "error": "error"}
    api_status = status_map.get(db_status, "processing")

    return SyllabusStatusResponse(
        syllabus_id=syllabus_id,
        status=api_status,
        needs_review=needs_review,
    )


@router.put("/{syllabus_id}/review", response_model=SyllabusResponse)
async def review_syllabus(
    syllabus_id: str,
    body: SyllabusReviewRequest,
    user: dict = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
):
    sb = get_authenticated_supabase(user, settings)
    result = (
        sb.table("syllabi")
        .update({
            "raw_extraction": body.raw_extraction,
            "needs_review": False,
            "reviewed_at": "now()",
        })
        .eq("id", syllabus_id)
        .eq("user_id", user["id"])
        .execute()
    )
    if not result.data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Syllabus not found")
    return result.data[0]
