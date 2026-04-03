"""Routes for quiz generation, submission, and concept browsing."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from lecturelink_api.auth import get_authenticated_supabase, get_current_user
from lecturelink_api.config import Settings, get_settings
from lecturelink_api.middleware.rate_limit import check_rate_limit
from lecturelink_api.models.api_models import (
    ConceptResponse,
    QuizGenerateRequest,
    QuizQuestionResponse,
    QuizResponse,
    QuizSubmissionResult,
    QuizSubmitRequest,
)
from lecturelink_api.services.quiz import score_quiz
from lecturelink_api.services.task_queue import TaskQueueService, get_task_queue


class HintRequest(BaseModel):
    hint_index: int = 0

router = APIRouter(prefix="/api", tags=["quizzes"])

LABELS = ["A", "B", "C", "D"]


def _resolve_correct_answer(raw_options: list | None, correct_answer: str | None) -> str | None:
    """Resolve correct_answer to the option text the frontend displays.

    The LLM may store correct_answer as a label ("A"), the full text, or
    "A. text".  The frontend compares selectedAnswer (option text) against
    correct_answer, so we must return the option text.
    """
    if not correct_answer or not raw_options:
        return correct_answer

    # Build text list and find the is_correct option
    texts: list[str] = []
    is_correct_text: str | None = None
    for opt in raw_options:
        if isinstance(opt, dict):
            text = opt.get("text", "")
            texts.append(text)
            if opt.get("is_correct"):
                is_correct_text = text
        else:
            texts.append(str(opt))

    # If correct_answer already matches an option text, use it
    for t in texts:
        if correct_answer == t:
            return correct_answer

    # If correct_answer is a label (A/B/C/D), return corresponding text
    label = correct_answer.strip().upper()
    if label in LABELS:
        idx = LABELS.index(label)
        if idx < len(texts):
            return texts[idx]

    # If correct_answer is "A. Some text" format, strip the label prefix
    if len(correct_answer) > 2 and correct_answer[1] in ".)" and correct_answer[0].upper() in LABELS:
        stripped = correct_answer[2:].strip()
        for t in texts:
            if stripped == t:
                return t

    # Fall back to the is_correct flagged option
    if is_correct_text:
        return is_correct_text

    return correct_answer


def _resolve_correct_option_index(
    raw_options: list | None,
    correct_answer: str | None,
    question_type: str | None = None,
) -> int | None:
    """Compute the 0-based index of the correct option.

    For MCQ: checks is_correct flag first, then falls back to matching
    correct_answer against labels/text.
    For true_false: normalizes common variants to find the index.
    For short_answer or missing options: returns None.
    """
    if not raw_options:
        return None

    # Strategy 1: Find the option with is_correct=True (most reliable)
    for i, opt in enumerate(raw_options):
        if isinstance(opt, dict) and opt.get("is_correct"):
            return i

    # No is_correct flags — fall back to matching correct_answer
    if not correct_answer:
        return None

    # Build text list
    texts: list[str] = []
    for opt in raw_options:
        if isinstance(opt, dict):
            texts.append(opt.get("text", ""))
        else:
            texts.append(str(opt))

    # Strategy 2a: Exact text match
    for i, t in enumerate(texts):
        if correct_answer == t:
            return i

    # Strategy 2b: Case-insensitive text match
    ca_lower = correct_answer.strip().lower()
    for i, t in enumerate(texts):
        if ca_lower == t.strip().lower():
            return i

    # Strategy 3: Label match (A/B/C/D)
    label = correct_answer.strip().upper()
    if label in LABELS:
        idx = LABELS.index(label)
        if idx < len(texts):
            return idx

    # Strategy 4: "A. Some text" or "A) Some text" format
    if (
        len(correct_answer) > 2
        and correct_answer[1] in ".)"
        and correct_answer[0].upper() in LABELS
    ):
        stripped = correct_answer[2:].strip()
        for i, t in enumerate(texts):
            if stripped == t:
                return i

    # Strategy 5: true_false normalization
    if question_type == "true_false":
        if ca_lower in ("true", "t", "yes"):
            for i, t in enumerate(texts):
                if t.strip().lower() == "true":
                    return i
        elif ca_lower in ("false", "f", "no"):
            for i, t in enumerate(texts):
                if t.strip().lower() == "false":
                    return i

    return None




@router.post("/quizzes/generate", status_code=status.HTTP_201_CREATED)
async def generate_quiz(
    body: QuizGenerateRequest,
    user: dict = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
    task_queue: TaskQueueService = Depends(get_task_queue),
):
    sb = get_authenticated_supabase(user, settings)

    # Rate limit
    check_rate_limit(sb, user["id"], "quiz_generate")

    # Verify course ownership
    course = (
        sb.table("courses")
        .select("id, name")
        .eq("id", body.course_id)
        .eq("user_id", user["id"])
        .execute()
    )
    if not course.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Course not found"
        )

    # Generate title
    title = f"Practice Quiz - {course.data[0]['name']}"
    if body.target_assessment_id:
        assessment = (
            sb.table("assessments")
            .select("title")
            .eq("id", body.target_assessment_id)
            .execute()
        )
        if assessment.data:
            title = f"Quiz: {assessment.data[0]['title']}"
    elif body.lecture_ids:
        lectures = (
            sb.table("lectures")
            .select("title")
            .in_("id", body.lecture_ids)
            .execute()
        )
        if lectures.data:
            names = [lec["title"] for lec in lectures.data[:2]]
            suffix = f" +{len(lectures.data) - 2}" if len(lectures.data) > 2 else ""
            title = f"Quiz: {', '.join(names)}{suffix}"

    # Create quiz record
    result = (
        sb.table("quizzes")
        .insert({
            "course_id": body.course_id,
            "user_id": user["id"],
            "title": title,
            "status": "generating",
            "question_count": 0,
            "difficulty": body.difficulty,
            "best_score": None,
            "attempt_count": 0,
        })
        .execute()
    )
    quiz_id = result.data[0]["id"]

    # Normalize coding_only mode
    include_coding = body.include_coding
    coding_ratio = body.coding_ratio
    num_questions = body.question_count
    if body.coding_only:
        include_coding = True
        coding_ratio = 1.0
        if num_questions > 8:
            num_questions = min(num_questions, 5)

    # Trigger background generation via arq
    await task_queue.enqueue_quiz_generation(
        supabase_url=settings.SUPABASE_URL,
        supabase_key=settings.SUPABASE_ANON_KEY,
        user_token=user["token"],
        quiz_id=quiz_id,
        course_id=body.course_id,
        user_id=user["id"],
        target_assessment_id=body.target_assessment_id,
        lecture_ids=body.lecture_ids,
        num_questions=num_questions,
        difficulty=body.difficulty,
        include_coding=include_coding,
        coding_ratio=coding_ratio,
        coding_language=body.coding_language,
        coding_only=body.coding_only,
    )

    return {"quiz_id": quiz_id, "status": "generating"}


@router.get("/quizzes/{quiz_id}")
async def get_quiz(
    quiz_id: str,
    user: dict = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
):
    sb = get_authenticated_supabase(user, settings)

    result = (
        sb.table("quizzes")
        .select("*")
        .eq("id", quiz_id)
        .eq("user_id", user["id"])
        .execute()
    )
    if not result.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Quiz not found"
        )

    quiz = result.data[0]
    response = {
        "id": quiz["id"],
        "title": quiz["title"],
        "status": quiz["status"],
        "question_count": quiz.get("question_count", 0),
        "difficulty": quiz.get("difficulty", "mixed"),
        "best_score": quiz.get("best_score"),
        "attempt_count": quiz.get("attempt_count", 0),
    }

    # Only include questions if quiz is ready
    if quiz["status"] == "ready":
        questions_result = (
            sb.table("quiz_questions")
            .select(
                "id, question_index, question_type, question_text, options,"
                " correct_answer, explanation"
            )
            .eq("quiz_id", quiz_id)
            .order("question_index")
            .execute()
        )

        # Strip is_correct from options; resolve correct_answer to option text
        safe_questions = []
        for q in questions_result.data or []:
            raw_options = q.get("options")
            safe_options = None
            if raw_options:
                safe_options = [
                    opt.get("text", "") if isinstance(opt, dict) else str(opt)
                    for opt in raw_options
                ]
            safe_questions.append(
                QuizQuestionResponse(
                    id=q["id"],
                    question_index=q["question_index"],
                    question_type=q["question_type"],
                    question_text=q["question_text"],
                    options=safe_options,
                    correct_answer=_resolve_correct_answer(
                        raw_options, q.get("correct_answer")
                    ),
                    correct_option_index=_resolve_correct_option_index(
                        raw_options, q.get("correct_answer"), q.get("question_type")
                    ),
                    explanation=q.get("explanation"),
                ).model_dump()
            )

        response["questions"] = safe_questions

    return response


@router.get("/quizzes/{quiz_id}/status")
async def get_quiz_status(
    quiz_id: str,
    user: dict = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
):
    sb = get_authenticated_supabase(user, settings)

    result = (
        sb.table("quizzes")
        .select("id, status, question_count")
        .eq("id", quiz_id)
        .eq("user_id", user["id"])
        .execute()
    )
    if not result.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Quiz not found"
        )

    quiz = result.data[0]
    quiz_status = quiz["status"]

    # Map status to a generation stage for the frontend progress UI
    if quiz_status == "generating":
        stage = "planning"
    elif quiz_status == "ready":
        stage = "ready"
    elif quiz_status == "failed":
        stage = "planning"
    else:
        stage = None

    return {
        "quiz_id": quiz["id"],
        "status": quiz_status,
        "stage": stage,
        "error_message": "Quiz generation failed. Please try again." if quiz_status == "failed" else None,
    }


@router.get("/quizzes/{quiz_id}/questions", response_model=list[QuizQuestionResponse])
async def get_quiz_questions(
    quiz_id: str,
    user: dict = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
):
    sb = get_authenticated_supabase(user, settings)

    # Verify quiz belongs to user and is ready
    quiz_result = (
        sb.table("quizzes")
        .select("id, status")
        .eq("id", quiz_id)
        .eq("user_id", user["id"])
        .execute()
    )
    if not quiz_result.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Quiz not found"
        )
    if quiz_result.data[0]["status"] != "ready":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Quiz is not ready",
        )

    questions_result = (
        sb.table("quiz_questions")
        .select(
            "id, question_index, question_type, question_text, options,"
            " correct_answer, explanation, code_metadata"
        )
        .eq("quiz_id", quiz_id)
        .order("question_index")
        .execute()
    )

    # Strip is_correct from options; resolve correct_answer to option text
    safe_questions = []
    for q in questions_result.data or []:
        raw_options = q.get("options")
        safe_options = None
        if raw_options:
            safe_options = [
                opt.get("text", "") if isinstance(opt, dict) else str(opt)
                for opt in raw_options
            ]
        safe_questions.append(
            QuizQuestionResponse(
                id=q["id"],
                question_index=q["question_index"],
                question_type=q["question_type"],
                question_text=q["question_text"],
                options=safe_options,
                correct_answer=_resolve_correct_answer(
                    raw_options, q.get("correct_answer")
                ),
                correct_option_index=_resolve_correct_option_index(
                    raw_options, q.get("correct_answer"), q.get("question_type")
                ),
                explanation=q.get("explanation"),
                code_metadata=q.get("code_metadata"),
            )
        )

    return safe_questions


@router.post("/quizzes/{quiz_id}/submit", response_model=QuizSubmissionResult)
async def submit_quiz(
    quiz_id: str,
    body: QuizSubmitRequest,
    user: dict = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
):
    sb = get_authenticated_supabase(user, settings)

    # Verify quiz exists and belongs to user
    result = (
        sb.table("quizzes")
        .select("id, status")
        .eq("id", quiz_id)
        .eq("user_id", user["id"])
        .execute()
    )
    if not result.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Quiz not found"
        )

    if result.data[0]["status"] != "ready":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Quiz is not ready for submission",
        )

    answers = [a.model_dump() for a in body.answers]
    scoring_result = await score_quiz(supabase=sb, quiz_id=quiz_id, answers=answers)

    return QuizSubmissionResult(**scoring_result)


@router.get("/courses/{course_id}/quizzes", response_model=list[QuizResponse])
async def list_course_quizzes(
    course_id: str,
    user: dict = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
):
    sb = get_authenticated_supabase(user, settings)

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

    result = (
        sb.table("quizzes")
        .select("*")
        .eq("course_id", course_id)
        .eq("user_id", user["id"])
        .order("created_at", desc=True)
        .execute()
    )

    return [
        QuizResponse(
            id=q["id"],
            title=q["title"],
            status=q["status"],
            question_count=q.get("question_count") or 0,
            difficulty=q.get("difficulty") or "mixed",
            best_score=q.get("best_score"),
            attempt_count=q.get("attempt_count") or 0,
            created_at=q["created_at"],
        )
        for q in result.data or []
    ]


@router.get("/courses/{course_id}/concepts", response_model=list[ConceptResponse])
async def list_course_concepts(
    course_id: str,
    user: dict = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
):
    sb = get_authenticated_supabase(user, settings)

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

    # Get concepts for this course
    concepts_result = (
        sb.table("concepts")
        .select("id, title, description, category, difficulty_estimate, lecture_id, subconcepts")
        .eq("course_id", course_id)
        .execute()
    )

    if not concepts_result.data:
        return []

    # Get lecture titles in bulk
    lecture_ids = list({c["lecture_id"] for c in concepts_result.data})
    lectures_result = (
        sb.table("lectures")
        .select("id, title, lecture_number")
        .in_("id", lecture_ids)
        .execute()
    )
    lecture_map = {lec["id"]: lec for lec in lectures_result.data or []}

    # Get all concept_assessment_links in bulk
    concept_ids = [c["id"] for c in concepts_result.data]
    links_result = (
        sb.table("concept_assessment_links")
        .select("concept_id, assessment_id, relevance_score")
        .in_("concept_id", concept_ids)
        .execute()
    )

    # Get assessment titles in bulk
    assessment_ids = list({lnk["assessment_id"] for lnk in links_result.data or []})
    assessments_map: dict[str, str] = {}
    if assessment_ids:
        assessments_result = (
            sb.table("assessments")
            .select("id, title")
            .in_("id", assessment_ids)
            .execute()
        )
        assessments_map = {a["id"]: a["title"] for a in assessments_result.data or []}

    # Group links by concept
    links_by_concept: dict[str, list[dict]] = {}
    for link in links_result.data or []:
        cid = link["concept_id"]
        links_by_concept.setdefault(cid, []).append({
            "assessment_id": link["assessment_id"],
            "title": assessments_map.get(link["assessment_id"], "Unknown"),
            "relevance_score": link.get("relevance_score", 0),
        })

    # Build response sorted by lecture_number, then concept title
    concepts = []
    for c in concepts_result.data:
        lecture = lecture_map.get(c["lecture_id"], {})
        concepts.append({
            "data": ConceptResponse(
                id=c["id"],
                title=c["title"],
                description=c.get("description"),
                category=c.get("category"),
                difficulty_estimate=c.get("difficulty_estimate", 0.5),
                linked_assessments=links_by_concept.get(c["id"], []),
                lecture_title=lecture.get("title", "Unknown"),
                subconcepts=c.get("subconcepts") or [],
            ),
            "lecture_number": lecture.get("lecture_number", 999),
        })

    concepts.sort(key=lambda x: (x["lecture_number"], x["data"].title))
    return [c["data"] for c in concepts]


@router.post("/quizzes/{quiz_id}/questions/{question_id}/hint")
async def get_hint(
    quiz_id: str,
    question_id: str,
    request: HintRequest,
    user: dict = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
):
    sb = get_authenticated_supabase(user, settings)

    # Verify quiz belongs to user
    quiz_result = (
        sb.table("quizzes")
        .select("id")
        .eq("id", quiz_id)
        .eq("user_id", user["id"])
        .execute()
    )
    if not quiz_result.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Quiz not found"
        )

    # Fetch the question
    question_result = (
        sb.table("quiz_questions")
        .select("id, code_metadata")
        .eq("id", question_id)
        .eq("quiz_id", quiz_id)
        .execute()
    )
    if not question_result.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Question not found"
        )

    question = question_result.data[0]
    code_metadata = question.get("code_metadata")

    if not code_metadata or not code_metadata.get("hints"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No hints available for this question",
        )

    hints = code_metadata["hints"]
    if request.hint_index < 0 or request.hint_index >= len(hints):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"hint_index must be between 0 and {len(hints) - 1}",
        )

    return {
        "hint": hints[request.hint_index],
        "hints_remaining": len(hints) - request.hint_index - 1,
        "hint_index": request.hint_index,
    }
