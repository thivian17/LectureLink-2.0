"""Study Tutor API endpoints."""

from __future__ import annotations

import logging
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, status
from supabase import create_client

from lecturelink_api.auth import get_current_user
from lecturelink_api.config import Settings, get_settings
from lecturelink_api.models.tutor_models import (
    AssessmentReadinessResponse,
    ChatResponse,
    DiagnosticResultResponse,
    GradingFeedbackRequest,
    GradingResultResponse,
    SessionEntryResponse,
    TutorAnswerRequest,
    TutorChatRequest,
    TutorDiagnosticStartRequest,
    TutorDiagnosticSubmitRequest,
    TutorSessionResponse,
    TutorSessionStartRequest,
    TutorSessionSummaryResponse,
)
from lecturelink_api.services.tutor import (
    complete_session,
    create_session,
    get_active_session,
    get_session_entry_data,
    get_session_history,
    get_session_summary,
    log_session_event,
    pause_session,
    resume_session,
    update_session_progress,
)
from lecturelink_api.services.tutor_content import (
    generate_chat_response,
    generate_next_block,
    generate_reteach,
    generate_session_summary_text,
    pre_generate_next_concept,
)
from lecturelink_api.services.tutor_grading import grade_answer
from lecturelink_api.services.tutor_planner import (
    analyze_diagnostic,
    generate_diagnostic,
    generate_lesson_plan,
    get_assessment_readiness,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["tutor"])


def _sb(user: dict, settings: Settings):
    """Build a Supabase client authenticated with the user's token."""
    client = create_client(settings.SUPABASE_URL, settings.SUPABASE_ANON_KEY)
    client.auth.set_session(user["token"], "")
    return client


def _verify_course_ownership(sb, course_id: str, user_id: str) -> dict:
    """Fetch course and verify ownership."""
    result = (
        sb.table("courses")
        .select("*")
        .eq("id", course_id)
        .eq("user_id", user_id)
        .execute()
    )
    if not result.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Course not found",
        )
    return result.data[0]


def _verify_session_ownership(sb, session_id: str, user_id: str) -> dict:
    """Fetch session and verify ownership."""
    result = (
        sb.table("tutor_sessions")
        .select("*")
        .eq("id", session_id)
        .eq("user_id", user_id)
        .execute()
    )
    if not result.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found",
        )
    return result.data[0]


# -----------------------------------------------------------------------
# 1. GET /{course_id}/entry
# -----------------------------------------------------------------------


@router.get(
    "/{course_id}/entry",
    response_model=SessionEntryResponse,
)
async def entry_endpoint(
    course_id: str,
    user: dict = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
):
    sb = _sb(user, settings)
    _verify_course_ownership(sb, course_id, user["id"])
    return await get_session_entry_data(sb, course_id, user["id"])


# -----------------------------------------------------------------------
# 2. POST /{course_id}/session/start
# -----------------------------------------------------------------------


