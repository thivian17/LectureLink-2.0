"""Routes for lecture upload, processing status, and management."""

from __future__ import annotations

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    UploadFile,
    status,
)
from fastapi.background import BackgroundTasks
from supabase import create_client

from lecturelink_api.auth import get_current_user
from lecturelink_api.config import Settings, get_settings
from lecturelink_api.middleware.rate_limit import check_rate_limit
from lecturelink_api.models.api_models import (
    LectureDetailResponse,
    LectureResponse,
    LectureStatusResponse,
)
from lecturelink_api.pipeline.background import run_lecture_processing
from lecturelink_api.services.lecture_storage import cleanup_lecture_data

router = APIRouter(prefix="/api", tags=["lectures"])

# Allowed MIME types and size limits
_AUDIO_TYPES = {
    "audio/mpeg",       # mp3
    "audio/wav",        # wav
    "audio/x-wav",      # wav (alt)
    "audio/x-m4a",      # m4a
    "audio/mp4",        # m4a (alt)
    "audio/ogg",        # ogg
    "audio/webm",       # webm
    "audio/flac",       # flac
    "audio/x-flac",     # flac (alt)
}
_SLIDE_TYPES = {
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.presentationml.presentation",
}
_ALL_ALLOWED = _AUDIO_TYPES | _SLIDE_TYPES

_MAX_AUDIO_BYTES = 200 * 1024 * 1024   # 200 MB
_MAX_SLIDE_BYTES = 50 * 1024 * 1024    # 50 MB


def _sb(user: dict, settings: Settings):
    client = create_client(settings.SUPABASE_URL, settings.SUPABASE_ANON_KEY)
    client.auth.set_session(user["token"], "")
    return client


def _sb_admin(settings: Settings):
    """Service-role client for storage operations (bypasses RLS)."""
    return create_client(settings.SUPABASE_URL, settings.SUPABASE_SERVICE_KEY)


def _max_size_for(content_type: str) -> int:
    if content_type in _AUDIO_TYPES:
        return _MAX_AUDIO_BYTES
    return _MAX_SLIDE_BYTES


def _signed_urls_from_lecture(sb_admin, lecture: dict) -> list[str]:
    """Generate fresh signed URLs from a lecture's stored storage paths."""
    urls: list[str] = []
    for key in ("audio_url", "slides_url"):
        path = lecture.get(key)
        if path:
            signed = sb_admin.storage.from_("lectures").create_signed_url(
                path, 21600,
            )
            urls.append(signed["signedURL"])
    return urls


@router.post("/lectures/upload", status_code=status.HTTP_200_OK)
async def upload_lecture(
    background_tasks: BackgroundTasks,
    course_id: str = Form(...),
    title: str = Form(...),
    lecture_number: int | None = Form(default=None),
    lecture_date: str | None = Form(default=None),
    files: list[UploadFile] = File(...),
    user: dict = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
):
    sb = _sb(user, settings)

    # Rate limit
    check_rate_limit(sb, user["id"], "lecture_upload")

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

    # Validate files and upload
    sb_admin = _sb_admin(settings)
    file_urls: list[str] = []
    audio_storage_path: str | None = None
    slides_storage_path: str | None = None

    for f in files:
        if f.content_type not in _ALL_ALLOWED:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unsupported file type: {f.content_type}",
            )

        file_bytes = await f.read()
        max_size = _max_size_for(f.content_type)
        if len(file_bytes) > max_size:
            raise HTTPException(
                status_code=413,
                detail=(
                    f"File too large: {f.filename} "
                    f"({len(file_bytes) / 1024 / 1024:.1f}MB > "
                    f"{max_size / 1024 / 1024:.0f}MB limit)"
                ),
            )

        filename = f.filename or "upload"
        storage_path = f"lectures/{user['id']}/{course_id}/{filename}"
        try:
            sb_admin.storage.from_("lectures").upload(
                storage_path,
                file_bytes,
                {"upsert": "true", "content-type": f.content_type or "application/octet-stream"},
            )
        except Exception as storage_err:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to upload file to storage: {storage_err}",
            )

        # Track storage paths by type for the lecture record
        if f.content_type in _AUDIO_TYPES:
            audio_storage_path = storage_path
        else:
            slides_storage_path = storage_path

        # Generate a signed URL (valid 6 hours) so the pipeline can download it
        signed = sb_admin.storage.from_("lectures").create_signed_url(
            storage_path, 21600,
        )
        file_urls.append(signed["signedURL"])

    # Create lecture record
    insert_data = {
        "course_id": course_id,
        "user_id": user["id"],
        "title": title,
        "processing_status": "pending",
        "processing_progress": 0.0,
    }
    if lecture_number is not None:
        insert_data["lecture_number"] = lecture_number
    if lecture_date is not None:
        insert_data["lecture_date"] = lecture_date
    if audio_storage_path:
        insert_data["audio_url"] = audio_storage_path
    if slides_storage_path:
        insert_data["slides_url"] = slides_storage_path

    result = sb.table("lectures").insert(insert_data).execute()
    lecture_id = result.data[0]["id"]

    # Trigger background processing
    background_tasks.add_task(
        run_lecture_processing,
        supabase=sb,
        lecture_id=lecture_id,
        course_id=course_id,
        user_id=user["id"],
        file_urls=file_urls,
    )

    return {"lecture_id": lecture_id, "status": "processing"}


