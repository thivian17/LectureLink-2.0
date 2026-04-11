"""Question generator — creates quiz questions from grounding chunks."""

from __future__ import annotations

import asyncio
import json
import uuid
import logging

from .genai_client import get_genai_client as _get_client

logger = logging.getLogger(__name__)


async def _generate_with_retry(
    client,
    prompt: str,
    *,
    model: str,
    max_retries: int = 2,
    base_delay: float = 1.0,
) -> str | None:
    """Call Gemini with retry on transient failures. Returns raw text or None."""
    for attempt in range(max_retries + 1):
        try:
            response = await client.aio.models.generate_content(
                model=model,
                contents=prompt,
                config={
                    "response_mime_type": "application/json",
                    "temperature": 0.5,
                },
            )
            text = response.text
            if not text or not text.strip():
                logger.warning(
                    "Power quiz Gemini returned empty response (attempt %d/%d)",
                    attempt + 1, max_retries + 1,
                )
                if attempt < max_retries:
                    await asyncio.sleep(base_delay * (2 ** attempt))
                    continue
                return None
            return text
        except Exception:
            logger.error(
                "Power quiz Gemini call failed (attempt %d/%d)",
                attempt + 1, max_retries + 1, exc_info=True,
            )
            if attempt < max_retries:
                await asyncio.sleep(base_delay * (2 ** attempt))
            else:
                return None
    return None


def _parse_power_quiz_question(
    raw: dict,
    concept_id: str,
    concept_title: str,
) -> dict | None:
    """Parse a raw Gemini quiz question into session data format.

    Returns None if the question is invalid. Handles multiple option
    shapes (strings vs dicts) and correct-answer encodings (index,
    letter label, answer text, or is_correct flag).
    """
    question_text = str(raw.get("question_text", "")).strip()
    if not question_text:
        return None

    raw_options = raw.get("options", [])
    options: list[str] = []
    for opt in raw_options:
        if isinstance(opt, str):
            options.append(opt)
        elif isinstance(opt, dict):
            text = opt.get("text", "") or opt.get("label", "")
            if text:
                options.append(str(text))
        else:
            options.append(str(opt))

    if len(options) < 3:
        logger.warning(
            "Power quiz: skipping question with %d options: %s",
            len(options), question_text[:60],
        )
        return None

    # Resolve correct index — try multiple formats Gemini might return
    correct_index: int | None = None
    raw_idx = raw.get("correct_index")
    if isinstance(raw_idx, int):
        correct_index = raw_idx
    elif isinstance(raw_idx, str) and raw_idx.strip().isdigit():
        correct_index = int(raw_idx.strip())

    correct_answer_raw = str(raw.get("correct_answer", "")).strip()
    if correct_index is None and correct_answer_raw:
        upper = correct_answer_raw.upper()
        if len(upper) == 1 and upper.isalpha():
            correct_index = ord(upper) - ord("A")
        else:
            for i, opt in enumerate(options):
                if correct_answer_raw.lower() in opt.lower():
                    correct_index = i
                    break

    if correct_index is None or not (0 <= correct_index < len(options)):
        if raw_options and isinstance(raw_options[0], dict):
            for i, opt in enumerate(raw_options):
                if isinstance(opt, dict) and opt.get("is_correct"):
                    correct_index = i
                    break

    if correct_index is None or not (0 <= correct_index < len(options)):
        logger.warning(
            "Power quiz: could not resolve correct_index for: %s",
            question_text[:60],
        )
        return None

    return {
        "question_id": str(uuid.uuid4()),
        "question_text": question_text,
        "options": options,
        "concept_id": concept_id,
        "concept_title": concept_title,
        "_correct_answer": options[correct_index],
        "_correct_index": correct_index,
        "_explanation": str(raw.get("explanation", "")),
        "_stored_question_id": None,
        "_source": "generated",
    }

GENERATOR_MODEL = "gemini-2.5-flash"