@router.post(
    "/{course_id}/session/start",
    response_model=TutorSessionResponse,
    status_code=status.HTTP_201_CREATED,
)
async def start_session(
    course_id: str,
    body: TutorSessionStartRequest,
    user: dict = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
):
    sb = _sb(user, settings)
    _verify_course_ownership(sb, course_id, user["id"])

    # Return existing active session if one exists and has a valid plan
    existing = await get_active_session(sb, course_id, user["id"])
    if existing is not None:
        plan = existing.lesson_plan
        has_concepts = (
            plan
            and isinstance(plan.get("concepts"), list)
            and len(plan["concepts"]) > 0
        )
        if has_concepts:
            return existing
        # Abandon broken session (no concepts) so a new one can be created
        await complete_session(sb, existing.id, user["id"])
        logger.info(
            "Auto-abandoned empty session %s to create a new one",
            existing.id,
        )

    # Generate lesson plan via AI planner
    try:
        lesson_plan = await generate_lesson_plan(
            supabase=sb,
            course_id=course_id,
            user_id=user["id"],
            mode=body.mode,
            target_assessment_id=body.target_assessment_id,
            custom_topic=body.custom_topic,
            concept_ids=body.concept_ids,
        )
    except Exception:
        logger.warning("Lesson plan generation failed", exc_info=True)
        # Build a minimal plan so the session isn't empty — content will
        # be generated on demand via the next-block endpoint.
        from lecturelink_api.services.tutor_planner import get_priority_concepts

        try:
            fallback_concepts = await get_priority_concepts(
                sb, course_id, user["id"], body.target_assessment_id,
            )
        except Exception:
            fallback_concepts = []

        if fallback_concepts:
            lesson_plan = {
                "session_title": f"Study Session: {fallback_concepts[0]['title']}",
                "estimated_duration_minutes": 30,
                "concepts": [
                    {
                        "concept_id": c.get("concept_id"),
                        "title": c["title"],
                        "mastery": c["mastery"],
                        "priority_score": c["priority_score"],
                        "teaching_approach": c["teaching_approach"],
                        "estimated_minutes": 8,
                        "outline": [
                            {"type": "explain", "description": f"Explain {c['title']}"},
                            {
                                "type": "check",
                                "description": f"Check understanding of {c['title']}",
                                "question_type": "short_answer",
                                "targets": c["title"],
                            },
                        ],
                    }
                    for c in fallback_concepts[:5]
                ],
                "wrap_up": {"type": "summary", "description": "Session wrap-up"},
            }
        else:
            lesson_plan = None

    session = await create_session(
        supabase=sb,
        course_id=course_id,
        user_id=user["id"],
        mode=body.mode,
        custom_topic=body.custom_topic,
        target_assessment_id=body.target_assessment_id,
        lesson_plan=lesson_plan,
    )

    await log_session_event(
        sb, session.id, user["id"], course_id, "session_started",
    )
    return session


# -----------------------------------------------------------------------
# 3. GET /{course_id}/session/active
# -----------------------------------------------------------------------


@router.get("/{course_id}/session/active")
async def active_session_endpoint(
    course_id: str,
    user: dict = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
):
    sb = _sb(user, settings)
    _verify_course_ownership(sb, course_id, user["id"])
    session = await get_active_session(sb, course_id, user["id"])
    if session is None:
        return None
    return session


# -----------------------------------------------------------------------
# 4. POST /session/{session_id}/answer
# -----------------------------------------------------------------------


@router.post(
    "/session/{session_id}/answer",
    response_model=GradingResultResponse,
)
async def answer_question(
    session_id: str,
    body: TutorAnswerRequest,
    user: dict = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
):
    sb = _sb(user, settings)
    session = _verify_session_ownership(sb, session_id, user["id"])

    if session["status"] != "active":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Session is not active",
        )

    # Find the question in the lesson plan
    question = _find_question_in_plan(session, body.question_id)

    grading_result = await grade_answer(question, body.student_answer, sb)

    # Log the answer event
    await log_session_event(
        sb,
        session_id,
        user["id"],
        session["course_id"],
        "question_answer",
        question_type=question.get("question_type"),
        question_text=question.get("question_text", ""),
        student_answer=body.student_answer,
        is_correct=grading_result.is_correct,
        grading_result=grading_result.model_dump(mode="json"),
        grading_confidence=grading_result.grading_confidence,
        misconception_type=grading_result.misconception_type,
        reteach_triggered=grading_result.reteach_triggered,
        time_spent_seconds=body.time_spent_seconds,
        concept_title=question.get("concept_title"),
    )

    # Update session counters
    await update_session_progress(
        sb,
        session_id,
        user["id"],
        questions_asked_delta=1,
        questions_correct_delta=1 if grading_result.is_correct else 0,
        duration_delta=body.time_spent_seconds,
    )

    # If reteach triggered, generate proper reteach content and log
    if grading_result.reteach_triggered:
        try:
            original = _get_teaching_content(
                session, question.get("concept_title", ""),
            )
            reteach_content = await generate_reteach(
                sb,
                session,
                concept_title=question.get("concept_title", ""),
                original_explanation=original,
                misconception=body.student_answer,
                misconception_type=(
                    grading_result.misconception_type or "near_miss"
                ),
            )
            grading_result.reteach_content = reteach_content
        except Exception:
            logger.warning("Reteach generation failed", exc_info=True)

        await log_session_event(
            sb,
            session_id,
            user["id"],
            session["course_id"],
            "reteach_triggered",
            misconception_type=grading_result.misconception_type,
            concept_title=question.get("concept_title"),
        )

    return grading_result


