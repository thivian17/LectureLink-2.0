"""Tutor grading service — multi-tier answer grading."""

from __future__ import annotations

import json
import logging
import re

from lecturelink_api.models.tutor_models import GradingResultResponse

from .genai_client import get_genai_client as _get_client

logger = logging.getLogger(__name__)


def _parse_json_lenient(text: str) -> dict:
    """Parse JSON leniently — handle trailing commas from LLM output."""
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # Strip trailing commas before } or ]
        cleaned = re.sub(r",\s*([}\]])", r"\1", text)
        return json.loads(cleaned)

GRADING_MODEL = "gemini-2.5-flash"


# ---------------------------------------------------------------------------
# 1. Dispatcher
# ---------------------------------------------------------------------------


async def grade_answer(
    question: dict,
    student_answer: str,
    supabase=None,
) -> GradingResultResponse:
    """Route to the appropriate grading function based on question_type."""
    qtype = question.get("question_type", "").lower()

    dispatch = {
        "mcq": grade_mcq,
        "multiple_choice": grade_mcq,
        "true_false": grade_true_false,
        "fill_in_blank": grade_fill_in_blank,
        "fill_in_the_blank": grade_fill_in_blank,
        "ordering": grade_ordering,
        "short_answer": grade_short_answer,
        "long_answer": grade_long_answer,
    }

    grading_fn = dispatch.get(qtype)
    if grading_fn is None:
        # Default to short_answer AI grading for unknown types
        grading_fn = grade_short_answer

    return await grading_fn(question, student_answer)


# ---------------------------------------------------------------------------
# 2. MCQ
# ---------------------------------------------------------------------------


async def grade_mcq(
    question: dict, student_answer: str,
) -> GradingResultResponse:
    correct = str(question.get("correct_answer", "")).strip().lower()
    given = student_answer.strip().lower()
    is_correct = given == correct

    explanation = question.get("explanation", "")
    if is_correct:
        feedback = explanation or "Correct!"
    else:
        feedback = (
            f"Incorrect. The correct answer is "
            f"'{question.get('correct_answer', '')}'."
        )
        if explanation:
            feedback += f" {explanation}"

    return GradingResultResponse(
        is_correct=is_correct,
        feedback=feedback,
        grading_confidence=1.0,
        model_answer=str(question.get("correct_answer", "")),
    )


# ---------------------------------------------------------------------------
# 3. True/False
# ---------------------------------------------------------------------------


async def grade_true_false(
    question: dict, student_answer: str,
) -> GradingResultResponse:
    correct_raw = str(question.get("correct_answer", "")).strip().lower()
    given_raw = student_answer.strip().lower()

    # Normalize both to "true" or "false"
    true_variants = {"true", "t", "yes", "1"}
    false_variants = {"false", "f", "no", "0"}

    correct_bool = correct_raw in true_variants
    given_bool = given_raw in true_variants

    # If the student answer is not a recognizable boolean, mark wrong
    if given_raw not in true_variants and given_raw not in false_variants:
        return GradingResultResponse(
            is_correct=False,
            feedback=(
                f"Please answer True or False. "
                f"The correct answer is '{question.get('correct_answer', '')}'."
            ),
            grading_confidence=1.0,
            model_answer=str(question.get("correct_answer", "")),
        )

    is_correct = correct_bool == given_bool
    explanation = question.get("explanation", "")

    if is_correct:
        feedback = explanation or "Correct!"
    else:
        feedback = (
            f"Incorrect. The correct answer is "
            f"'{question.get('correct_answer', '')}'."
        )
        if explanation:
            feedback += f" {explanation}"

    return GradingResultResponse(
        is_correct=is_correct,
        feedback=feedback,
        grading_confidence=1.0,
        model_answer=str(question.get("correct_answer", "")),
    )


# ---------------------------------------------------------------------------
# 4. Fill-in-the-blank
# ---------------------------------------------------------------------------


def _normalize_for_comparison(text: str) -> str:
    """Normalize a string for fuzzy comparison."""
    text = text.strip().lower()
    # Remove common wrappers: O(...), Θ(...), Ω(...)
    text = re.sub(r'^[oOΘΩ]\((.*)\)$', r'\1', text)
    # Remove all whitespace and common delimiters
    text = re.sub(r'[\s*()_\-,]+', '', text)
    return text


