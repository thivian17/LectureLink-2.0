"""Request/response models for the REST API (separate from extraction models)."""

from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Courses
# ---------------------------------------------------------------------------


class CourseCreate(BaseModel):
    name: str
    code: str | None = None
    semester_start: date
    semester_end: date
    meeting_days: list[str] | None = None
    meeting_time: str | None = None
    holidays: list[dict] | None = None
    target_grade: float = Field(default=0.8, ge=0.0, le=1.0)


class CourseUpdate(BaseModel):
    name: str | None = None
    code: str | None = None
    semester_start: date | None = None
    semester_end: date | None = None
    meeting_days: list[str] | None = None
    meeting_time: str | None = None
    holidays: list[dict] | None = None
    target_grade: float | None = Field(default=None, ge=0.0, le=1.0)


class CourseResponse(BaseModel):
    id: str
    user_id: str
    name: str
    code: str | None = None
    semester_start: date
    semester_end: date
    meeting_days: list[str] = Field(default_factory=list)
    meeting_time: str | None = None
    holidays: list = Field(default_factory=list)
    target_grade: float = 0.8
    created_at: datetime
    updated_at: datetime


# ---------------------------------------------------------------------------
# Syllabi
# ---------------------------------------------------------------------------


class SyllabusUploadResponse(BaseModel):
    syllabus_id: str
    status: str


class SyllabusStatusResponse(BaseModel):
    syllabus_id: str
    status: str
    needs_review: bool


class SyllabusResponse(BaseModel):
    id: str
    course_id: str
    user_id: str
    file_url: str | None = None
    file_name: str | None = None
    raw_extraction: dict | None = None
    grade_breakdown: list = Field(default_factory=list)
    extraction_confidence: float | None = None
    needs_review: bool = True
    reviewed_at: datetime | None = None
    created_at: datetime


class SyllabusReviewRequest(BaseModel):
    raw_extraction: dict


# ---------------------------------------------------------------------------
# Assessments
# ---------------------------------------------------------------------------


class AssessmentResponse(BaseModel):
    id: str
    course_id: str
    syllabus_id: str | None = None
    title: str
    type: str
    due_date: date | None = None
    due_date_raw: str | None = None
    is_date_ambiguous: bool = False
    weight_percent: float | None = None
    topics: list[str] = Field(default_factory=list)
    created_at: datetime


class AssessmentUpdate(BaseModel):
    title: str | None = None
    type: str | None = None
    due_date: date | None = None
    due_date_raw: str | None = None
    is_date_ambiguous: bool | None = None
    weight_percent: float | None = None
    topics: list[str] | None = None


class PriorityResponse(BaseModel):
    assessment_id: str
    title: str
    course_id: str
    due_date: date | None = None
    weight_percent: float | None = None
    priority_score: float
