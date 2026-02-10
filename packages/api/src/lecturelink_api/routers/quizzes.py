"""Routes for quiz generation, submission, and concept browsing."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.background import BackgroundTasks
from supabase import create_client

from lecturelink_api.auth import get_current_user
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
from lecturelink_api.services.quiz import generate_quiz_background, score_quiz

router = APIRouter(prefix="/api", tags=["quizzes"])


def _sb(user: dict, settings: Settings):
    client = create_client(settings.SUPABASE_URL, settings.SUPABASE_ANON_KEY)
    client.auth.set_session(user["token"], "")
    return client


@router.post("/quizzes/generate", status_code=status.HTTP_201_CREATED)
async def generate_quiz(
    body: QuizGenerateRequest,
    background_tasks: BackgroundTasks,
    user: dict = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
):
    sb = _sb(user, settings)

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

    # Trigger background generation
    background_tasks.add_task(
        generate_quiz_background,
        supabase=sb,
        quiz_id=quiz_id,
        course_id=body.course_id,
        user_id=user["id"],
        target_assessment_id=body.target_assessment_id,
        num_questions=body.num_questions,
        difficulty=body.difficulty,
    )

    return {"quiz_id": quiz_id, "status": "generating"}


@router.get("/quizzes/{quiz_id}")
async def get_quiz(
    quiz_id: str,
    user: dict = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
):
    sb = _sb(user, settings)

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
            .select("id, question_index, question_type, question_text, options")
            .eq("quiz_id", quiz_id)
            .order("question_index")
            .execute()
        )

        # CRITICAL: Strip is_correct from options — do NOT expose correct_answer
        safe_questions = []
        for q in questions_result.data or []:
            safe_options = None
            if q.get("options"):
                safe_options = [
                    {"label": opt["label"], "text": opt["text"]}
                    for opt in q["options"]
                ]
            safe_questions.append(
                QuizQuestionResponse(
                    id=q["id"],
                    question_index=q["question_index"],
                    question_type=q["question_type"],
                    question_text=q["question_text"],
                    options=safe_options,
                ).model_dump()
            )

        response["questions"] = safe_questions

    return response


@router.post("/quizzes/{quiz_id}/submit", response_model=QuizSubmissionResult)
async def submit_quiz(
    quiz_id: str,
    body: QuizSubmitRequest,
    user: dict = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
):
    sb = _sb(user, settings)

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
    scoring_result = score_quiz(supabase=sb, quiz_id=quiz_id, answers=answers)

    return QuizSubmissionResult(**scoring_result)


@router.get("/courses/{course_id}/quizzes", response_model=list[QuizResponse])
async def list_course_quizzes(
    course_id: str,
    user: dict = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
):
    sb = _sb(user, settings)

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
            question_count=q.get("question_count", 0),
            difficulty=q.get("difficulty", "mixed"),
            best_score=q.get("best_score"),
            attempt_count=q.get("attempt_count", 0),
        )
        for q in result.data or []
    ]


@router.get("/courses/{course_id}/concepts", response_model=list[ConceptResponse])
async def list_course_concepts(
    course_id: str,
    user: dict = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
):
    sb = _sb(user, settings)

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
        .select("id, title, description, category, difficulty_estimate, lecture_id")
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
            ),
            "lecture_number": lecture.get("lecture_number", 999),
        })

    concepts.sort(key=lambda x: (x["lecture_number"], x["data"].title))
    return [c["data"] for c in concepts]