async def grade_fill_in_blank(
    question: dict, student_answer: str,
) -> GradingResultResponse:
    correct = str(question.get("correct_answer", ""))
    acceptable = question.get("acceptable_answers", [correct])
    if not isinstance(acceptable, list):
        acceptable = [str(acceptable)]
    # Always include the canonical correct answer
    if correct and correct not in acceptable:
        acceptable.append(correct)

    given = student_answer.strip()
    given_normalized = _normalize_for_comparison(given)

    is_correct = False
    for ans in acceptable:
        if _normalize_for_comparison(str(ans)) == given_normalized:
            is_correct = True
            break

    explanation = question.get("explanation", "")
    if is_correct:
        feedback = explanation or "Correct!"
    else:
        feedback = f"Incorrect. The correct answer is '{correct}'."
        if explanation:
            feedback += f" {explanation}"

    return GradingResultResponse(
        is_correct=is_correct,
        feedback=feedback,
        grading_confidence=1.0,
        model_answer=correct,
    )


# ---------------------------------------------------------------------------
# 5. Ordering
# ---------------------------------------------------------------------------


async def grade_ordering(
    question: dict, student_answer: str,
) -> GradingResultResponse:
    correct_order = question.get("correct_answer", [])
    if isinstance(correct_order, str):
        # Accept comma-separated or JSON list
        try:
            correct_order = json.loads(correct_order)
        except (json.JSONDecodeError, ValueError):
            correct_order = [
                s.strip() for s in correct_order.split(",")
            ]

    # Parse student answer the same way
    given_order = student_answer
    if isinstance(given_order, str):
        try:
            given_order = json.loads(given_order)
        except (json.JSONDecodeError, ValueError):
            given_order = [s.strip() for s in given_order.split(",")]

    # Normalize both to lists of lowercase stripped strings
    correct_norm = [str(x).strip().lower() for x in correct_order]
    given_norm = [str(x).strip().lower() for x in given_order]

    is_correct = correct_norm == given_norm

    explanation = question.get("explanation", "")
    if is_correct:
        feedback = explanation or "Correct ordering!"
    else:
        feedback = (
            f"Incorrect ordering. The correct order is: "
            f"{', '.join(str(x) for x in correct_order)}."
        )
        if explanation:
            feedback += f" {explanation}"

    return GradingResultResponse(
        is_correct=is_correct,
        feedback=feedback,
        grading_confidence=1.0,
        model_answer=str(correct_order),
    )


# ---------------------------------------------------------------------------
# 6. Short answer (AI-graded)
# ---------------------------------------------------------------------------


_SHORT_ANSWER_SYSTEM = """\
You are grading a student's short answer for a university course.
Be fair, specific, and educational in your feedback.

IMPORTANT feedback rules:
- NEVER tell the student to "review materials", "check lecture notes", or "reach out for help".
- If the answer is wrong, explain specifically WHAT is wrong and WHY.
- Reference the correct concepts from the rubric in your feedback.
- If the answer is partially correct, acknowledge what they got right, then explain what's missing.
- Keep feedback concise (2-3 sentences).
Output ONLY valid JSON with no extra text."""


