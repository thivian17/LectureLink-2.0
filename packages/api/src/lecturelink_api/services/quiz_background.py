"""Background task for full quiz generation pipeline."""

from __future__ import annotations

import logging

from .quiz_loop import run_quiz_generation_loop
from .quiz_planner import plan_quiz

logger = logging.getLogger(__name__)


async def generate_quiz_background(
    supabase,
    quiz_id: str,
    course_id: str,
    user_id: str,
    title: str,
    target_assessment_id: str | None = None,
    num_questions: int = 10,
    difficulty: str = "medium",
):
    """Full quiz generation pipeline (runs as background task).

    1. Plan quiz (select concepts + retrieve grounding)
    2. Run generator-critic loop
    3. Save accepted questions to DB
    4. Update quiz status
    """
    try:
        await (
            supabase.table("quizzes")
            .update({"status": "generating"})
            .eq("id", quiz_id).execute()
        )

        quiz_plan = await plan_quiz(
            supabase=supabase,
            course_id=course_id,
            user_id=user_id,
            target_assessment_id=target_assessment_id,
            num_questions=num_questions,
            difficulty=difficulty,
        )

        questions = await run_quiz_generation_loop(quiz_plan)

        if not questions:
            await (
                supabase.table("quizzes")
                .update({"status": "failed"})
                .eq("id", quiz_id).execute()
            )
            logger.error(
                "Quiz %s: No questions survived critic loop", quiz_id
            )
            return

        question_records = []
        for q in questions:
            record = {
                "quiz_id": quiz_id,
                "user_id": user_id,
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
            await (
                supabase.table("quiz_questions")
                .insert(question_records).execute()
            )

        target_concepts = list(set(
            q.get("concept_id")
            for q in questions if q.get("concept_id")
        ))
        await (
            supabase.table("quizzes")
            .update({
                "status": "ready",
                "title": title,
                "target_assessment_id": target_assessment_id,
                "target_concepts": target_concepts,
                "difficulty": difficulty,
            })
            .eq("id", quiz_id).execute()
        )

        logger.info(
            "Quiz %s ready with %d questions",
            quiz_id, len(question_records),
        )

    except Exception as e:
        logger.error("Quiz generation failed for %s: %s", quiz_id, e)
        await (
            supabase.table("quizzes")
            .update({"status": "failed"})
            .eq("id", quiz_id).execute()
        )
