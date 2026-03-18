"""Question generator — creates quiz questions from grounding chunks."""

from __future__ import annotations

import json
import uuid
import logging

from .genai_client import get_genai_client as _get_client

logger = logging.getLogger(__name__)

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
            f"[Chunk ID: {c['chunk_id']}]\n{c['content']}"
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

        questions = json.loads(response.text)

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

    except json.JSONDecodeError as e:
        logger.error("Generator returned invalid JSON: %s", e)
        raise
    except Exception as e:
        logger.error("Question generation failed: %s", e)
        raise


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

    try:
        response = await _get_client().aio.models.generate_content(
            model=POWER_QUIZ_MODEL,
            contents=prompt,
            config={
                "temperature": 0.5,
                "response_mime_type": "application/json",
            },
        )
        raw_questions = json.loads(response.text)
        if isinstance(raw_questions, dict):
            raw_questions = raw_questions.get("questions", [])
    except Exception:
        logger.error("Power quiz generation failed", exc_info=True)
        raw_questions = []

    results: list[dict] = []
    for q in raw_questions[:num_questions]:
        question_id = str(uuid.uuid4())
        concept_title = q.get("concept_title", "")
        concept_id_for_q = title_to_id.get(concept_title, "")

        results.append({
            "question_id": question_id,
            "question_text": q.get("question_text", ""),
            "options": q.get("options", []),
            "concept_id": concept_id_for_q,
            "concept_title": concept_title,
            "_correct_answer": q.get("correct_answer", "A"),
            "_correct_index": q.get("correct_index", 0),
            "_explanation": q.get("explanation", ""),
            "_stored_question_id": None,
            "_source": "generated",
        })

    return results
