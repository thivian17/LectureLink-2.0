"""Pydantic models for the Readiness V2 system."""

from __future__ import annotations

from pydantic import BaseModel

# Assessment types eligible for readiness scoring
EXAM_TYPES = {"exam", "midterm", "quiz", "test", "final"}


class ReadinessBreakdown(BaseModel):
    """The four readiness signals for one assessment."""

    coverage: float  # 0.0 - 1.0
    practice: float  # 0.0 - 1.0
    freshness: float  # 0.0 - 1.0
    effort: float  # 0.0 - 1.0


class WeakConcept(BaseModel):
    """A concept contributing least to readiness."""

    concept_id: str
    title: str
    coverage: bool  # has any interaction
    practice_score: float  # correctness ratio
    freshness_score: float  # decay-based
    combined_score: float  # weighted contribution


class SuggestedAction(BaseModel):
    """A recommended preparation action."""

    action_type: str  # "study_session" | "practice_test" | "flash_review"
    title: str
    description: str
    estimated_minutes: int
    target_course_id: str | None = None
    target_assessment_id: str | None = None
    urgency: str  # "critical" | "high" | "medium" | "low"
    expected_impact: str  # e.g., "+12% readiness"


class AssessmentReadinessV2(BaseModel):
    """Full readiness report for one assessment."""

    assessment_id: str
    title: str
    course_id: str
    course_name: str | None = None
    assessment_type: str
    due_date: str | None = None
    days_until_due: int | None = None
    readiness: float  # 0.0 - 1.0 weighted composite
    breakdown: ReadinessBreakdown
    weak_concepts: list[WeakConcept]  # top 3-5 weakest
    suggested_actions: list[SuggestedAction]
    urgency: str  # "critical" | "high" | "medium" | "low"
    concept_count: int  # total linked concepts
    covered_count: int  # concepts with any interaction


class CourseIntelligenceV2(BaseModel):
    """Course-level readiness summary for the dashboard."""

    course_id: str
    course_name: str
    course_code: str | None = None
    readiness: float  # avg across exam-type assessments
    risk: str  # "low" | "medium" | "high"
    next_assessment: dict | None = None  # {title, type, due_date, days_until, readiness}
    recommended_action: SuggestedAction | None = None
    assessment_count: int = 0


class TimelineItem(BaseModel):
    """One item on the 14-day academic timeline."""

    date: str  # ISO date
    item_type: str  # "exam" | "quiz" | "midterm" | "assignment" | "project" | "discussion" | "practice_quiz"
    title: str
    course_id: str
    course_name: str
    course_code: str | None = None
    assessment_id: str | None = None
    readiness: float | None = None  # only for exam-type
    urgency: str | None = None  # only for exam-type
    needs_review: bool = False  # for lectures: student hasn't interacted


class DashboardTimelineResponse(BaseModel):
    """Response for the 14-day academic timeline endpoint."""

    items: list[TimelineItem]
    today: str  # ISO date


class DashboardActionsResponse(BaseModel):
    """Response for the best-next-actions endpoint."""

    actions: list[SuggestedAction]


class DashboardCoursesResponse(BaseModel):
    """Response for the course intelligence cards endpoint."""

    courses: list[CourseIntelligenceV2]


class StatsRow(BaseModel):
    """Compact weekly stats for the command center header."""

    streak: int
    xp_this_week: int
    study_minutes_this_week: int
    concepts_practiced_this_week: int
