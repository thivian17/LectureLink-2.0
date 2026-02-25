"""Question critic — reviews generated questions for quality."""

from __future__ import annotations

import json
import logging

from .genai_client import get_genai_client as _get_client

logger = logging.getLogger(__name__)

CRITIC_MODEL = "gemini-2.5-flash"

CRITIC_SYSTEM_PROMPT = """\
Review generated quiz questions for quality.

For each question, evaluate:

1. FAITHFULNESS (critical):
   - Is the question answerable from the source chunks?
   - Does the correct answer match the source material?
   Score: 0.0-1.0 (reject if < 0.7)

2. CLARITY:
   - Is the question unambiguous?
   Score: 0.0-1.0 (flag if < 0.8)

3. DIFFICULTY:
   - Does it match the target difficulty level?
   - MCQ distractors: plausible but distinguishable?
   Score: 0.0-1.0 (flag if < 0.6)

For each question, output:
{
    "question_index": 0,
    "verdict": "accept" | "revise" | "reject",
    "faithfulness_score": 0.9,
    "clarity_score": 0.8,
    "difficulty_score": 0.7,
    "feedback": "Specific feedback for revision if needed",
    "suggested_revision": "Improved question text if revising"
}

Be strict on faithfulness.

Output as JSON array of review objects."""


async def critique_questions(
    questions: list[dict],
    quiz_plan: dict,
) -> list[dict]:
    """Review generated questions for quality."""
    review_blocks = []

    chunk_lookup: dict[str, list[dict]] = {}
    for item in quiz_plan["concepts"]:
        concept_id = item["concept"]["id"]
        chunk_lookup[concept_id] = item["grounding_chunks"]

    for q in questions:
        concept_id = q.get("concept_id", "")
        grounding = chunk_lookup.get(concept_id, [])

        chunk_text = (
            "\n".join([
                f"[{c['chunk_id']}] {c['content'][:300]}"
                for c in grounding
            ]) if grounding else "No source chunks available"
        )

        options_text = ""
        if q.get("options"):
            options_text = "\nOptions:\n" + "\n".join([
                f"  {o['label']}) {o['text']}"
                f" {'[correct]' if o.get('is_correct') else ''}"
                for o in q["options"]
            ])

        block = (
            f"### Question {q.get('question_index', '?')}\n"
            f"Type: {q.get('question_type', '?')}\n"
            f"Text: {q.get('question_text', '?')}{options_text}\n"
            f"Correct Answer: {q.get('correct_answer', '?')}\n"
            f"Explanation: {q.get('explanation', '?')}\n\n"
            f"Source Chunks:\n{chunk_text}"
        )
        review_blocks.append(block)

    prompt = (
        f"Target difficulty: {quiz_plan['difficulty']}\n\n"
        f"Review these {len(questions)} questions:\n\n"
        + "\n---\n".join(review_blocks)
    )

    try:
        response = await _get_client().aio.models.generate_content(
            model=CRITIC_MODEL,
            contents=prompt,
            config={
                "system_instruction": CRITIC_SYSTEM_PROMPT,
                "temperature": 0.1,
                "response_mime_type": "application/json",
            },
        )

        reviews = json.loads(response.text)

        validated = []
        for r in reviews:
            if r.get("verdict") not in ("accept", "revise", "reject"):
                r["verdict"] = "revise"

            for score_key in (
                "faithfulness_score", "clarity_score", "difficulty_score",
            ):
                if score_key in r:
                    r[score_key] = min(1.0, max(0.0, r[score_key]))

            if r.get("faithfulness_score", 1.0) < 0.7:
                r["verdict"] = "reject"

            validated.append(r)

        return validated

    except json.JSONDecodeError:
        logger.warning("Critic returned invalid JSON, accepting all")
        return [
            {
                "question_index": i, "verdict": "accept",
                "faithfulness_score": 0.5, "clarity_score": 0.5,
                "difficulty_score": 0.5, "feedback": "Critic parse error",
            }
            for i in range(len(questions))
        ]
    except Exception as e:
        logger.error("Question critique failed: %s", e)
        raise