async def grade_short_answer(
    question: dict, student_answer: str,
) -> GradingResultResponse:
    rubric = question.get("rubric") or {}
    must_mention = rubric.get("must_mention", [])
    partial_credit = rubric.get("partial_credit_for", [])
    misconceptions = rubric.get("common_misconceptions", [])
    model_answer = rubric.get("model_answer") or question.get(
        "correct_answer", ""
    )

    prompt = (
        f"Question: {question.get('question_text', '')}\n"
        f"Student answer: {student_answer}\n\n"
        f"Rubric:\n"
        f"- Must mention: {json.dumps(must_mention)}\n"
        f"- Partial credit for: {json.dumps(partial_credit)}\n"
        f"- Common misconceptions: {json.dumps(misconceptions)}\n"
        f"- Model answer: {model_answer}\n\n"
        f'Respond in JSON:\n'
        f'{{\n'
        f'  "is_correct": bool,\n'
        f'  "partially_correct": bool,\n'
        f'  "criteria_met": [list of must_mention items satisfied],\n'
        f'  "criteria_missed": [list of must_mention items NOT satisfied],\n'
        f'  "misconceptions_detected": [list],\n'
        f'  "misconception_type": "near_miss" | "fundamental" | '
        f'"incomplete" | null,\n'
        f'  "feedback": "specific feedback — explain what is wrong/missing and the correct answer; NEVER say review materials",\n'
        f'  "confidence": float 0.0-1.0\n'
        f'}}'
    )

    try:
        client = _get_client()
        response = await client.aio.models.generate_content(
            model=GRADING_MODEL,
            contents=prompt,
            config={
                "system_instruction": _SHORT_ANSWER_SYSTEM,
                "response_mime_type": "application/json",
                "temperature": 0.1,
                "max_output_tokens": 1024,
            },
        )
        if not response.text:
            raise ValueError("Empty response from grading model")
        result = _parse_json_lenient(response.text)
    except Exception:
        logger.exception("Short-answer grading failed, using fallback")
        fallback_feedback = (
            "I couldn't grade your answer automatically."
        )
        if model_answer:
            fallback_feedback += (
                f" Here's what a strong answer includes: {model_answer}"
            )
        return GradingResultResponse(
            is_correct=False,
            feedback=fallback_feedback,
            grading_confidence=0.0,
            model_answer=str(model_answer),
            reteach_triggered=bool(model_answer),
            reteach_content=(
                f"Let me clarify: {model_answer}" if model_answer else None
            ),
        )

    is_correct = result.get("is_correct", False)
    confidence = result.get("confidence", 0.8)
    misconception_type = result.get("misconception_type")
    # Trigger reteach for ALL wrong answers so the student always gets
    # a detailed explanation, not just for "fundamental" misconceptions.
    reteach = not is_correct

    reteach_content = None
    if reteach and model_answer:
        reteach_content = f"Let me clarify: {model_answer}"

    return GradingResultResponse(
        is_correct=is_correct,
        feedback=result.get("feedback", ""),
        misconception_type=misconception_type,
        reteach_triggered=reteach,
        reteach_content=reteach_content,
        grading_confidence=confidence,
        rubric_evaluation={
            "criteria_met": result.get("criteria_met", []),
            "criteria_missed": result.get("criteria_missed", []),
            "misconceptions_detected": result.get(
                "misconceptions_detected", []
            ),
        },
        model_answer=str(model_answer),
    )


# ---------------------------------------------------------------------------
# 7. Long answer (AI-graded, with extra detail)
# ---------------------------------------------------------------------------


async def grade_long_answer(
    question: dict, student_answer: str,
) -> GradingResultResponse:
    result = await grade_short_answer(question, student_answer)

    # Always include model answer for long answers
    rubric = question.get("rubric") or {}
    model_answer = rubric.get("model_answer") or question.get(
        "correct_answer", ""
    )
    result.model_answer = str(model_answer)

    # If low confidence, add self-evaluation note
    if result.grading_confidence < 0.7:
        result.feedback += (
            " (Note: I'm not fully confident in this assessment. "
            "Let me know if you think I've misjudged anything.)"
        )

    return result


# ---------------------------------------------------------------------------
# 8. Misconception classifier
# ---------------------------------------------------------------------------


def classify_misconception(
    grading_result: dict,
) -> str | None:
    """Classify the type of misconception from a grading result.

    Returns 'near_miss', 'fundamental', 'incomplete', or None.
    """
    # If the LLM already classified it, use that
    existing = grading_result.get("misconception_type")
    if existing in ("near_miss", "fundamental", "incomplete"):
        return existing

    # Fallback heuristic
    rubric_eval = grading_result.get("rubric_evaluation") or {}
    criteria_met = rubric_eval.get("criteria_met", [])
    criteria_missed = rubric_eval.get("criteria_missed", [])

    total_criteria = len(criteria_met) + len(criteria_missed)
    if total_criteria == 0:
        return None

    met_ratio = len(criteria_met) / total_criteria

    if met_ratio >= 0.5:
        return "near_miss"
    return "fundamental"
