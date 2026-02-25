"""AI-graded code evaluation service using Gemini."""

from __future__ import annotations

import json
import logging

from .genai_client import get_genai_client as _get_client

logger = logging.getLogger(__name__)

CODE_GRADING_MODEL = "gemini-2.5-flash"


_GRADING_SYSTEM_INSTRUCTION = """\
You are grading a student's code submission for a university course.
Be encouraging but honest. Your goal is to help the student learn.
Grade the submission against each rubric criterion. For each criterion:

Assign a score (0.0-1.0) relative to the criterion's weight
Provide specific, actionable feedback

CRITICAL:

Grade the APPROACH, not just the output. A correct algorithm with a small bug
shows more understanding than hardcoded answers.
Be specific. "Good job" is useless. "Your use of memoization correctly avoids
recomputation of overlapping subproblems" teaches something.
If the student's approach differs from the reference but is valid, grade fairly.

Output JSON with these exact fields:
{
"overall_score": 0.0-1.0,
"is_correct": true/false,
"rubric_scores": {
"<criterion_name>": {
"score": 0.0-1.0,
"max_weight": <integer>,
"feedback": "<specific feedback>"
}
},
"line_feedback": [
{"line": <int>, "type": "error|suggestion|praise", "message": "<specific note>"}
],
"overall_feedback": "<2-3 sentence summary of strengths and areas for improvement>",
"suggested_improvement": "<improved version of student's code, or null if score >= 0.9>",
"concepts_demonstrated": ["<concept1>", "<concept2>"],
"concepts_lacking": ["<concept1>"]
}"""

_FALLBACK_RESULT = {
    "overall_score": 0.0,
    "is_correct": False,
    "rubric_scores": {},
    "line_feedback": [],
    "overall_feedback": "Grading failed. Please try again.",
    "suggested_improvement": None,
    "concepts_demonstrated": [],
    "concepts_lacking": [],
}


def is_code_question(question: dict) -> bool:
    """Return True if the question is a coding question type."""
    return question.get("question_type") in ("code_writing", "code_fix", "code_explain")


def calculate_weighted_score(rubric_scores: dict) -> float:
    """Compute a weighted average from rubric scores.

    Args:
        rubric_scores: Dict of criterion_name -> {"score": float, "max_weight": int, ...}.

    Returns:
        Weighted average score between 0.0 and 1.0.
    """
    if not rubric_scores:
        return 0.0

    total_weighted = 0.0
    total_weight = 0

    for criterion in rubric_scores.values():
        score = criterion.get("score", 0.0)
        weight = criterion.get("max_weight", 1)
        total_weighted += score * weight
        total_weight += weight

    if total_weight == 0:
        return 0.0

    return total_weighted / total_weight


async def grade_code_answer(
    question: dict,
    student_code: str,
    attempt_context: dict | None = None,
) -> dict:
    """Grade a student's code submission using Gemini.

    Args:
        question: The question dict including code_metadata and question text.
        student_code: The student's submitted code.
        attempt_context: Optional context with attempt_number, hints_used,
            previous_code, and previous_feedback.

    Returns:
        A grading result dict with scores, feedback, and suggestions.
    """
    try:
        code_metadata = question.get("code_metadata") or {}
        question_text = question.get("question_text", "")
        reference_solution = code_metadata.get("reference_solution", "")
        grading_rubric = code_metadata.get("grading_rubric", {})
        common_mistakes = code_metadata.get("common_mistakes", [])

        # Build the grading prompt
        prompt_parts = [
            "Problem",
            question_text,
            "",
            "Reference Solution",
            reference_solution,
            "",
            "Student's Submission",
            student_code,
            "",
            "Grading Rubric",
            json.dumps(grading_rubric, indent=2),
            "",
            "Common Mistakes to Watch For",
        ]

        if isinstance(common_mistakes, list):
            for mistake in common_mistakes:
                prompt_parts.append(f"- {mistake}")
        else:
            prompt_parts.append(str(common_mistakes))

        # Include previous attempt context for progressive guidance
        if attempt_context:
            previous_code = attempt_context.get("previous_code")
            previous_feedback = attempt_context.get("previous_feedback")
            if previous_code and previous_feedback:
                prompt_parts.extend([
                    "",
                    "Previous Attempt",
                    previous_code,
                    "",
                    "Previous Feedback",
                    previous_feedback,
                    "",
                    "Acknowledge what the student improved. "
                    "If they addressed previous feedback, praise the improvement.",
                ])

        prompt = "\n".join(prompt_parts)

        client = _get_client()
        response = await client.aio.models.generate_content(
            model=CODE_GRADING_MODEL,
            contents=prompt,
            config={
                "system_instruction": _GRADING_SYSTEM_INSTRUCTION,
                "response_mime_type": "application/json",
            },
        )

        result = json.loads(response.text)

        # Recalculate weighted score from rubric for consistency
        if result.get("rubric_scores"):
            result["overall_score"] = calculate_weighted_score(result["rubric_scores"])

        return result

    except Exception as e:
        logger.exception("Code grading failed: %s", e)
        return {**_FALLBACK_RESULT, "error": str(e)}
