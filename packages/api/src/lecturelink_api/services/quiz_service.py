"""Quiz storage and scoring service."""

from __future__ import annotations

import logging
from datetime import datetime

logger = logging.getLogger(__name__)


def save_quiz(
    supabase,
    course_id: str,
    user_id: str,
    title: str,
    questions: list[dict],
    target_assessment_id: str | None = None,
    difficulty: str = "medium",
) -> dict:
    """Save a generated quiz and its questions to the database."""
    target_concepts = list(set(
        q.get("concept_id") for q in questions if q.get("concept_id")
    ))

    quiz_data = {
        "course_id": course_id,
        "user_id": user_id,
        "title": title,
        "target_assessment_id": target_assessment_id,
        "target_concepts": target_concepts,
        "difficulty": difficulty,
        "status": "ready",
    }

    quiz_result = supabase.table("quizzes").insert(quiz_data).execute()
    quiz = quiz_result.data[0]
    quiz_id = quiz["id"]

    question_records = []
    for q in questions:
        record = {
            "quiz_id": quiz_id,
            "question_index": q["question_index"],
            "question_text": q["question_text"],
            "question_type": q["question_type"],
            "options": q.get("options"),
            "correct_answer": q["correct_answer"],
            "explanation": q["explanation"],
            "source_chunk_ids": q.get("source_chunk_ids", []),
            "concept_id": q.get("concept_id"),
            "difficulty": q.get("difficulty", difficulty),
        }
        question_records.append(record)

    if question_records:
        supabase.table("quiz_questions").insert(
            question_records
        ).execute()

    logger.info(
        "Saved quiz %s with %d questions", quiz_id, len(question_records)
    )
    return quiz


def get_quiz_with_questions(supabase, quiz_id: str) -> dict | None:
    """Get quiz with all its questions."""
    quiz_result = (
        supabase.table("quizzes")
        .select("*").eq("id", quiz_id).execute()
    )

    if not quiz_result.data:
        return None

    quiz = quiz_result.data[0]

    questions_result = (
        supabase.table("quiz_questions")
        .select("*").eq("quiz_id", quiz_id)
        .order("question_index").execute()
    )

    quiz["questions"] = questions_result.data
    return quiz


def score_quiz(
    supabase,
    quiz_id: str,
    user_id: str,
    answers: list[dict],
) -> dict:
    """Score a quiz submission and save results."""
    quiz = get_quiz_with_questions(supabase, quiz_id)
    if not quiz:
        raise ValueError(f"Quiz {quiz_id} not found")

    question_map = {q["id"]: q for q in quiz["questions"]}

    results = []
    correct_count = 0

    for ans in answers:
        question_id = ans["question_id"]
        student_answer = ans.get("student_answer", "")

        question = question_map.get(question_id)
        if not question:
            continue

        is_correct = check_answer(question, student_answer)
        if is_correct:
            correct_count += 1

        results.append({
            "question_id": question_id,
            "is_correct": is_correct,
            "student_answer": student_answer,
            "correct_answer": question["correct_answer"],
            "explanation": question["explanation"],
            "source_chunk_ids": question.get("source_chunk_ids", []),
            "concept_id": question.get("concept_id"),
            "time_spent_seconds": ans.get("time_spent_seconds"),
        })

    total = len(results)
    score = correct_count / total if total > 0 else 0.0

    (
        supabase.table("quizzes")
        .update({
            "status": "completed",
            "best_score": score,
            "last_attempted_at": datetime.utcnow().isoformat(),
        })
        .eq("id", quiz_id).execute()
    )

    logger.info(
        "Quiz %s scored: %d/%d = %.1f%%",
        quiz_id, correct_count, total, score * 100,
    )

    return {
        "score": score,
        "total_questions": total,
        "correct_count": correct_count,
        "results": results,
    }


def check_answer(question: dict, student_answer: str) -> bool:
    """Check if a student's answer is correct.

    MCQ: Match label (A/B/C/D) or text against correct option
    True/False: Match "true"/"false" (case-insensitive)
    Short answer: Exact match (case-insensitive, stripped)
    """
    qtype = question.get("question_type", "mcq")
    correct = question.get("correct_answer", "")
    student = student_answer.strip()

    if qtype == "mcq":
        if student.upper() == correct.upper():
            return True

        options = question.get("options", [])
        for opt in options:
            if (
                opt.get("is_correct")
                and student.lower() == opt.get("text", "").lower()
            ):
                return True

        for opt in options:
            if (
                opt.get("label", "").upper() == student.upper()
                and opt.get("is_correct")
            ):
                return True

        return False

    elif qtype == "true_false":
        if correct.lower() in ("true", "t"):
            return student.lower() in ("true", "t")
        return student.lower() in ("false", "f")

    elif qtype == "short_answer":
        return student.lower().strip() == correct.lower().strip()

    return False
