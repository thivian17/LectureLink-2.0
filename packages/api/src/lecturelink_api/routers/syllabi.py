"""Routes for syllabus upload, status checking, and review."""

from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from fastapi.background import BackgroundTasks
from supabase import create_client

from lecturelink_api.auth import get_current_user
from lecturelink_api.config import Settings, get_settings
from lecturelink_api.models.api_models import (
    SyllabusResponse,
    SyllabusReviewRequest,
    SyllabusStatusResponse,
    SyllabusUploadResponse,
)
from lecturelink_api.services.syllabus_service import process_syllabus

router = APIRouter(prefix="/api/syllabi", tags=["syllabi"])

_ALLOWED_TYPES = {
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}


def _sb(user: dict, settings: Settings):
    client = create_client(settings.SUPABASE_URL, settings.SUPABASE_ANON_KEY)
    client.auth.set_session(user["token"], "")
    return client


@router.post("/upload", response_model=SyllabusUploadResponse, status_code=status.HTTP_201_CREATED)
async def upload_syllabus(
    background_tasks: BackgroundTasks,
    course_id: str = Form(...),
    file: UploadFile = File(...),
    user: dict = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
):
    if file.content_type not in _ALLOWED_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported file type: {file.content_type}. Only PDF and DOCX are accepted.",
        )

    sb = _sb(user, settings)

    # Verify course belongs to user
    course = (
        sb.table("courses")
        .select("id")
        .eq("id", course_id)
        .eq("user_id", user["id"])
        .maybe_single()
        .execute()
    )
    if course.data is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Course not found")

    file_bytes = await file.read()
    file_name = file.filename or "syllabus"
    storage_path = f"{user['id']}/{course_id}/{file_name}"

    # Upload to Supabase Storage
    sb.storage.from_("syllabi").upload(storage_path, file_bytes)
    file_url = f"{settings.SUPABASE_URL}/storage/v1/object/public/syllabi/{storage_path}"

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

    # Trigger background processing
    background_tasks.add_task(
        process_syllabus,
        syllabus_id=syllabus_id,
        file_bytes=file_bytes,
        file_name=file_name,
        mime_type=file.content_type,
        course_id=course_id,
        user_id=user["id"],
        supabase=sb,
    )

    return SyllabusUploadResponse(syllabus_id=syllabus_id, status="processing")


@router.get("/{syllabus_id}", response_model=SyllabusResponse)
async def get_syllabus(
    syllabus_id: str,
    user: dict = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
):
    sb = _sb(user, settings)
    result = (
        sb.table("syllabi")
        .select("*")
        .eq("id", syllabus_id)
        .eq("user_id", user["id"])
        .maybe_single()
        .execute()
    )
    if result.data is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Syllabus not found")
    return result.data


@router.get("/{syllabus_id}/status", response_model=SyllabusStatusResponse)
async def get_syllabus_status(
    syllabus_id: str,
    user: dict = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
):
    sb = _sb(user, settings)
    result = (
        sb.table("syllabi")
        .select("id, status, needs_review")
        .eq("id", syllabus_id)
        .eq("user_id", user["id"])
        .maybe_single()
        .execute()
    )
    if result.data is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Syllabus not found")

    db_status = result.data.get("status", "pending")
    needs_review = result.data.get("needs_review", True)

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
    sb = _sb(user, settings)
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
