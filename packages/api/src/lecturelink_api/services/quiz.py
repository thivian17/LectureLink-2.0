"""Quiz generation and scoring service.

Uses a generator-critic loop for high-quality question generation:
1. Plan: select concepts + retrieve grounding chunks
2. Generate: LLM creates questions from grounding material
3. Critique: LLM reviews for faithfulness, clarity, difficulty
4. Revise: flagged questions regenerated with feedback (max 3 iterations)
5. Score: check student answers against correct answers

IMPORTANT: ``run_quiz_generation`` is a **sync** function so that
FastAPI's ``BackgroundTasks`` runs it in a thread-pool instead of the
main async event loop.  The quiz pipeline uses async Gemini calls mixed
with sync Supabase calls — running async on the main loop would block
the entire server.
"""

from __future__ import annotations

import asyncio
import json
import logging

from supabase import create_client

logger = logging.getLogger(__name__)

VALID_QUESTION_TYPES = frozenset({
    "mcq", "true_false", "short_answer",
    "code_writing", "code_fix", "code_explain",
})

DIFFICULTY_TO_FLOAT = {"easy": 0.3, "medium": 0.5, "hard": 0.8}


def _difficulty_float(val) -> float:
    """Convert a difficulty value to float for the DB column."""
    if isinstance(val, (int, float)):
        return float(val)
    return DIFFICULTY_TO_FLOAT.get(str(val).lower(), 0.5)


async def run_quiz_generation_async(
    supabase_url: str,
    supabase_key: str,
    user_token: str,
    quiz_id: str,
    course_id: str,
    user_id: str,
    target_assessment_id: str | None = None,
    lecture_ids: list[str] | None = None,
    num_questions: int = 10,
    difficulty: str = "mixed",
    include_coding: bool = False,
    coding_ratio: float = 0.3,
    coding_language: str = "python",
    coding_only: bool = False,
) -> None:
    """Async entry point for quiz generation (used by arq worker)."""
    sb = create_client(supabase_url, supabase_key)
    if user_token:
        sb.auth.set_session(user_token, "")

    await _generate_quiz_async(
        sb, quiz_id, course_id, user_id,
        target_assessment_id, lecture_ids,
        num_questions, difficulty,
        include_coding=include_coding,
        coding_ratio=coding_ratio,
        coding_language=coding_language,
        coding_only=coding_only,
    )


def run_quiz_generation(
    supabase_url: str,
    supabase_key: str,
    user_token: str,
    quiz_id: str,
    course_id: str,
    user_id: str,
    target_assessment_id: str | None = None,
    lecture_ids: list[str] | None = None,
    num_questions: int = 10,
    difficulty: str = "mixed",
    include_coding: bool = False,
    coding_ratio: float = 0.3,
    coding_language: str = "python",
    coding_only: bool = False,
) -> None:
    """Sync fallback for quiz generation (runs in a daemon thread)."""
    sb = create_client(supabase_url, supabase_key)
    if user_token:
        sb.auth.set_session(user_token, "")

    loop = asyncio.new_event_loop()
    try:
        loop.run_until_complete(
            _generate_quiz_async(
                sb, quiz_id, course_id, user_id,
                target_assessment_id, lecture_ids,
                num_questions, difficulty,
                include_coding=include_coding,
                coding_ratio=coding_ratio,
                coding_language=coding_language,
                coding_only=coding_only,
            )
        )
    except Exception:
        logger.exception("Quiz generation thread failed for %s", quiz_id)
    finally:
        loop.close()


