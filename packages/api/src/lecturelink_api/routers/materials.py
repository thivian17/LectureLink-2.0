"""Routes for course material upload, processing status, and management."""

from __future__ import annotations

import contextlib
import uuid
from enum import StrEnum
from typing import Any

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    UploadFile,
    status,
)
from pydantic import BaseModel
from supabase import create_client

from lecturelink_api.auth import get_authenticated_supabase, get_current_user
from lecturelink_api.config import Settings, get_settings
from lecturelink_api.middleware.rate_limit import check_rate_limit
from lecturelink_api.services.task_queue import TaskQueueService, get_task_queue

router = APIRouter(prefix="/api", tags=["materials"])

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

ALLOWED_MATERIAL_EXTENSIONS: set[str] = {
    ".pdf", ".docx", ".doc", ".pptx", ".ppt",
    ".txt", ".md", ".csv", ".xlsx", ".xls",
    ".py", ".java", ".cpp", ".c", ".h", ".js", ".ts",
    ".html", ".css", ".json", ".xml", ".yaml", ".yml",
    ".r", ".m", ".tex", ".bib", ".ipynb",
}

MAX_MATERIAL_SIZE_BYTES: int = 50 * 1024 * 1024  # 50 MB


class MaterialType(StrEnum):
    """Types of supplementary course materials."""

    TEXTBOOK = "textbook"
    NOTES = "notes"
    SLIDES = "slides"
    WORKSHEET = "worksheet"
    LAB = "lab"
    READING = "reading"
    CODE = "code"
    REFERENCE = "reference"
    OTHER = "other"


# ---------------------------------------------------------------------------
# Response models
# ---------------------------------------------------------------------------


class MaterialResponse(BaseModel):
    id: str
    course_id: str
    user_id: str
    title: str
    material_type: str
    file_name: str
    file_size_bytes: int | None = None
    processing_status: str = "pending"
    retry_count: int = 0
    created_at: str | None = None


class MaterialListResponse(BaseModel):
    materials: list[MaterialResponse]


class MaterialDetailResponse(MaterialResponse):
    file_url: str | None = None
    linked_assessment_id: str | None = None
    week_number: int | None = None
    relevant_date: str | None = None
    chunk_count: int | None = None
    processing_error: str | None = None


class MaterialStatusResponse(BaseModel):
    id: str
    processing_status: str
    processing_error: str | None = None
    retry_count: int = 0
    chunk_count: int | None = None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------




def _sb_admin(settings: Settings):
    """Service-role client for storage operations (bypasses RLS)."""
    return create_client(settings.SUPABASE_URL, settings.SUPABASE_SERVICE_KEY)


def _get_extension(filename: str) -> str:
    """Extract lowercase file extension from filename."""
    import os

    _, ext = os.path.splitext(filename)
    return ext.lower()