def _find_question_in_plan(session: dict, question_id: str) -> dict:
    """Find a question by ID in the lesson plan."""
    plan = session.get("lesson_plan") or {}
    for concept in plan.get("concepts", []):
        # Search pre-generated content blocks
        for block in concept.get("generated_content", {}).get("blocks", []):
            q = block.get("question", {})
            if q.get("question_id") == question_id:
                return q
        # Search outline steps
        for step in concept.get("outline", []):
            if step.get("question_id") == question_id:
                return step
        # Legacy: search "steps" and "questions"
        for step in concept.get("steps", []):
            if step.get("question_id") == question_id:
                return step
            for q in step.get("questions", []):
                if q.get("question_id") == question_id:
                    return q
        for q in concept.get("questions", []):
            if q.get("question_id") == question_id:
                return q

    # Search diagnostic questions at plan level
    for q in plan.get("questions", []):
        if q.get("question_id") == question_id:
            return q

    # If not found, return a minimal dict so grading still works
    return {"question_id": question_id, "question_type": "short_answer"}


# -----------------------------------------------------------------------
# 5. PUT /session/{session_id}/pause
# -----------------------------------------------------------------------


@router.put("/session/{session_id}/pause", status_code=status.HTTP_200_OK)
async def pause_session_endpoint(
    session_id: str,
    user: dict = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
):
    sb = _sb(user, settings)
    session = _verify_session_ownership(sb, session_id, user["id"])
    await pause_session(sb, session_id, user["id"])
    await log_session_event(
        sb, session_id, user["id"], session["course_id"], "session_paused",
    )
    return {"status": "paused"}


# -----------------------------------------------------------------------
# 6. POST /session/{session_id}/resume
# -----------------------------------------------------------------------


@router.post(
    "/session/{session_id}/resume",
    response_model=TutorSessionResponse,
)
async def resume_session_endpoint(
    session_id: str,
    user: dict = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
):
    sb = _sb(user, settings)
    session_row = _verify_session_ownership(sb, session_id, user["id"])
    result = await resume_session(sb, session_id, user["id"])
    await log_session_event(
        sb, session_id, user["id"], session_row["course_id"],
        "session_resumed",
    )
    return result


# -----------------------------------------------------------------------
# 7. PUT /session/{session_id}/complete
# -----------------------------------------------------------------------


@router.put(
    "/session/{session_id}/complete",
    response_model=TutorSessionSummaryResponse,
)
async def complete_session_endpoint(
    session_id: str,
    user: dict = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
):
    sb = _sb(user, settings)
    session_row = _verify_session_ownership(sb, session_id, user["id"])
    summary = await complete_session(sb, session_id, user["id"])

    # Generate natural-language summary via AI
    try:
        summary_text = await generate_session_summary_text({
            "mode": summary.mode,
            "concepts_covered": summary.concepts_covered,
            "total_questions": summary.total_questions,
            "total_correct": summary.total_correct,
            "accuracy_percent": summary.accuracy_percent,
            "duration_seconds": summary.duration_seconds,
        })
        summary.summary = summary_text
        sb.table("tutor_sessions").update(
            {"summary": summary_text},
        ).eq("id", session_id).execute()
    except Exception:
        logger.warning(
            "Session summary generation failed", exc_info=True,
        )

    await log_session_event(
        sb, session_id, user["id"], session_row["course_id"],
        "session_completed",
    )
    return summary


# -----------------------------------------------------------------------
# 8. POST /session/{session_id}/grading-feedback
# -----------------------------------------------------------------------


