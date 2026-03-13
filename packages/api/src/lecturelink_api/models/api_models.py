"""Request/response models for the REST API (separate from extraction models)."""

from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Courses
# ---------------------------------------------------------------------------


class CourseCreate(BaseModel):
    name: str
    code: str | None = None
    professor: str | None = None
    color: str | None = None
    description: str | None = None
    semester: str | None = None
    semester_start: date | None = None
    semester_end: date | None = None
    meeting_days: list[str] = Field(min_length=1)
    meeting_time: str | None = None
    holidays: list[dict] | None = None
    target_grade: float = Field(default=0.8, ge=0.0, le=1.0)


class CourseUpdate(BaseModel):
    name: str | None = None
    code: str | None = None
    professor: str | None = None
    color: str | None = None
    description: str | None = None
    semester: str | None = None
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
    professor: str | None = None
    color: str | None = None
    description: str | None = None
    semester: str | None = None
    semester_start: date | None = None
    semester_end: date | None = None
    meeting_days: list[str] = Field(default_factory=list)
    meeting_time: str | None = None
    holidays: list = Field(default_factory=list)
    target_grade: float = 0.8
    created_at: datetime


class CourseCreateResponse(CourseResponse):
    needs_onboarding: bool = True
    is_first_course: bool = False
    onboarding_completed_at: datetime | None = None


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
    user_id: str | None = None
    title: str
    type: str
    due_date: datetime | None = None
    due_date_raw: str | None = None
    is_date_ambiguous: bool = False
    weight_percent: float | None = None
    student_score: float | None = None
    completed: bool = False
    topics: list[str] = Field(default_factory=list)
    description: str | None = None
    created_at: datetime
    updated_at: datetime | None = None


class AssessmentUpdate(BaseModel):
    title: str | None = None
    type: str | None = None
    due_date: datetime | None = None
    due_date_raw: str | None = None
    is_date_ambiguous: bool | None = None
    weight_percent: float | None = None
    completed: bool | None = None
    topics: list[str] | None = None


class AssessmentResultRequest(BaseModel):
    score_percent: float = Field(ge=0.0, le=100.0)


class AssessmentResultResponse(BaseModel):
    id: str
    title: str
    type: str
    due_date: datetime | None = None
    weight_percent: float | None = None
    student_score: float | None = None


class PriorityResponse(BaseModel):
    assessment_id: str
    title: str
    course_id: str
    due_date: datetime | None = None
    weight_percent: float | None = None
    priority_score: float


# ---------------------------------------------------------------------------
# Lectures
# ---------------------------------------------------------------------------


class LectureResponse(BaseModel):
    id: str
    course_id: str
    title: str
    lecture_number: int | None = None
    lecture_date: str | None = None
    processing_status: str
    processing_stage: str | None = None
    processing_progress: float
    summary: str | None = None
    duration_seconds: int | None = None
    created_at: datetime

class LectureStatusResponse(BaseModel):
    processing_status: str
    processing_stage: str | None = None
    processing_progress: float
    processing_error: str | None = None

class SearchResult(BaseModel):
    chunk_id: str
    lecture_id: str
    lecture_title: str
    content: str
    start_time: float | None = None
    end_time: float | None = None
    slide_number: int | None = None
    score: float
    highlight: str | None = None  # Content with search terms highlighted

class QAResponse(BaseModel):
    answer: str
    confidence: float
    source_chunks: list[dict]  # [{chunk_id, content, lecture_title, timestamp}]
    follow_up_suggestions: list[str]

class QuizResponse(BaseModel):
    id: str
    title: str
    status: str
    question_count: int
    difficulty: str
    best_score: float | None = None
    attempt_count: int
    created_at: datetime

class QuizQuestionResponse(BaseModel):
    id: str
    question_index: int
    question_type: str
    question_text: str
    options: list[str] | None = None
    correct_answer: str | None = None
    correct_option_index: int | None = None
    explanation: str | None = None
    code_metadata: dict | None = None

class QuizSubmissionResult(BaseModel):
    score: float
    total_questions: int
    correct_count: int
    results: list[dict]  # [{question_id, is_correct, correct_answer, explanation, source_chunks}]

class TranscriptSegmentResponse(BaseModel):
    start: float | None = None
    end: float | None = None
    text: str
    speaker: str = "Speaker"
    slide_number: int | None = None
    source: str = "chunk"