def _verify_ownership(sb, table: str, record_id: str, user_id: str, label: str = "Record") -> dict:
    """Fetch a record and verify ownership, raising 404/403 as needed."""
    result = (
        sb.table(table)
        .select("*")
        .eq("id", record_id)
        .execute()
    )
    if not result.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"{label} not found",
        )
    record = result.data[0]
    if record.get("user_id") != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"You do not own this {label.lower()}",
        )
    return record


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post(
    "/courses/{course_id}/materials/upload",
    status_code=status.HTTP_201_CREATED,
)
async def upload_material(
    course_id: str,
    material_type: str = Form(...),
    title: str | None = Form(default=None),
    linked_assessment_id: str | None = Form(default=None),
    week_number: int | None = Form(default=None),
    relevant_date: str | None = Form(default=None),
    file: UploadFile = File(...),
    user: dict = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
    task_queue: TaskQueueService = Depends(get_task_queue),
):
    sb = get_authenticated_supabase(user, settings)

    # Rate limit
    check_rate_limit(sb, user["id"], "material_upload")

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

    # Validate file extension
    filename = file.filename or "upload"
    ext = _get_extension(filename)
    if ext not in ALLOWED_MATERIAL_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported file type: {ext}. Allowed: {sorted(ALLOWED_MATERIAL_EXTENSIONS)}",
        )

    # Stream file and check size
    import tempfile

    spooled = tempfile.SpooledTemporaryFile(max_size=10 * 1024 * 1024)
    total_bytes = 0
    while True:
        chunk = await file.read(1024 * 1024)  # 1 MB chunks
        if not chunk:
            break
        total_bytes += len(chunk)
        if total_bytes > MAX_MATERIAL_SIZE_BYTES:
            spooled.close()
            raise HTTPException(
                status_code=413,
                detail=(
                    f"File too large: {filename} "
                    f"({total_bytes / 1024 / 1024:.1f}MB > "
                    f"{MAX_MATERIAL_SIZE_BYTES / 1024 / 1024:.0f}MB limit)"
                ),
            )
        spooled.write(chunk)
    spooled.seek(0)
    file_bytes = spooled.read()
    spooled.close()

    # Generate material ID and upload to storage
    material_id = str(uuid.uuid4())
    storage_path = f"{user['id']}/{course_id}/{material_id}/{filename}"

    sb_admin = _sb_admin(settings)
    try:
        sb_admin.storage.from_("course-materials").upload(
            storage_path,
            file_bytes,
            {"upsert": "true", "content-type": file.content_type or "application/octet-stream"},
        )
    except Exception as storage_err:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to upload file to storage: {storage_err}",
        ) from storage_err

    # Generate signed URL for pipeline
    signed = sb_admin.storage.from_("course-materials").create_signed_url(
        storage_path, 21600,
    )
    file_url = signed["signedURL"]

    # Determine title
    effective_title = (title or "").strip() or filename

    # Create DB record
    insert_data: dict[str, Any] = {
        "id": material_id,
        "course_id": course_id,
        "user_id": user["id"],
        "title": effective_title,
        "material_type": material_type,
        "file_name": filename,
        "file_size_bytes": total_bytes,
        "storage_path": storage_path,
        "processing_status": "pending",
        "retry_count": 0,
    }
    if linked_assessment_id:
        insert_data["linked_assessment_id"] = linked_assessment_id
    if week_number is not None:
        insert_data["week_number"] = week_number
    if relevant_date is not None:
        insert_data["relevant_date"] = relevant_date

    result = sb.table("course_materials").insert(insert_data).execute()

    # Enqueue processing
    await task_queue.enqueue_material_processing(
        material_id=material_id,
        course_id=course_id,
        user_id=user["id"],
        file_url=file_url,
        file_name=filename,
        material_type=material_type,
        title=effective_title,
        supabase_url=settings.SUPABASE_URL,
        supabase_key=settings.SUPABASE_ANON_KEY,
        user_token=user["token"],
    )

    record = result.data[0]
    return MaterialResponse(
        id=record["id"],
        course_id=record["course_id"],
        user_id=record["user_id"],
        title=record["title"],
        material_type=record["material_type"],
        file_name=record["file_name"],
        file_size_bytes=record.get("file_size_bytes"),
        processing_status=record["processing_status"],
        retry_count=record.get("retry_count", 0),
        created_at=record.get("created_at"),
    )


@router.get(
    "/courses/{course_id}/materials",
    response_model=MaterialListResponse,
)
async def list_course_materials(
    course_id: str,
    material_type: str | None = None,
    user: dict = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
):
    sb = get_authenticated_supabase(user, settings)

    query = (
        sb.table("course_materials")
        .select("*")
        .eq("course_id", course_id)
        .eq("user_id", user["id"])
    )
    if material_type:
        query = query.eq("material_type", material_type)

    result = query.order("created_at", desc=True).execute()

    materials = [
        MaterialResponse(
            id=row["id"],
            course_id=row["course_id"],
            user_id=row["user_id"],
            title=row["title"],
            material_type=row["material_type"],
            file_name=row["file_name"],
            file_size_bytes=row.get("file_size_bytes"),
            processing_status=row.get("processing_status", "pending"),
            retry_count=row.get("retry_count", 0),
            created_at=row.get("created_at"),
        )
        for row in (result.data or [])
    ]
    return MaterialListResponse(materials=materials)


@router.get(
    "/materials/{material_id}",
    response_model=MaterialDetailResponse,
)
async def get_material(
    material_id: str,
    user: dict = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
):
    sb = get_authenticated_supabase(user, settings)
    material = _verify_ownership(sb, "course_materials", material_id, user["id"], "Material")

    # Generate signed URL
    file_url = None
    storage_path = material.get("storage_path")
    if storage_path:
        sb_admin = _sb_admin(settings)
        try:
            signed = sb_admin.storage.from_("course-materials").create_signed_url(
                storage_path, 21600,
            )
            file_url = signed["signedURL"]
        except Exception:
            pass

    # Get chunk count
    chunk_count = None
    try:
        chunks_result = (
            sb.table("material_chunks")
            .select("id", count="exact")
            .eq("material_id", material_id)
            .execute()
        )
        chunk_count = chunks_result.count
    except Exception:
        pass

    return MaterialDetailResponse(
        id=material["id"],
        course_id=material["course_id"],
        user_id=material["user_id"],
        title=material["title"],
        material_type=material["material_type"],
        file_name=material["file_name"],
        file_size_bytes=material.get("file_size_bytes"),
        processing_status=material.get("processing_status", "pending"),
        retry_count=material.get("retry_count", 0),
        created_at=material.get("created_at"),
        file_url=file_url,
        linked_assessment_id=material.get("linked_assessment_id"),
        week_number=material.get("week_number"),
        relevant_date=material.get("relevant_date"),
        chunk_count=chunk_count,
        processing_error=material.get("processing_error"),
    )