GENERATOR_SYSTEM_PROMPT = """\
Generate quiz questions from lecture content.

For each concept in the quiz plan, create ONE question using ONLY the provided \
grounding chunks as source material.

Question types (vary across the quiz):
- mcq: 4 options, exactly 1 correct. Distractors should be plausible \
misconceptions, not obviously wrong.
- short_answer: Requires 1-3 sentence response.
- true_false: Statement that is clearly true or false based on the lecture content.

For each question provide:
1. question_text: Clear, unambiguous question
2. question_type: "mcq" | "short_answer" | "true_false"
3. options: (mcq only) [{"label": "A", "text": "...", "is_correct": true/false}]
4. correct_answer: The correct answer text
5. explanation: Why this is correct, referencing lecture content
6. source_chunk_ids: Which chunk IDs this question is based on
7. concept_id: Which concept this tests

Difficulty guidelines:
- easy: Recall/recognition (Bloom's: remember, understand)
- medium: Application of concepts (Bloom's: apply, analyze)
- hard: Analysis/synthesis across concepts (Bloom's: evaluate, create)

CRITICAL: Every question MUST be answerable from the provided chunks. Do not \
use external knowledge.

Output as JSON array of question objects."""


async def generate_questions(
    quiz_plan: dict,
    critic_feedback: list[dict] | None = None,
) -> list[dict]:
    """Generate quiz questions from a quiz plan.

    On first call, generates fresh questions. On subsequent calls
    (with critic_feedback), revises flagged questions.
    """
    difficulty = quiz_plan["difficulty"]

    concept_blocks = []
    for item in quiz_plan["concepts"]:
        concept = item["concept"]
        chunks = item["grounding_chunks"]

        chunk_text = "\n\n".join([
            f"[Chunk ID: {c['id']}]\n{c['content']}"
            for c in chunks
        ])

        subconcepts = concept.get("subconcepts") or []
        subconcept_text = ""
        if subconcepts:
            sc_lines = [
                f"  - {sc['title']}: {sc.get('description', '')}"
                for sc in subconcepts
            ]
            subconcept_text = "\nSubconcepts:\n" + "\n".join(sc_lines) + "\n"

        block = (
            f"### Concept: {concept['title']}\n"
            f"Category: {concept.get('category', 'concept')}\n"
            f"Concept ID: {concept['id']}\n"
            f"Description: {concept.get('description', 'N/A')}\n"
            f"{subconcept_text}\n"
            f"Source Material:\n{chunk_text}"
        )
        concept_blocks.append(block)

    prompt_parts = [
        f"Difficulty: {difficulty}\n",
        f"Generate {quiz_plan['num_questions']} questions.\n",
        "\n---\n".join(concept_blocks),
    ]

    if critic_feedback:
        revision_section = (
            "\n\n## REVISION INSTRUCTIONS\n"
            "The following questions were flagged. "
            "Regenerate ONLY these questions with the given feedback:\n"
        )
        for fb in critic_feedback:
            if fb["verdict"] == "revise":
                revision_section += (
                    f"\nQuestion {fb['question_index']}: "
                    f"{fb['verdict'].upper()}\n"
                    f"Feedback: {fb['feedback']}\n"
                    f"Suggested revision: "
                    f"{fb.get('suggested_revision', 'N/A')}\n---"
                )
        prompt_parts.append(revision_section)

    user_prompt = "\n".join(prompt_parts)

    max_attempts = 2
    last_error: Exception | None = None

    for attempt in range(max_attempts):
        try:
            response = await _get_client().aio.models.generate_content(
                model=GENERATOR_MODEL,
                contents=user_prompt,
                config={
                    "system_instruction": GENERATOR_SYSTEM_PROMPT,
                    "temperature": 0.7,
                    "response_mime_type": "application/json",
                },
            )

            raw_text = response.text
            if not raw_text:
                logger.warning(
                    "Generator returned empty response (attempt %d/%d)",
                    attempt + 1, max_attempts,
                )
                continue

            questions = json.loads(raw_text)

            validated = []
            for i, q in enumerate(questions):
                q["question_index"] = i

                if q.get("question_type") == "mcq":
                    options = q.get("options", [])
                    if len(options) != 4:
                        logger.warning(
                            "Question %d: MCQ has %d options, expected 4",
                            i, len(options),
                        )
                        continue
                    correct_count = sum(
                        1 for o in options if o.get("is_correct")
                    )
                    if correct_count != 1:
                        logger.warning(
                            "Question %d: MCQ has %d correct, expected 1",
                            i, correct_count,
                        )
                        continue

                required = [
                    "question_text", "question_type",
                    "correct_answer", "explanation",
                ]
                if all(q.get(f) for f in required):
                    validated.append(q)
                else:
                    missing = [f for f in required if not q.get(f)]
                    logger.warning(
                        "Question %d: Missing fields: %s", i, missing
                    )

            return validated

        except (json.JSONDecodeError, TypeError) as e:
            last_error = e
            logger.warning(
                "Generator returned invalid JSON (attempt %d/%d): %s",
                attempt + 1, max_attempts, e,
            )
            continue
        except Exception as e:
            logger.error("Question generation failed: %s", e, exc_info=True)
            raise

    # All attempts failed — return empty list so the caller can handle gracefully
    logger.error(
        "Generator failed after %d attempts: %s", max_attempts, last_error
    )
    return []


