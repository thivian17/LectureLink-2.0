"""Quiz generation loop — orchestrates generator-critic iterations."""

from __future__ import annotations

import logging

from .quiz_critic import critique_questions
from .quiz_generator import generate_questions

logger = logging.getLogger(__name__)

MAX_ITERATIONS = 3


async def run_quiz_generation_loop(quiz_plan: dict) -> list[dict]:
    """Run the generator-critic loop to produce high-quality questions.

    Loop logic:
    - Generate questions from plan
    - Critic reviews each question
    - Accepted questions are kept
    - Rejected questions are dropped permanently
    - Revised questions get regenerated with feedback
    - Loop until no revisions needed (max 3 iterations)
    """
    accepted_questions: list[dict] = []
    current_plan = quiz_plan
    revision_feedback: list[dict] = []

    for iteration in range(MAX_ITERATIONS):
        logger.info(
            "Quiz generation iteration %d/%d", iteration + 1, MAX_ITERATIONS
        )

        if iteration == 0:
            questions = await generate_questions(current_plan)
        else:
            questions = await generate_questions(
                current_plan, critic_feedback=revision_feedback
            )

        if not questions:
            logger.warning(
                "No questions generated in iteration %d", iteration + 1
            )
            break

        reviews = await critique_questions(questions, current_plan)

        revision_feedback = []
        newly_accepted = 0
        rejected_count = 0

        for review in reviews:
            idx = review.get("question_index", 0)
            verdict = review.get("verdict", "accept")

            matching = [
                q for q in questions if q.get("question_index") == idx
            ]
            if not matching:
                continue
            question = matching[0]

            if verdict == "accept":
                accepted_questions.append(question)
                newly_accepted += 1
            elif verdict == "revise":
                revision_feedback.append(review)
            elif verdict == "reject":
                rejected_count += 1
                logger.info(
                    "Rejected Q%d: %s", idx, review.get("feedback", "")
                )

        logger.info(
            "Iteration %d: accepted=%d, revise=%d, rejected=%d",
            iteration + 1, newly_accepted,
            len(revision_feedback), rejected_count,
        )

        if not revision_feedback:
            break

        # Narrow plan to only concepts needing revision
        revision_concept_ids: set[str] = set()
        for fb in revision_feedback:
            idx = fb.get("question_index", 0)
            matching = [
                q for q in questions if q.get("question_index") == idx
            ]
            if matching:
                revision_concept_ids.add(matching[0].get("concept_id", ""))

        current_plan = {
            **quiz_plan,
            "concepts": [
                c for c in quiz_plan["concepts"]
                if c["concept"]["id"] in revision_concept_ids
            ],
            "num_questions": len(revision_feedback),
        }

    # Order by difficulty: easy first, hard last
    difficulty_order = {"easy": 0, "medium": 1, "hard": 2}
    accepted_questions.sort(
        key=lambda q: difficulty_order.get(_estimate_difficulty(q), 1)
    )

    for i, q in enumerate(accepted_questions):
        q["question_index"] = i

    logger.info(
        "Quiz generation complete: %d questions accepted",
        len(accepted_questions),
    )
    return accepted_questions


def _estimate_difficulty(question: dict) -> str:
    """Estimate difficulty from question type."""
    qtype = question.get("question_type", "mcq")
    if qtype == "true_false":
        return "easy"
    elif qtype == "short_answer":
        return "hard"
    return "medium"
