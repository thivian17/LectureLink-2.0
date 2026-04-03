"""Routes for lecture upload, processing status, and management."""

from __future__ import annotations

import logging

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    UploadFile,
    status,
)
from supabase import Client as SupabaseClient, create_client

from lecturelink_api.auth import get_authenticated_supabase, get_current_user
from lecturelink_api.config import Settings, get_settings
from lecturelink_api.middleware.rate_limit import check_rate_limit
from lecturelink_api.models.api_models import (
    LectureDetailResponse,
    LectureResponse,
    LectureStatusResponse,
)
from lecturelink_api.services.lecture_storage import cleanup_lecture_data
from lecturelink_api.services.task_queue import TaskQueueService, get_task_queue

logger = logging.getLogger(__name__)

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

_MAX_AUDIO_BYTES = 500 * 1024 * 1024   # 500 MB
_MAX_SLIDE_BYTES = 50 * 1024 * 1024    # 50 MB




def _sb_admin(settings: Settings) -> SupabaseClient:
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
    course_id: str = Form(...),
    title: str = Form(default=""),
    lecture_number: int = Form(...),
    lecture_date: str | None = Form(default=None),
    files: list[UploadFile] = File(...),
    user: dict = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
    task_queue: TaskQueueService = Depends(get_task_queue),
):
    sb = get_authenticated_supabase(user, settings)

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

        # Stream into a SpooledTemporaryFile (stays in memory up to 10MB,
        # spills to disk for larger files — avoids unbounded RAM usage).
        import tempfile

        max_size = _max_size_for(f.content_type)
        spooled = tempfile.SpooledTemporaryFile(max_size=10 * 1024 * 1024)
        total_bytes = 0
        while True:
            chunk = await f.read(1024 * 1024)  # 1 MB chunks
            if not chunk:
                break
            total_bytes += len(chunk)
            if total_bytes > max_size:
                spooled.close()
                raise HTTPException(
                    status_code=413,
                    detail=(
                        f"File too large: {f.filename} "
                        f"({total_bytes / 1024 / 1024:.1f}MB > "
                        f"{max_size / 1024 / 1024:.0f}MB limit)"
                    ),
                )
            spooled.write(chunk)
        spooled.seek(0)
        file_bytes = spooled.read()
        spooled.close()

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

    # Remove any existing non-completed lecture with the same lecture_number
    # so re-uploads (e.g. after a failure) don't create duplicates.
    existing = (
        sb.table("lectures")
        .select("id")
        .eq("course_id", course_id)
        .eq("lecture_number", lecture_number)
        .neq("processing_status", "completed")
        .execute()
    )
    for old in existing.data or []:
        cleanup_lecture_data(sb_admin, old["id"])
        sb_admin.table("lectures").delete().eq("id", old["id"]).execute()

    # Create lecture record
    effective_title = title.strip() if title else ""
    if not effective_title:
        effective_title = f"Lecture {lecture_number}"

    insert_data = {
        "course_id": course_id,
        "user_id": user["id"],
        "title": effective_title,
        "lecture_number": lecture_number,
        "processing_status": "pending",
        "processing_progress": 0.0,
    }
    if lecture_date is not None:
        insert_data["lecture_date"] = lecture_date
    if audio_storage_path:
        insert_data["audio_url"] = audio_storage_path
    if slides_storage_path:
        insert_data["slides_url"] = slides_storage_path

    result = sb.table("lectures").insert(insert_data).execute()
    lecture_id = result.data[0]["id"]

    # Trigger processing via arq task queue
    await task_queue.enqueue_lecture_processing(
        lecture_id=lecture_id,
        course_id=course_id,
        user_id=user["id"],
        file_urls=file_urls,
        supabase_url=settings.SUPABASE_URL,
        supabase_key=settings.SUPABASE_ANON_KEY,
        user_token=user["token"],
    )

    try:
        from lecturelink_api.services.observability import track_event

        track_event(user["id"], "lecture_uploaded", {
            "course_id": course_id,
            "lecture_id": lecture_id,
            "has_audio": bool(audio_storage_path),
            "has_slides": bool(slides_storage_path),
        })
    except Exception:
        pass  # Observability is non-critical

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
    sb = get_authenticated_supabase(user, settings)

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

    # Sanitize nullable DB fields that Pydantic expects as non-null
    if lecture.get("processing_progress") is None:
        lecture["processing_progress"] = 0.0

    # ── Transcript segments from chunks ──
    chunks_result = (
        sb.table("lecture_chunks")
        .select("id, chunk_index, content, start_time, end_time, slide_number, metadata")
        .eq("lecture_id", lecture_id)
        .order("chunk_index")
        .execute()
    )
    chunks = chunks_result.data or []

    # Build a chunk-id → index map for concept segment_indices later
    chunk_id_to_index: dict[str, int] = {}
    transcript_segments = []
    for i, chunk in enumerate(chunks):
        chunk_id_to_index[chunk["id"]] = i
        meta = chunk.get("metadata") or {}
        transcript_segments.append({
            "start": chunk.get("start_time"),
            "end": chunk.get("end_time"),
            "text": chunk["content"],
            "speaker": "Speaker",
            "slide_number": chunk.get("slide_number"),
            "source": meta.get("source", "chunk"),
        })

    # ── Signed URLs for audio/slides ──
    audio_url = None
    slides_url = None
    sb_admin = _sb_admin(settings)
    if lecture.get("audio_url"):
        try:
            signed = sb_admin.storage.from_("lectures").create_signed_url(
                lecture["audio_url"], 21600,
            )
            audio_url = signed["signedURL"]
        except Exception:
            logger.debug("Failed to generate signed URL for audio", exc_info=True)
    if lecture.get("slides_url"):
        try:
            signed = sb_admin.storage.from_("lectures").create_signed_url(
                lecture["slides_url"], 21600,
            )
            slides_url = signed["signedURL"]
        except Exception:
            logger.debug("Failed to generate signed URL for slides", exc_info=True)

    # ── Processing path ──
    has_audio = lecture.get("audio_url") is not None
    has_slides = lecture.get("slides_url") is not None
    if has_audio and has_slides:
        processing_path = "audio+slides"
    elif has_slides:
        processing_path = "slides_only"
    else:
        processing_path = "audio_only"

    # ── Concepts with linked assessments + segment indices (bulk, O(3) queries) ──
    concepts_result = (
        sb.table("concepts")
        .select(
            "id, title, description, category, "
            "difficulty_estimate, source_chunk_ids, subconcepts"
        )
        .eq("lecture_id", lecture_id)
        .execute()
    )
    concept_rows = concepts_result.data or []
    concept_ids = [c["id"] for c in concept_rows]

    # Bulk fetch all concept-assessment links for these concepts
    links_by_concept: dict[str, list[dict]] = {}
    if concept_ids:
        all_links_result = (
            sb.table("concept_assessment_links")
            .select("concept_id, assessment_id, relevance_score")
            .in_("concept_id", concept_ids)
            .execute()
        )
        # Bulk fetch assessment titles
        assessment_ids = list({lnk["assessment_id"] for lnk in (all_links_result.data or [])})
        assessments_map: dict[str, dict] = {}
        if assessment_ids:
            assessments_result = (
                sb.table("assessments")
                .select("id, title, due_date")
                .in_("id", assessment_ids)
                .execute()
            )
            assessments_map = {a["id"]: a for a in (assessments_result.data or [])}

        for link in all_links_result.data or []:
            cid = link["concept_id"]
            a_data = assessments_map.get(link["assessment_id"], {})
            links_by_concept.setdefault(cid, []).append({
                "id": link["assessment_id"],
                "title": a_data.get("title", "Unknown"),
                "due_date": a_data.get("due_date"),
                "relevance_score": link.get("relevance_score", 0),
            })

    concepts = []
    for c in concept_rows:
        segment_indices = [
            chunk_id_to_index[cid]
            for cid in (c.get("source_chunk_ids") or [])
            if cid in chunk_id_to_index
        ]
        concepts.append({
            "id": c["id"],
            "title": c["title"],
            "description": c.get("description"),
            "category": c.get("category", "concept"),
            "difficulty_estimate": c.get("difficulty_estimate", 0.5),
            "linked_assessments": links_by_concept.get(c["id"], []),
            "segment_indices": segment_indices,
            "subconcepts": c.get("subconcepts") or [],
        })

    # ── Slide count ──
    slide_numbers = {
        ch.get("slide_number")
        for ch in chunks
        if ch.get("slide_number") is not None
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
        audio_url=audio_url,
        slides_url=slides_url,
        transcript_segments=transcript_segments,
        concepts=concepts,
        processing_path=processing_path,
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
    sb = get_authenticated_supabase(user, settings)

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

    row = result.data[0]
    if row.get("processing_progress") is None:
        row["processing_progress"] = 0.0
    return LectureStatusResponse(**row)


@router.get("/courses/{course_id}/lectures", response_model=list[LectureResponse])
async def list_course_lectures(
    course_id: str,
    user: dict = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
):
    sb = get_authenticated_supabase(user, settings)

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

    # Sanitize nullable DB fields that Pydantic expects as non-null
    for row in result.data or []:
        if row.get("processing_progress") is None:
            row["processing_progress"] = 0.0

    return result.data or []


@router.post("/lectures/{lecture_id}/retry")
async def retry_lecture(
    lecture_id: str,
    user: dict = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
    task_queue: TaskQueueService = Depends(get_task_queue),
):
    sb = get_authenticated_supabase(user, settings)

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

    # Re-trigger processing via arq
    await task_queue.enqueue_lecture_processing(
        lecture_id=lecture_id,
        course_id=lecture["course_id"],
        user_id=user["id"],
        file_urls=file_urls,
        supabase_url=settings.SUPABASE_URL,
        supabase_key=settings.SUPABASE_ANON_KEY,
        user_token=user["token"],
    )

    return {"status": "processing", "retry_count": new_retry}


@router.post("/lectures/{lecture_id}/reprocess")
async def reprocess_lecture(
    lecture_id: str,
    user: dict = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
    task_queue: TaskQueueService = Depends(get_task_queue),
):
    sb = get_authenticated_supabase(user, settings)

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

    # Re-trigger full pipeline via arq
    await task_queue.enqueue_lecture_processing(
        lecture_id=lecture_id,
        course_id=lecture["course_id"],
        user_id=user["id"],
        file_urls=file_urls,
        supabase_url=settings.SUPABASE_URL,
        supabase_key=settings.SUPABASE_ANON_KEY,
        user_token=user["token"],
        is_reprocess=True,
    )

    return {"status": "processing"}
