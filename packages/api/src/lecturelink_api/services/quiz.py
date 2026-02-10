"""Quiz generation and scoring service.

Uses a generator-critic loop for high-quality question generation:
1. Plan: select concepts + retrieve grounding chunks
2. Generate: LLM creates questions from grounding material
3. Critique: LLM reviews for faithfulness, clarity, difficulty
4. Revise: flagged questions regenerated with feedback (max 3 iterations)
5. Score: check student answers against correct answers
"""

from __future__ import annotations

import json
import logging

logger = logging.getLogger(__name__)


async def generate_quiz_background(
    supabase,
    quiz_id: str,
    course_id: str,
    user_id: str,
    target_assessment_id: str | None = None,
    num_questions: int = 10,
    difficulty: str = "mixed",
) -> None:
    """Background task: generate quiz questions using generator-critic loop.

    Updates the quiz record with generated questions and sets status to 'ready'.
    On failure, sets status to 'failed' with error message.
    """
    try:
        from .quiz_loop import run_quiz_generation_loop
        from .quiz_planner import plan_quiz

        # 1. Plan quiz (select concepts + retrieve grounding)
        try:
            quiz_plan = await plan_quiz(
                supabase=supabase,
                course_id=course_id,
                user_id=user_id,
                target_assessment_id=target_assessment_id,
                num_questions=num_questions,
                difficulty=difficulty if difficulty != "mixed" else "medium",
            )
        except ValueError:
            # Fallback: use simple search if no concepts exist yet
            logger.info(
                "Quiz %s: No concepts found, using simple generation",
                quiz_id,
            )
            await _generate_simple(
                supabase, quiz_id, course_id, user_id,
                target_assessment_id, num_questions, difficulty,
            )
            return

        # 2. Run generator-critic loop
        questions = await run_quiz_generation_loop(quiz_plan)

        if not questions:
            (
                supabase.table("quizzes")
                .update({"status": "failed"})
                .eq("id", quiz_id)
                .execute()
            )
            logger.error(
                "Quiz %s: No questions survived critic loop", quiz_id
            )
            return

        # 3. Store questions
        question_rows = []
        for q in questions:
            question_rows.append({
                "quiz_id": quiz_id,
                "question_index": q["question_index"],
                "question_type": q.get("question_type", "mcq"),
                "question_text": q["question_text"],
                "options": q.get("options", []),
                "correct_answer": q["correct_answer"],
                "explanation": q.get("explanation", ""),
                "difficulty": q.get("difficulty", "medium"),
                "source_chunk_ids": q.get("source_chunk_ids", []),
                "concept_id": q.get("concept_id"),
            })

        if question_rows:
            (
                supabase.table("quiz_questions")
                .insert(question_rows)
                .execute()
            )

        # 4. Update quiz status
        (
            supabase.table("quizzes")
            .update({
                "status": "ready",
                "question_count": len(question_rows),
            })
            .eq("id", quiz_id)
            .execute()
        )

        logger.info(
            "Quiz %s: generated %d questions via critic loop",
            quiz_id, len(question_rows),
        )

    except Exception as e:
        logger.error("Quiz generation failed for %s: %s", quiz_id, e)
        try:
            (
                supabase.table("quizzes")
                .update({"status": "failed"})
                .eq("id", quiz_id)
                .execute()
            )
        except Exception as update_err:
            logger.error(
                "Failed to update quiz error status: %s", update_err
            )