async def _generate_quiz_async(
    supabase,
    quiz_id: str,
    course_id: str,
    user_id: str,
    target_assessment_id: str | None = None,
    lecture_ids: list[str] | None = None,
    num_questions: int = 10,
    difficulty: str = "mixed",
    include_coding: bool = False,
    coding_ratio: float = 0.3,
    coding_language: str = "python",
    coding_only: bool = False,
) -> None:
    """Async quiz generation executed inside the background thread's event loop."""
    # LangFuse trace for the full generator-critic loop
    lf = None
    trace = None
    try:
        from .observability import get_langfuse

        lf = get_langfuse()
        if lf:
            trace = lf.trace(
                name="quiz_generation",
                user_id=user_id,
                metadata={
                    "course_id": course_id,
                    "question_count": num_questions,
                    "difficulty": difficulty,
                    "include_coding": include_coding,
                },
            )
    except Exception:
        logger.debug("LangFuse trace init failed for quiz generation", exc_info=True)

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
                lecture_ids=lecture_ids,
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
                target_assessment_id, lecture_ids,
                num_questions, difficulty,
                include_coding=include_coding,
                coding_ratio=coding_ratio,
                coding_language=coding_language,
                coding_only=coding_only,
            )
            return

        # 2. Determine question counts and type distribution
        from .code_question_generator import generate_coding_questions

        if coding_only:
            coding_count = num_questions
            regular_count = 0
            type_distribution = {
                "code_writing": 0.5, "code_fix": 0.3, "code_explain": 0.2,
            }
        elif include_coding:
            coding_count = max(1, round(num_questions * coding_ratio))
            regular_count = num_questions - coding_count
            type_distribution = None
        else:
            coding_count = 0
            regular_count = num_questions
            type_distribution = None

        # Generate regular questions
        regular_questions = []
        if regular_count > 0:
            regular_plan = {**quiz_plan, "num_questions": regular_count}
            regular_questions = await run_quiz_generation_loop(regular_plan)

        # Generate coding questions
        coding_questions = []
        if coding_count > 0:
            coding_plan = {**quiz_plan, "num_questions": coding_count}
            coding_questions = await generate_coding_questions(
                coding_plan,
                language=coding_language,
                type_distribution=type_distribution,
            )

        # Interleave or use whichever list has questions
        if regular_questions and coding_questions:
            questions = []
            ri, ci = 0, 0
            while ri < len(regular_questions) or ci < len(coding_questions):
                if ri < len(regular_questions):
                    questions.append(regular_questions[ri])
                    ri += 1
                if ci < len(coding_questions):
                    questions.append(coding_questions[ci])
                    ci += 1
        elif coding_questions:
            questions = coding_questions
        else:
            questions = regular_questions

        # Re-index after merging
        for i, q in enumerate(questions):
            q["question_index"] = i

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
        # Build set of valid concept IDs from the plan so we can
        # discard hallucinated IDs that would violate the FK constraint.
        valid_concept_ids = {
            item["concept"]["id"]
            for item in quiz_plan.get("concepts", [])
            if item.get("concept", {}).get("id")
        }

        question_rows = []
        for q in questions:
            qtype = q.get("question_type", "mcq")
            if qtype not in VALID_QUESTION_TYPES:
                logger.warning(
                    "Quiz %s: dropping question with invalid type %r",
                    quiz_id, qtype,
                )
                continue
            raw_concept_id = q.get("concept_id")
            if raw_concept_id and raw_concept_id not in valid_concept_ids:
                logger.warning(
                    "Quiz %s: dropping invalid concept_id %r",
                    quiz_id, raw_concept_id,
                )
                raw_concept_id = None
            question_rows.append({
                "quiz_id": quiz_id,
                "user_id": user_id,
                "question_index": q["question_index"],
                "question_type": qtype,
                "question_text": q["question_text"],
                "options": q.get("options", []),
                "correct_answer": q["correct_answer"],
                "explanation": q.get("explanation", ""),
                "difficulty": _difficulty_float(q.get("difficulty", 0.5)),
                "source_chunk_ids": q.get("source_chunk_ids", []),
                "concept_id": raw_concept_id,
                "code_metadata": q.get("code_metadata"),
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

        # Finalize LangFuse trace
        try:
            if trace:
                trace.update(output={
                    "questions_stored": len(question_rows),
                    "has_coding": any(
                        r["question_type"].startswith("code") for r in question_rows
                    ),
                })
                lf.flush()
        except Exception:
            logger.debug("LangFuse trace finalization failed", exc_info=True)

    except Exception as e:
        logger.exception("Quiz generation failed for %s: %s", quiz_id, e)
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
    lecture_ids: list[str] | None,
    num_questions: int,
    difficulty: str,
    include_coding: bool = False,
    coding_ratio: float = 0.3,
    coding_language: str = "python",
    coding_only: bool = False,
) -> None:
    """Simple fallback generation without concepts (pre-concept-extraction).

    Used when the course has lecture chunks but no extracted concepts yet.
    """
    from .genai_client import get_genai_client
    from .search import format_chunks_for_context, search_lectures

    client = get_genai_client()
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
        lecture_ids=lecture_ids,
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

    # Determine how many regular vs coding questions
    if coding_only:
        coding_count = num_questions
        regular_count = 0
    elif include_coding:
        coding_count = max(1, round(num_questions * coding_ratio))
        regular_count = num_questions - coding_count
    else:
        regular_count = num_questions
        coding_count = 0

    # Generate regular questions
    regular_questions = []
    if regular_count > 0:
        prompt = (
            f"Generate exactly {regular_count} quiz questions.\n"
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

        raw_text = response.text
        if raw_text:
            try:
                regular_questions = json.loads(raw_text)
            except (json.JSONDecodeError, TypeError):
                logger.warning("Simple quiz gen: invalid JSON for regular questions")
                regular_questions = []
        else:
            logger.warning("Simple quiz gen: empty response for regular questions")

    # Generate coding questions in simple mode (no concepts available)
    coding_questions = []
    if coding_count > 0:
        from .code_question_generator import CODING_QUESTION_SYSTEM_PROMPT

        type_dist_instruction = ""
        if coding_only:
            type_dist_instruction = (
                "\nDistribute question types approximately as follows: "
                "50% code_writing, 30% code_fix, 20% code_explain.\n"
            )
        else:
            type_dist_instruction = (
                "\nVary the question types: prefer ~50% code_writing, "
                "~30% code_fix, ~20% code_explain.\n"
            )

        coding_prompt = (
            f"Programming language: {coding_language}\n"
            f"Difficulty: {difficulty}\n"
            f"Student mastery level: 0.5\n"
            f"Generate {coding_count} coding questions.\n"
            f"{type_dist_instruction}"
            f"{assessment_context}\n\n"
            f"Lecture Content:\n{context}"
        )

        coding_response = await client.aio.models.generate_content(
            model="gemini-2.5-flash",
            contents=coding_prompt,
            config={
                "system_instruction": CODING_QUESTION_SYSTEM_PROMPT,
                "temperature": 0.7,
                "response_mime_type": "application/json",
            },
        )
        raw_coding_text = coding_response.text
        if raw_coding_text:
            try:
                coding_questions = json.loads(raw_coding_text)
            except (json.JSONDecodeError, TypeError):
                from .code_question_generator import _repair_json_escapes
                logger.debug("Repairing invalid JSON escapes in simple coding gen")
                try:
                    coding_questions = json.loads(_repair_json_escapes(raw_coding_text))
                except (json.JSONDecodeError, TypeError):
                    logger.warning("Simple quiz gen: coding question JSON repair also failed")
                    coding_questions = []
        else:
            logger.warning("Simple quiz gen: empty response for coding questions")

    # Interleave or use whichever list has questions
    if regular_questions and coding_questions:
        all_questions: list[dict] = []
        ri, ci = 0, 0
        while ri < len(regular_questions) or ci < len(coding_questions):
            if ri < len(regular_questions):
                all_questions.append(regular_questions[ri])
                ri += 1
            if ci < len(coding_questions):
                all_questions.append(coding_questions[ci])
                ci += 1
    elif coding_questions:
        all_questions = coding_questions
    else:
        all_questions = regular_questions

    question_rows = []
    for i, q in enumerate(all_questions):
        question_rows.append({
            "quiz_id": quiz_id,
            "user_id": user_id,
            "question_index": i,
            "question_type": q.get("question_type", "mcq"),
            "question_text": q["question_text"],
            "options": q.get("options", []),
            "correct_answer": q["correct_answer"],
            "explanation": q.get("explanation", ""),
            "difficulty": _difficulty_float(q.get("difficulty", 0.5)),
            "source_chunk_ids": [],
            "code_metadata": q.get("code_metadata"),
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


async def score_quiz(
    supabase,
    quiz_id: str,
    answers: list[dict],
) -> dict:
    """Score a quiz submission.

    Uses smart answer checking:
    - MCQ: match by label or option text
    - True/false: case-insensitive match
    - Short answer: case-insensitive exact match
    - Code questions: AI-graded via Gemini
    """
    from .code_grading import grade_code_answer, is_code_question
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

        grading_result = None

        if is_code_question(question):
            # Build attempt context for progressive feedback
            attempt_context = {
                "attempt_number": answer.get("attempt_number", 1),
                "hints_used": answer.get("hints_used", 0),
            }

            # Check for previous attempt feedback
            prev_attempts = (
                supabase.table("quiz_attempts")
                .select("student_answer, code_grading_result")
                .eq("question_id", answer["question_id"])
                .eq("user_id", question.get("user_id"))
                .order("created_at", desc=True)
                .limit(1)
                .execute()
            )
            if prev_attempts.data:
                prev = prev_attempts.data[0]
                attempt_context["previous_code"] = prev["student_answer"]
                if prev.get("code_grading_result"):
                    attempt_context["previous_feedback"] = prev[
                        "code_grading_result"
                    ].get("overall_feedback", "")

            grading_result = await grade_code_answer(
                question, answer["student_answer"], attempt_context
            )
            is_correct = grading_result.get("is_correct", False)
        else:
            is_correct = check_answer(question, answer["student_answer"])

        if is_correct:
            correct_count += 1

        # Strip is_correct from options for the response
        raw_options = question.get("options") or []
        safe_options = [
            opt.get("text", "") if isinstance(opt, dict) else str(opt)
            for opt in raw_options
        ] if raw_options else None

        result_entry = {
            "question_id": answer["question_id"],
            "is_correct": is_correct,
            "student_answer": answer["student_answer"],
            "correct_answer": question["correct_answer"],
            "explanation": question.get("explanation", ""),
            "question_text": question.get("question_text", ""),
            "question_type": question.get("question_type", "mcq"),
            "options": safe_options,
            "source_chunk_ids": question.get("source_chunk_ids", []),
            "concept_id": question.get("concept_id"),
        }

        if grading_result is not None:
            result_entry["code_grading_result"] = grading_result

        results.append(result_entry)

        # Save attempt
        attempt_data = {
            "quiz_id": quiz_id,
            "user_id": question.get("user_id"),
            "question_id": answer["question_id"],
            "student_answer": answer["student_answer"],
            "is_correct": is_correct,
            "time_spent_seconds": answer.get("time_spent_seconds"),
        }

        if grading_result is not None:
            attempt_data["code_grading_result"] = grading_result
            attempt_data["hints_used"] = answer.get("hints_used", 0)

        (
            supabase.table("quiz_attempts")
            .insert(attempt_data)
            .execute()
        )

        # Update BKT mastery state for this concept (if linked)
        concept_id = question.get("concept_id")
        user_id = question.get("user_id")
        if concept_id and user_id:
            try:
                from lecturelink_api.services.mastery import update_mastery_from_quiz_result

                await update_mastery_from_quiz_result(
                    supabase=supabase,
                    user_id=user_id,
                    concept_id=concept_id,
                    is_correct=is_correct,
                )
            except Exception:
                logger.warning(
                    "BKT update failed for concept %s", concept_id, exc_info=True
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

    try:
        from .observability import track_event

        quiz_user_id = questions_result.data[0].get("user_id") if questions_result.data else None
        if quiz_user_id:
            track_event(quiz_user_id, "quiz_submitted", {
                "quiz_id": quiz_id,
                "score_pct": score,
                "question_count": total,
                "has_code_questions": any(
                    q.get("question_type", "").startswith("code")
                    for q in questions_result.data
                ),
            })
    except Exception:
        pass  # Observability is non-critical

    return {
        "score": score,
        "total_questions": total,
        "correct_count": correct_count,
        "results": results,
    }
