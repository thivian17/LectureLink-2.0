"""Pydantic models for the Study Tutor system."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------


class TutorSessionStartRequest(BaseModel):
    mode: Literal["diagnostic", "full_lesson", "custom_topic"]
    custom_topic: str | None = None
    target_assessment_id: str | None = None
    concept_ids: list[str] | None = None


class TutorAnswerRequest(BaseModel):
    question_id: str
    student_answer: str
    time_spent_seconds: int = 0


class TutorChatRequest(BaseModel):
    message: str


class TutorDiagnosticSubmitRequest(BaseModel):
    answers: list[dict]


class TutorDiagnosticStartRequest(BaseModel):
    target_assessment_id: str


class GradingFeedbackRequest(BaseModel):
    event_id: str
    feedback_type: Literal["accurate", "inaccurate"]
    feedback_text: str | None = None


# ---------------------------------------------------------------------------
# Response models
# ---------------------------------------------------------------------------


class TutorSessionResponse(BaseModel):
    id: str
    course_id: str
    mode: str
    status: str
    lesson_plan: dict | None = None
    current_concept_index: int = 0
    current_step_index: int = 0
    concepts_planned: int = 0
    concepts_completed: int = 0
    questions_asked: int = 0
    questions_correct: int = 0
    duration_seconds: int = 0
    suggested_duration_minutes: int = 30
    target_assessment_id: str | None = None
    started_at: str
    created_at: str


class TutorSessionSummaryResponse(BaseModel):
    session_id: str
    mode: str
    concepts_covered: list[dict] = Field(default_factory=list)
    total_questions: int = 0
    total_correct: int = 0
    accuracy_percent: float = 0.0
    duration_seconds: int = 0
    mastery_changes: list[dict] | None = None
    summary: str | None = None


class GradingResultResponse(BaseModel):
    is_correct: bool
    feedback: str
    misconception_type: str | None = None
    reteach_triggered: bool = False
    reteach_content: str | None = None
    grading_confidence: float = 1.0
    rubric_evaluation: dict | None = None
    model_answer: str | None = None


class ChatResponse(BaseModel):
    response: str
    relevance: Literal["on_topic", "related", "off_topic"]


class DiagnosticResultResponse(BaseModel):
    total_correct: int
    total_questions: int
    concept_results: list[dict] = Field(default_factory=list)
    identified_gaps: list[str] = Field(default_factory=list)
    recommended_focus: list[str | dict] = Field(default_factory=list)


class ConceptReadiness(BaseModel):
    concept_id: str | None = None
    title: str
    mastery: float
    covered: bool
    teaching_approach: str  # foundational/application/synthesis
    lecture_title: str | None = None


class AssessmentReadinessResponse(BaseModel):
    assessment_id: str
    assessment_title: str
    due_date: str | None = None
    days_remaining: int | None = None
    concepts: list[ConceptReadiness]
    overall_readiness: float
    ready_count: int
    total_count: int


class AssessmentChoice(BaseModel):
    id: str
    title: str
    due_date: str
    weight_percent: float | None = None
    days_remaining: int


class SessionEntryResponse(BaseModel):
    upcoming_assessments: list[AssessmentChoice] = Field(default_factory=list)
    active_session: TutorSessionResponse | None = None
    mastery_summary: list[dict] = Field(default_factory=list)
    suggested_duration_minutes: int = 30