@router.get(
    "/lectures/{lecture_id}",
    response_model=LectureDetailResponse,
)
async def get_lecture(
    lecture_id: str,
    user: dict = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
):
    sb = _sb(user, settings)

    result = (
        sb.table("lectures")
        .select("*")
        .eq("id", lecture_id)
        .eq("user_id", user["id"])
        .execute()
    )
    if not result.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Lecture not found"
        )

    lecture = result.data[0]

    # Fetch concepts with linked assessments
    concepts_result = (
        sb.table("concepts")
        .select("id, title, description, category, difficulty_estimate")
        .eq("lecture_id", lecture_id)
        .execute()
    )
    concepts = []
    for c in concepts_result.data or []:
        # Get linked assessments for each concept
        links_result = (
            sb.table("concept_assessment_links")
            .select("assessment_id, relevance_score")
            .eq("concept_id", c["id"])
            .execute()
        )
        linked = []
        for link in links_result.data or []:
            a_result = (
                sb.table("assessments")
                .select("title")
                .eq("id", link["assessment_id"])
                .execute()
            )
            linked.append({
                "assessment_id": link["assessment_id"],
                "title": a_result.data[0]["title"] if a_result.data else "Unknown",
                "relevance_score": link.get("relevance_score", 0),
            })
        concepts.append({**c, "linked_assessments": linked})

    # Get slide count from chunks
    slide_result = (
        sb.table("lecture_chunks")
        .select("slide_number")
        .eq("lecture_id", lecture_id)
        .execute()
    )
    slide_numbers = {
        c["slide_number"]
        for c in slide_result.data or []
        if c.get("slide_number") is not None
    }
    slide_count = len(slide_numbers) if slide_numbers else None

    return LectureDetailResponse(
        **{
            k: lecture[k]
            for k in (
                "id", "course_id", "title", "lecture_number", "lecture_date",
                "processing_status", "processing_stage", "processing_progress",
                "summary", "duration_seconds", "created_at",
            )
            if k in lecture
        },
        transcript=lecture.get("transcript"),
        concepts=concepts,
        slide_count=slide_count,
    )


@router.get(
    "/lectures/{lecture_id}/status",
    response_model=LectureStatusResponse,
)
async def get_lecture_status(
    lecture_id: str,
    user: dict = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
):
    sb = _sb(user, settings)

    result = (
        sb.table("lectures")
        .select(
            "processing_status, processing_stage, "
            "processing_progress, processing_error"
        )
        .eq("id", lecture_id)
        .eq("user_id", user["id"])
        .execute()
    )
    if not result.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Lecture not found"
        )

    return LectureStatusResponse(**result.data[0])


@router.get("/courses/{course_id}/lectures", response_model=list[LectureResponse])
async def list_course_lectures(
    course_id: str,
    user: dict = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
):
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

    result = (
        sb.table("lectures")
        .select("*")
        .eq("course_id", course_id)
        .eq("user_id", user["id"])
        .order("lecture_date", desc=True)
        .order("lecture_number", desc=True)
        .execute()
    )
    return result.data or []


@router.post("/lectures/{lecture_id}/retry")
async def retry_lecture(
    lecture_id: str,
    background_tasks: BackgroundTasks,
    user: dict = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
):
    sb = _sb(user, settings)

    result = (
        sb.table("lectures")
        .select("*")
        .eq("id", lecture_id)
        .eq("user_id", user["id"])
        .execute()
    )
    if not result.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Lecture not found"
        )

    lecture = result.data[0]

    if lecture["processing_status"] != "failed":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Lecture is not in failed state",
        )

    retry_count = lecture.get("retry_count", 0)
    if retry_count >= 3:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Maximum retries exceeded",
        )

    # Reset status
    new_retry = retry_count + 1
    sb.table("lectures").update({
        "processing_status": "pending",
        "processing_error": None,
        "retry_count": new_retry,
    }).eq("id", lecture_id).execute()

    # Regenerate signed URLs from stored storage paths
    sb_admin = _sb_admin(settings)
    file_urls = _signed_urls_from_lecture(sb_admin, lecture)

    # Re-trigger processing
    background_tasks.add_task(
        run_lecture_processing,
        supabase=sb,
        lecture_id=lecture_id,
        course_id=lecture["course_id"],
        user_id=user["id"],
        file_urls=file_urls,
    )

    return {"status": "processing", "retry_count": new_retry}


@router.post("/lectures/{lecture_id}/reprocess")
async def reprocess_lecture(
    lecture_id: str,
    background_tasks: BackgroundTasks,
    user: dict = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
):
    sb = _sb(user, settings)

    result = (
        sb.table("lectures")
        .select("*")
        .eq("id", lecture_id)
        .eq("user_id", user["id"])
        .execute()
    )
    if not result.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Lecture not found"
        )

    lecture = result.data[0]

    # Clean up existing data
    cleanup_lecture_data(sb, lecture_id)

    # Reset lecture fields
    sb.table("lectures").update({
        "processing_status": "pending",
        "processing_stage": None,
        "processing_progress": 0.0,
        "processing_error": None,
        "transcript": None,
        "summary": None,
    }).eq("id", lecture_id).execute()

    # Regenerate signed URLs from stored storage paths
    sb_admin = _sb_admin(settings)
    file_urls = _signed_urls_from_lecture(sb_admin, lecture)

    # Re-trigger full pipeline
    background_tasks.add_task(
        run_lecture_processing,
        supabase=sb,
        lecture_id=lecture_id,
        course_id=lecture["course_id"],
        user_id=user["id"],
        file_urls=file_urls,
        is_reprocess=True,
    )

    return {"status": "processing"}