@router.post(
    "/session/{session_id}/grading-feedback",
    status_code=status.HTTP_201_CREATED,
)
async def submit_grading_feedback(
    session_id: str,
    body: GradingFeedbackRequest,
    user: dict = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
):
    sb = _sb(user, settings)
    _verify_session_ownership(sb, session_id, user["id"])

    sb.table("grading_feedback").insert({
        "event_id": body.event_id,
        "user_id": user["id"],
        "feedback_type": body.feedback_type,
        "feedback_text": body.feedback_text,
    }).execute()

    return {"status": "submitted"}


# -----------------------------------------------------------------------
# 9. GET /{course_id}/history
# -----------------------------------------------------------------------


@router.get(
    "/{course_id}/history",
    response_model=list[TutorSessionResponse],
)
async def history_endpoint(
    course_id: str,
    user: dict = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
):
    sb = _sb(user, settings)
    _verify_course_ownership(sb, course_id, user["id"])
    return await get_session_history(sb, course_id, user["id"])


# -----------------------------------------------------------------------
# 10. GET /session/{session_id}/summary
# -----------------------------------------------------------------------


@router.get(
    "/session/{session_id}/summary",
    response_model=TutorSessionSummaryResponse,
)
async def summary_endpoint(
    session_id: str,
    user: dict = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
):
    sb = _sb(user, settings)
    _verify_session_ownership(sb, session_id, user["id"])
    return await get_session_summary(sb, session_id, user["id"])


def _get_teaching_content(session: dict, concept_title: str) -> str:
    """Extract teaching content for a concept from the lesson plan."""
    plan = session.get("lesson_plan") or {}
    for concept in plan.get("concepts", []):
        if concept.get("title") == concept_title:
            content = concept.get("generated_content", {})
            for block in content.get("blocks", []):
                if block.get("block_type") in (
                    "explain", "activate",
                ) and block.get("content"):
                    return block["content"]
    return ""


# -----------------------------------------------------------------------
# 11. POST /session/{session_id}/next-block
# -----------------------------------------------------------------------


@router.post("/session/{session_id}/next-block")
async def next_block_endpoint(
    session_id: str,
    user: dict = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
):
    sb = _sb(user, settings)
    session = _verify_session_ownership(sb, session_id, user["id"])

    if session["status"] != "active":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Session is not active",
        )

    concept_idx = session.get("current_concept_index", 0)
    step_idx = session.get("current_step_index", 0)

    block = await generate_next_block(
        sb, session, concept_idx, step_idx,
    )

    # Advance position based on block type
    new_concept_idx = concept_idx
    new_step_idx = step_idx
    concepts_completed_delta = 0

    if block["block_type"] == "concept_complete":
        new_concept_idx = concept_idx + 1
        new_step_idx = 0
        concepts_completed_delta = 1
    elif block["block_type"] != "complete":
        new_step_idx = step_idx + 1

    await update_session_progress(
        sb,
        session_id,
        user["id"],
        concept_index=new_concept_idx,
        step_index=new_step_idx,
        concepts_completed_delta=concepts_completed_delta,
    )

    block["concept_index"] = new_concept_idx
    block["step_index"] = new_step_idx
    return block


# -----------------------------------------------------------------------
# 12. POST /session/{session_id}/generate-concept
# -----------------------------------------------------------------------


@router.post("/session/{session_id}/generate-concept")
async def generate_concept_endpoint(
    session_id: str,
    concept_index: int | None = None,
    user: dict = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
):
    sb = _sb(user, settings)
    session = _verify_session_ownership(sb, session_id, user["id"])

    if concept_index is None:
        concept_index = (
            session.get("current_concept_index", 0) + 1
        )

    content = await pre_generate_next_concept(
        sb, session, concept_index,
    )
    return content


# -----------------------------------------------------------------------
# 13. POST /session/{session_id}/chat
# -----------------------------------------------------------------------