class SubconceptResponse(BaseModel):
    title: str
    description: str = ""
    difficulty_estimate: float = 0.5


class ConceptDetailResponse(BaseModel):
    id: str
    title: str
    description: str | None = None
    category: str = "concept"
    difficulty_estimate: float = 0.5
    linked_assessments: list[dict] = Field(default_factory=list)
    segment_indices: list[int] = Field(default_factory=list)
    subconcepts: list[SubconceptResponse] = Field(default_factory=list)


class LectureDetailResponse(BaseModel):
    id: str
    course_id: str
    title: str
    lecture_number: int | None = None
    lecture_date: str | None = None
    processing_status: str
    processing_stage: str | None = None
    processing_progress: float
    summary: str | None = None
    duration_seconds: int | None = None
    audio_url: str | None = None
    slides_url: str | None = None
    transcript_segments: list[TranscriptSegmentResponse] = Field(default_factory=list)
    concepts: list[ConceptDetailResponse] = Field(default_factory=list)
    slides: list[dict] = Field(default_factory=list)
    processing_path: str = "audio_only"
    slide_count: int | None = None
    created_at: datetime


class ConceptResponse(BaseModel):
    id: str
    title: str
    description: str | None = None
    category: str | None = None
    difficulty_estimate: float
    linked_assessments: list[dict]  # [{assessment_id, title, relevance_score}]
    lecture_title: str
    subconcepts: list[SubconceptResponse] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Search / Q&A
# ---------------------------------------------------------------------------


class SearchRequest(BaseModel):
    course_id: str
    query: str = Field(..., min_length=1)
    lecture_ids: list[str] | None = None
    limit: int = Field(default=10, ge=1, le=50)


class QARequest(BaseModel):
    course_id: str
    question: str = Field(..., min_length=1)
    lecture_ids: list[str] | None = None


# ---------------------------------------------------------------------------
# Quizzes
# ---------------------------------------------------------------------------


class QuizGenerateRequest(BaseModel):
    course_id: str
    target_assessment_id: str | None = None
    lecture_ids: list[str] | None = None
    question_count: int = Field(default=10, ge=1, le=30)
    difficulty: str = "mixed"
    include_coding: bool = False
    coding_ratio: float = Field(default=0.3, ge=0.0, le=1.0)
    coding_language: str = "python"
    coding_only: bool = False


class QuizAnswer(BaseModel):
    question_id: str
    student_answer: str
    time_spent_seconds: int | None = None


class QuizSubmitRequest(BaseModel):
    answers: list[QuizAnswer]


# ---------------------------------------------------------------------------
# Onboarding
# ---------------------------------------------------------------------------


class OnboardingStartResponse(BaseModel):
    status: str
    step: str


class OnboardingStatusResponse(BaseModel):
    path: str | None
    step: str | None
    completed_at: str | None
    welcome_message: dict | None


class SetPathRequest(BaseModel):
    path: Literal["just_starting", "mid_semester", "course_complete"]


class SetPathResponse(BaseModel):
    path: str
    mode: str
    suggested_path: str


class PersonalizedMessageRequest(BaseModel):
    force_regenerate: bool = False


class PersonalizedMessageResponse(BaseModel):
    message: str
    generated_at: str
    path: str


class LectureChecklistItem(BaseModel):
    lecture_number: int
    expected_date: str
    week_number: int
    topic_hint: str | None
    day_of_week: str
    status: str
    is_user_added: bool = False


class LectureChecklistUpdate(BaseModel):
    """User correction to a single lecture in the checklist."""
    lecture_number: int
    title: str | None = None
    lecture_date: date | None = None
    description: str | None = None


class LectureChecklistAdd(BaseModel):
    """User-added lecture that was missing from the auto-generated checklist."""
    title: str | None = None
    lecture_date: date | None = None
    description: str | None = None
    week_number: int | None = None


class SemesterProgressResponse(BaseModel):
    status: str
    progress_pct: int
    weeks_elapsed: int
    estimated_lectures_passed: int
    days_remaining: int
    past_assessments: list[dict]
    upcoming_assessments: list[dict]
    next_assessment: dict | None


class StepUpdateRequest(BaseModel):
    step: str


class OnboardingCompleteResponse(BaseModel):
    completed_at: str
    mastery_scores_seeded: int