# ---------------------------------------------------------------------------
# Power quiz question generation (Learn Mode)
# ---------------------------------------------------------------------------

POWER_QUIZ_MODEL = "gemini-2.5-flash"


async def generate_power_quiz_questions(
    concept_list: str,
    context: str,
    num_questions: int,
    title_to_id: dict[str, str] | None = None,
) -> list[dict]:
    """Generate MCQ questions for a power quiz.

    Returns a list of question dicts ready for persistence and client delivery.
    Each dict includes question_text, options, concept_id, concept_title,
    and internal fields prefixed with _.
    """
    title_to_id = title_to_id or {}

    prompt = (
        f"Generate exactly {num_questions} multiple-choice quiz questions.\n"
        f"Concepts to cover: {concept_list}\n"
        "Interleave questions across concepts (don't group by concept).\n\n"
        f"Lecture Content:\n{context}\n\n"
        "Rules:\n"
        "- Each question must have exactly 4 options (A-D)\n"
        "- One correct answer per question\n"
        "- CRITICAL: Every question MUST be directly answerable from the lecture "
        "content provided above. Do NOT use outside knowledge.\n"
        "- Vary difficulty: some recognition, some application\n"
        "- Include the concept_title for each question\n\n"
        "Respond ONLY with valid JSON array:\n"
        "[\n"
        '  {\n'
        '    "question_text": "...",\n'
        '    "options": ["A) ...", "B) ...", "C) ...", "D) ..."],\n'
        '    "correct_answer": "A",\n'
        '    "correct_index": 0,\n'
        '    "explanation": "...",\n'
        '    "concept_title": "..."\n'
        '  }\n'
        "]"
    )

    raw_text = await _generate_with_retry(
        _get_client(), prompt, model=POWER_QUIZ_MODEL,
    )
    if raw_text is None:
        logger.error(
            "Power quiz: Gemini failed after all retries (concepts=%s, num_questions=%d)",
            concept_list[:120], num_questions,
        )
        return []

    try:
        parsed = json.loads(raw_text)
    except json.JSONDecodeError:
        logger.error(
            "Power quiz: failed to parse Gemini JSON response: %s",
            raw_text[:200], exc_info=True,
        )
        return []

    if isinstance(parsed, dict):
        raw_questions = parsed.get("questions", []) or []
    elif isinstance(parsed, list):
        raw_questions = parsed
    else:
        logger.warning(
            "Power quiz: unexpected Gemini response shape %s", type(parsed).__name__,
        )
        raw_questions = []

    # Fall back to the first known concept when Gemini omits concept_title
    fallback_title = ""
    fallback_concept_id = ""
    if title_to_id:
        fallback_title = next(iter(title_to_id.keys()), "")
        fallback_concept_id = title_to_id.get(fallback_title, "")

    results: list[dict] = []
    for raw_q in raw_questions[:num_questions]:
        if not isinstance(raw_q, dict):
            logger.warning(
                "Power quiz: skipping non-dict question entry: %s",
                str(raw_q)[:80],
            )
            continue
        concept_title = str(raw_q.get("concept_title", "")).strip() or fallback_title
        concept_id_for_q = title_to_id.get(concept_title, "") or fallback_concept_id

        parsed_q = _parse_power_quiz_question(raw_q, concept_id_for_q, concept_title)
        if parsed_q is not None:
            results.append(parsed_q)

    logger.info(
        "Power quiz: parsed %d/%d valid questions from Gemini",
        len(results), len(raw_questions),
    )

    return results
