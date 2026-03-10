"""Pydantic models for course material processing and API responses."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field


class MaterialType(StrEnum):
    READING = "reading"
    HOMEWORK = "homework"
    PRACTICE_EXAM = "practice_exam"
    ASSIGNMENT_OUTLINE = "assignment_outline"
    LAB_MANUAL = "lab_manual"
    STUDY_GUIDE = "study_guide"
    PROBLEM_SET = "problem_set"
    OTHER = "other"


ALLOWED_MATERIAL_EXTENSIONS = {".pdf", ".docx", ".pptx", ".txt", ".md"}
MAX_MATERIAL_SIZE_BYTES = 50 * 1024 * 1024  # 50 MB


class MaterialUploadRequest(BaseModel):
    """Request body for material upload (non-file fields)."""

    material_type: MaterialType
    title: str | None = None
    linked_assessment_id: str | None = None
    linked_lecture_id: str | None = None
    week_number: int | None = Field(None, ge=1, le=52)
    relevant_date: str | None = None  # ISO date string


class MaterialResponse(BaseModel):
    """API response for a single material."""

    id: str
    course_id: str
    title: str
    material_type: str
    file_name: str | None = None
    processing_status: str
    processing_progress: float = 0.0
    processing_error: str | None = None
    linked_assessment_id: str | None = None
    linked_lecture_id: str | None = None
    week_number: int | None = None
    relevant_date: str | None = None
    concept_count: int = 0
    chunk_count: int = 0
    created_at: str


class MaterialDetailResponse(MaterialResponse):
    """Extended response with text preview and file URL."""

    file_url: str | None = None  # Signed URL
    extracted_text_preview: str | None = None
    page_count: int | None = None


class MaterialStatusResponse(BaseModel):
    """Processing status response."""

    id: str
    processing_status: str
    processing_stage: str | None = None
    processing_progress: float = 0.0
    processing_error: str | None = None


class MaterialListResponse(BaseModel):
    """List response with materials."""

    materials: list[MaterialResponse]
    total: int


# --- Pipeline intermediate models ---


class TextSection(BaseModel):
    """A section within an extracted document."""

    title: str | None = None
    content: str
    page_number: int | None = None


class ExtractedText(BaseModel):
    """Result of text extraction from a material document."""

    text: str
    page_count: int | None = None
    sections: list[TextSection] = []
    preview: str = ""  # First ~500 chars


class MaterialChunk(BaseModel):
    """A processed chunk ready for storage."""

    chunk_index: int
    content: str
    page_number: int | None = None
    section_title: str | None = None
    embedding: list[float] | None = None
