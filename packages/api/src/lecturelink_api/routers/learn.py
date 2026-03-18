"""Routes for Learn Mode sessions."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, status
from supabase import create_client

from lecturelink_api.auth import get_current_user
from lecturelink_api.config import Settings, get_settings
from lecturelink_api.models.learn import (
    FlashReviewAnswerRequest,
    GutCheckAnswerRequest,
    QuizAnswerRequest,
    SessionCompleteResponse,
    StartSessionRequest,
    StartSessionResponse,
)
from lecturelink_api.services.learn_session import (
    abandon_learn_session,
    complete_learn_session,
    get_concept_brief,
    get_power_quiz,
    get_session,
    start_learn_session,
    submit_flash_review_answer,
    submit_gut_check,
    submit_power_quiz_answer,
)
from lecturelink_api.services.lecture_mastery import get_lecture_mastery
from lecturelink_api.services.spaced_repetition import (
    get_priority_concepts as get_priority_concepts_service,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/learn", tags=["learn"])


def _sb(user: dict, settings: Settings):
    client = create_client(settings.SUPABASE_URL, settings.SUPABASE_ANON_KEY)
    client.auth.set_session(user["token"], "")
    return client


@router.post("/{course_id}/session/start", response_model=StartSessionResponse)
async def start_session(
    course_id: str,
    body: StartSessionRequest,
    user: dict = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
):
    sb = _sb(user, settings)
    result = await start_learn_session(
        sb,
        user_id=user["id"],
        course_id=course_id,
        time_budget_minutes=body.time_budget_minutes,
        target_assessment_id=body.target_assessment_id,
        target_lecture_id=body.target_lecture_id,
        target_concept_ids=body.target_concept_ids,
    )
    return StartSessionResponse(**result)


@router.post("/session/{session_id}/flash-review")
async def submit_flash_review(
    session_id: str,
    body: FlashReviewAnswerRequest,
    user: dict = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
):
    sb = _sb(user, settings)

    # Grade the flash review card

    # Get session to find the card data
    session = await get_session(sb, user["id"], session_id)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Session not found"
        )

    # Record the answer
    result = await submit_flash_review_answer(
        sb,
        user_id=user["id"],
        session_id=session_id,
        card_id=body.card_id,
        answer_index=body.answer_index,
        time_ms=body.time_ms,
    )

    return result


@router.get("/session/{session_id}/concept/{index}")
async def get_concept(
    session_id: str,
    index: int,
    user: dict = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
):
    sb = _sb(user, settings)
    try:
        brief = await get_concept_brief(
            sb,
            user_id=user["id"],
            session_id=session_id,
            concept_index=index,
        )
        return brief
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(e)
        ) from e
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Concept brief generation failed for session %s concept %d", session_id, index, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Failed to generate concept brief. Please try again.",
        ) from e


@router.post("/session/{session_id}/gut-check")
async def submit_gut_check_answer(
    session_id: str,
    body: GutCheckAnswerRequest,
    user: dict = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
):
    sb = _sb(user, settings)
    try:
        result = await submit_gut_check(
            sb,
            user_id=user["id"],
            session_id=session_id,
            concept_id=body.concept_id,
            answer_index=body.answer_index,
        )
        return result
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(e)
        ) from e


@router.get("/session/{session_id}/quiz")
async def get_quiz(
    session_id: str,
    user: dict = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
):
    sb = _sb(user, settings)
    try:
        result = await get_power_quiz(
            sb, user_id=user["id"], session_id=session_id
        )
        return result
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(e)
        ) from e


@router.post("/session/{session_id}/quiz/answer")
async def submit_quiz_answer(
    session_id: str,
    body: QuizAnswerRequest,
    user: dict = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
):
    sb = _sb(user, settings)
    try:
        result = await submit_power_quiz_answer(
            sb,
            user_id=user["id"],
            session_id=session_id,
            question_id=body.question_id,
            answer_index=body.answer_index,
            time_ms=body.time_ms,
        )
        return result
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(e)
        ) from e


@router.put("/session/{session_id}/complete", response_model=SessionCompleteResponse)
async def complete_session(
    session_id: str,
    user: dict = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
):
    sb = _sb(user, settings)
    try:
        result = await complete_learn_session(
            sb, user_id=user["id"], session_id=session_id
        )
        return SessionCompleteResponse(**result)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(e)
        ) from e


@router.put("/session/{session_id}/abandon")
async def abandon_session(
    session_id: str,
    user: dict = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
):
    sb = _sb(user, settings)
    try:
        result = await abandon_learn_session(
            sb, user_id=user["id"], session_id=session_id
        )
        return result
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(e)
        ) from e


@router.get("/session/{session_id}")
async def get_session_state(
    session_id: str,
    user: dict = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
):
    sb = _sb(user, settings)
    session = await get_session(sb, user["id"], session_id)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Session not found"
        )
    return session


@router.get("/lecture-mastery/{course_id}")
async def lecture_mastery(
    course_id: str,
    user: dict = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
):
    """Per-lecture mastery stats for a course."""
    sb = _sb(user, settings)
    return await get_lecture_mastery(sb, user["id"], course_id)


@router.get("/priority-concepts/{course_id}")
async def priority_concepts(
    course_id: str,
    limit: int = 10,
    user: dict = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
):
    """Top N priority concepts for spaced repetition study."""
    sb = _sb(user, settings)
    return await get_priority_concepts_service(sb, user["id"], course_id, limit=limit)