async def _generate_simple(
    supabase,
    quiz_id: str,
    course_id: str,
    user_id: str,
    target_assessment_id: str | None,
    num_questions: int,
    difficulty: str,
) -> None:
    """Simple fallback generation without concepts (pre-concept-extraction).

    Used when the course has lecture chunks but no extracted concepts yet.
    """
    from google import genai

    from .search import format_chunks_for_context, search_lectures

    client = genai.Client()
    assessment_context = ""
    if target_assessment_id:
        assessment = (
            supabase.table("assessments")
            .select("title, topics")
            .eq("id", target_assessment_id)
            .execute()
        )
        if assessment.data:
            a = assessment.data[0]
            topics = a.get("topics", [])
            assessment_context = (
                f"\nTarget assessment: {a['title']}\n"
                f"Topics: {', '.join(topics) if topics else 'general'}\n"
            )

    query = assessment_context or "key concepts and important topics"
    chunks = await search_lectures(
        supabase=supabase,
        course_id=course_id,
        query=query,
        limit=15,
        user_id=user_id,
    )

    if not chunks:
        (
            supabase.table("quizzes")
            .update({"status": "failed"})
            .eq("id", quiz_id)
            .execute()
        )
        return

    context = format_chunks_for_context(chunks, max_tokens=8000)
    prompt = (
        f"Generate exactly {num_questions} quiz questions.\n"
        f"Difficulty: {difficulty}\n{assessment_context}\n\n"
        f"Lecture Content:\n{context}"
    )

    system_prompt = """\
Generate quiz questions from lecture content.
Rules:
- Questions must be answerable from the provided content ONLY
- Mix of question types: mcq and true_false
- MCQ: exactly 4 options labeled A-D, one correct
- true_false: exactly 2 options labeled True/False
Output as JSON array of question objects."""

    response = await client.aio.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt,
        config={
            "system_instruction": system_prompt,
            "temperature": 0.7,
            "response_mime_type": "application/json",
        },
    )

    questions = json.loads(response.text)

    question_rows = []
    for i, q in enumerate(questions):
        question_rows.append({
            "quiz_id": quiz_id,
            "question_index": i,
            "question_type": q.get("question_type", "mcq"),
            "question_text": q["question_text"],
            "options": q.get("options", []),
            "correct_answer": q["correct_answer"],
            "explanation": q.get("explanation", ""),
            "difficulty": q.get("difficulty", "medium"),
            "source_chunk_ids": [],
        })

    if question_rows:
        (
            supabase.table("quiz_questions")
            .insert(question_rows)
            .execute()
        )

    (
        supabase.table("quizzes")
        .update({
            "status": "ready",
            "question_count": len(question_rows),
        })
        .eq("id", quiz_id)
        .execute()
    )


def score_quiz(
    supabase,
    quiz_id: str,
    answers: list[dict],
) -> dict:
    """Score a quiz submission.

    Uses smart answer checking:
    - MCQ: match by label or option text
    - True/false: case-insensitive match
    - Short answer: case-insensitive exact match
    """
    from .quiz_service import check_answer

    questions_result = (
        supabase.table("quiz_questions")
        .select("*")
        .eq("quiz_id", quiz_id)
        .order("question_index")
        .execute()
    )
    questions = {q["id"]: q for q in questions_result.data}

    results = []
    correct_count = 0

    for answer in answers:
        question = questions.get(answer["question_id"])
        if not question:
            continue

        is_correct = check_answer(question, answer["student_answer"])
        if is_correct:
            correct_count += 1

        results.append({
            "question_id": answer["question_id"],
            "is_correct": is_correct,
            "student_answer": answer["student_answer"],
            "correct_answer": question["correct_answer"],
            "explanation": question.get("explanation", ""),
            "source_chunk_ids": question.get("source_chunk_ids", []),
        })

        # Save attempt
        (
            supabase.table("quiz_attempts")
            .insert({
                "quiz_id": quiz_id,
                "question_id": answer["question_id"],
                "student_answer": answer["student_answer"],
                "is_correct": is_correct,
                "time_spent_seconds": answer.get("time_spent_seconds"),
            })
            .execute()
        )

    total = len(results)
    score = (correct_count / total * 100) if total > 0 else 0.0

    # Update quiz best_score
    current_quiz = (
        supabase.table("quizzes")
        .select("best_score, attempt_count")
        .eq("id", quiz_id)
        .execute()
    )
    if current_quiz.data:
        current_best = current_quiz.data[0].get("best_score") or 0
        current_attempts = current_quiz.data[0].get("attempt_count") or 0
    else:
        current_best = 0
        current_attempts = 0

    (
        supabase.table("quizzes")
        .update({
            "best_score": max(score, current_best),
            "attempt_count": current_attempts + 1,
        })
        .eq("id", quiz_id)
        .execute()
    )

    return {
        "score": score,
        "total_questions": total,
        "correct_count": correct_count,
        "results": results,
    }