@router.get(
    "/materials/{material_id}/status",
    response_model=MaterialStatusResponse,
)
async def get_material_status(
    material_id: str,
    user: dict = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
):
    sb = get_authenticated_supabase(user, settings)
    material = _verify_ownership(sb, "course_materials", material_id, user["id"], "Material")

    # Get chunk count
    chunk_count = None
    try:
        chunks_result = (
            sb.table("material_chunks")
            .select("id", count="exact")
            .eq("material_id", material_id)
            .execute()
        )
        chunk_count = chunks_result.count
    except Exception:
        pass

    return MaterialStatusResponse(
        id=material["id"],
        processing_status=material.get("processing_status", "pending"),
        processing_error=material.get("processing_error"),
        retry_count=material.get("retry_count", 0),
        chunk_count=chunk_count,
    )


@router.delete(
    "/materials/{material_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_material(
    material_id: str,
    user: dict = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
):
    sb = get_authenticated_supabase(user, settings)
    material = _verify_ownership(sb, "course_materials", material_id, user["id"], "Material")

    # Delete from storage
    storage_path = material.get("storage_path")
    if storage_path:
        sb_admin = _sb_admin(settings)
        with contextlib.suppress(Exception):
            sb_admin.storage.from_("course-materials").remove([storage_path])

    # Delete DB record (CASCADE cleans up material_chunks)
    sb.table("course_materials").delete().eq("id", material_id).execute()


@router.post("/materials/{material_id}/retry")
async def retry_material(
    material_id: str,
    user: dict = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
    task_queue: TaskQueueService = Depends(get_task_queue),
):
    sb = get_authenticated_supabase(user, settings)
    material = _verify_ownership(sb, "course_materials", material_id, user["id"], "Material")

    if material["processing_status"] != "failed":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Material is not in failed state",
        )

    retry_count = material.get("retry_count", 0)
    if retry_count >= 3:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Maximum retries exceeded",
        )

    # Reset status
    new_retry = retry_count + 1
    sb.table("course_materials").update({
        "processing_status": "pending",
        "processing_error": None,
        "retry_count": new_retry,
    }).eq("id", material_id).execute()

    # Generate signed URL for re-processing
    storage_path = material.get("storage_path", "")
    file_url = ""
    if storage_path:
        sb_admin = _sb_admin(settings)
        signed = sb_admin.storage.from_("course-materials").create_signed_url(
            storage_path, 21600,
        )
        file_url = signed["signedURL"]

    await task_queue.enqueue_material_processing(
        material_id=material_id,
        course_id=material["course_id"],
        user_id=user["id"],
        file_url=file_url,
        file_name=material["file_name"],
        material_type=material["material_type"],
        title=material.get("title"),
        supabase_url=settings.SUPABASE_URL,
        supabase_key=settings.SUPABASE_ANON_KEY,
        user_token=user["token"],
        is_reprocess=True,
    )

    return MaterialResponse(
        id=material["id"],
        course_id=material["course_id"],
        user_id=material["user_id"],
        title=material["title"],
        material_type=material["material_type"],
        file_name=material["file_name"],
        file_size_bytes=material.get("file_size_bytes"),
        processing_status="pending",
        retry_count=new_retry,
        created_at=material.get("created_at"),
    )


@router.patch(
    "/materials/{material_id}",
    response_model=MaterialResponse,
)
async def update_material(
    material_id: str,
    title: str | None = None,
    material_type: str | None = None,
    linked_assessment_id: str | None = None,
    week_number: int | None = None,
    relevant_date: str | None = None,
    user: dict = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
):
    sb = get_authenticated_supabase(user, settings)
    material = _verify_ownership(sb, "course_materials", material_id, user["id"], "Material")

    update_data: dict[str, Any] = {}
    if title is not None:
        update_data["title"] = title
    if material_type is not None:
        update_data["material_type"] = material_type
    if linked_assessment_id is not None:
        update_data["linked_assessment_id"] = linked_assessment_id
    if week_number is not None:
        update_data["week_number"] = week_number
    if relevant_date is not None:
        update_data["relevant_date"] = relevant_date

    if not update_data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No fields to update",
        )

    result = (
        sb.table("course_materials")
        .update(update_data)
        .eq("id", material_id)
        .execute()
    )

    row = result.data[0] if result.data else {**material, **update_data}
    return MaterialResponse(
        id=row["id"],
        course_id=row["course_id"],
        user_id=row["user_id"],
        title=row["title"],
        material_type=row["material_type"],
        file_name=row["file_name"],
        file_size_bytes=row.get("file_size_bytes"),
        processing_status=row.get("processing_status", "pending"),
        retry_count=row.get("retry_count", 0),
        created_at=row.get("created_at"),
    )
