"""Pydantic models for Learn Mode endpoints."""

from __future__ import annotations

from pydantic import BaseModel, Field


class StartSessionRequest(BaseModel):
    time_budget_minutes: int = Field(default=15, ge=10, le=25)


class StartSessionResponse(BaseModel):
    session_id: str
    daily_briefing: dict
    flash_review_cards: list[dict]


class FlashReviewAnswerRequest(BaseModel):
    card_id: str
    answer_index: int
    time_ms: int = 0


class GutCheckAnswerRequest(BaseModel):
    concept_id: str
    answer_index: int


class QuizAnswerRequest(BaseModel):
    question_id: str
    answer_index: int
    time_ms: int = 0


class SessionCompleteResponse(BaseModel):
    session_summary: dict
    xp_summary: dict
    streak: dict
    badges_earned: list[dict]
    tomorrow_preview: str
