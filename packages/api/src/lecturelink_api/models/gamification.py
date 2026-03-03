"""Pydantic models for gamification API responses."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class XPEvent(BaseModel):
    amount: int
    source: str
    total_xp: int
    level: int
    leveled_up: bool


class StreakInfo(BaseModel):
    current_streak: int
    longest_streak: int
    studied_today: bool
    freeze_available: bool
    streak_milestone: int | None = None


class LevelInfo(BaseModel):
    current_level: int
    total_xp: int
    xp_to_next_level: int
    progress_percent: float


class BadgeEarned(BaseModel):
    badge_id: str
    name: str
    description: str
    icon: str
    category: str
    earned_at: datetime | None = None


class GamificationState(BaseModel):
    streak: StreakInfo
    level: LevelInfo
    today_xp: int
    badges_count: int
    recent_badges: list[BadgeEarned]


class AssessmentReadiness(BaseModel):
    assessment_id: str
    title: str
    due_date: datetime | None = None
    weight_percent: float | None = None
    type: str
    readiness_score: float
    days_until_due: int | None = None
    urgency: str
    trend: float
    concept_scores: list[dict]


class CourseReadinessSummary(BaseModel):
    course_id: str
    course_name: str
    overall_readiness: float
    next_assessment: dict | None = None
    concepts_mastered: int
    concepts_total: int


class GradeProjection(BaseModel):
    projected_grade_low: float
    projected_grade_high: float
    grade_letter: str
    completed_assessments: list[dict]
    upcoming_assessments: list[dict]


class WeeklyProgress(BaseModel):
    sessions_count: int
    concepts_improved: int
    total_xp: int
    readiness_changes: list[dict]
    xp_by_day: list[dict]