@router.post(
    "/session/{session_id}/chat",
    response_model=ChatResponse,
)
async def chat_endpoint(
    session_id: str,
    body: TutorChatRequest,
    user: dict = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
):
    sb = _sb(user, settings)
    session = _verify_session_ownership(sb, session_id, user["id"])

    if session["status"] != "active":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Session is not active",
        )

    result = await generate_chat_response(
        sb, session, body.message,
    )

    await log_session_event(
        sb,
        session_id,
        user["id"],
        session["course_id"],
        "chat_message",
        student_answer=body.message,
    )

    return ChatResponse(
        response=result["response"],
        relevance=result["relevance"],
    )


# -----------------------------------------------------------------------
# 14. POST /session/{session_id}/diagnostic
# -----------------------------------------------------------------------


@router.post("/session/{session_id}/diagnostic")
async def diagnostic_from_session_endpoint(
    session_id: str,
    user: dict = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
):
    """Generate diagnostic questions using session context."""
    sb = _sb(user, settings)
    session = _verify_session_ownership(sb, session_id, user["id"])

    course_id = session["course_id"]
    target_assessment_id = session.get("target_assessment_id")

    # Auto-select nearest upcoming assessment if none set
    if not target_assessment_id:
        result = (
            sb.table("assessments")
            .select("id")
            .eq("course_id", course_id)
            .gte("due_date", datetime.now(UTC).isoformat())
            .order("due_date")
            .limit(1)
            .execute()
        )
        if result.data:
            target_assessment_id = result.data[0]["id"]

    if not target_assessment_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No upcoming assessments found for diagnostic",
        )

    return await generate_diagnostic(
        sb, course_id, user["id"], target_assessment_id,
    )


@router.post("/{course_id}/diagnostic")
async def diagnostic_endpoint(
    course_id: str,
    body: TutorDiagnosticStartRequest,
    user: dict = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
):
    sb = _sb(user, settings)
    _verify_course_ownership(sb, course_id, user["id"])

    return await generate_diagnostic(
        sb, course_id, user["id"], body.target_assessment_id,
    )


# -----------------------------------------------------------------------
# 15. POST /session/{session_id}/diagnostic/submit
# -----------------------------------------------------------------------


@router.post(
    "/session/{session_id}/diagnostic/submit",
    response_model=DiagnosticResultResponse,
)
async def diagnostic_submit_endpoint(
    session_id: str,
    body: TutorDiagnosticSubmitRequest,
    user: dict = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
):
    sb = _sb(user, settings)
    session = _verify_session_ownership(sb, session_id, user["id"])

    # Grade each answer
    results = []
    total_correct = 0
    for answer in body.answers:
        question = answer.get("question", {})
        student_answer = answer.get("student_answer", "")
        grading = await grade_answer(question, student_answer, sb)
        if grading.is_correct:
            total_correct += 1
        results.append({
            **answer,
            "is_correct": grading.is_correct,
            "feedback": grading.feedback,
        })

    # Analyze results
    analysis = await analyze_diagnostic(results)

    # Update session progress
    await update_session_progress(
        sb,
        session_id,
        user["id"],
        questions_asked_delta=len(body.answers),
        questions_correct_delta=total_correct,
    )

    await log_session_event(
        sb,
        session_id,
        user["id"],
        session["course_id"],
        "diagnostic_submitted",
    )

    return DiagnosticResultResponse(
        total_correct=total_correct,
        total_questions=len(body.answers),
        concept_results=analysis.get("concept_results", []),
        identified_gaps=analysis.get("identified_gaps", []),
        recommended_focus=analysis.get("recommended_focus", []),
    )


# -----------------------------------------------------------------------
# 16. GET /{course_id}/assessment/{assessment_id}/readiness
# -----------------------------------------------------------------------


@router.get(
    "/{course_id}/assessment/{assessment_id}/readiness",
    response_model=AssessmentReadinessResponse,
)
async def assessment_readiness_endpoint(
    course_id: str,
    assessment_id: str,
    user: dict = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
):
    sb = _sb(user, settings)
    _verify_course_ownership(sb, course_id, user["id"])
    return await get_assessment_readiness(
        sb, course_id, user["id"], assessment_id,
    )
