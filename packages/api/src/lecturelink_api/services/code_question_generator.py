"""Coding question generator — creates code practice problems from lecture content."""

from __future__ import annotations

import json
import logging
import re

from .genai_client import get_genai_client as _get_client

logger = logging.getLogger(__name__)

GENERATOR_MODEL = "gemini-2.5-flash"


CODING_QUESTION_SYSTEM_PROMPT = """\
Generate coding practice questions grounded in lecture content.

You receive:
- Lecture content chunks with specific concepts
- Assessment context (what the student is preparing for)
- Student mastery level (0.0-1.0)
- Target programming language

Generate three types of coding questions:

1. **code_writing**: Student implements a function from scratch.
   - Provide a clear problem description referencing lecture concepts
   - Include a function signature and starter code
   - Include example inputs/outputs
   - The starter code should have the function signature and docstring

2. **code_fix**: Student debugs broken code.
   - Provide buggy code that compiles/runs but produces wrong results
   - Describe the expected behavior clearly
   - Include a hint about the bug category (logic error, off-by-one, etc.)
   - The bug must relate to a misconception about a lecture concept

3. **code_explain**: Student reads code and explains its behavior/output.
   - Provide working code that demonstrates a lecture concept
   - Ask specific questions: What does it output? Why? What concept does it use?
   - Code should be non-trivial but readable

Difficulty calibration based on mastery level:
- mastery < 0.3: Simple single-concept problems, heavy scaffolding \
(lots of starter code, detailed hints, simple I/O)
- mastery 0.3-0.6: Multi-step problems combining 2 concepts, \
moderate scaffolding (function signature provided, some guidance)
- mastery 0.6-0.8: Complex implementations with edge cases, \
minimal scaffolding (just the function name, handle edge cases)
- mastery > 0.8: Optimization challenges, multi-concept synthesis, \
no scaffolding (design the solution from scratch)

CRITICAL RULES:
- Every problem MUST be answerable using ONLY concepts from the provided \
lecture chunks. Do not use external knowledge.
- The reference_solution MUST be correct and runnable.
- The grading_rubric MUST be specific and tied to lecture concepts.
- common_mistakes should reflect real student misconceptions about the \
lecture material.
- starter_code must be syntactically valid in the target language.
- example_inputs_outputs must match the reference_solution behavior.

Output as a JSON array where each element has:
{
  "question_text": "Problem description referencing lecture content",
  "question_type": "code_writing | code_fix | code_explain",
  "correct_answer": "reference solution or expected explanation",
  "explanation": "Detailed walkthrough referencing lecture content",
  "source_chunk_ids": ["chunk-id-1"],
  "concept_id": "concept-uuid",
  "difficulty": 0.0-1.0,
  "code_metadata": {
    "language": "python",
    "starter_code": "def func():\\n    # Your code here\\n    pass",
    "reference_solution": "def func():\\n    return 42",
    "grading_rubric": {
      "correctness": {"weight": 40, "criteria": "..."},
      "concept_understanding": {"weight": 30, "criteria": "..."},
      "code_quality": {"weight": 20, "criteria": "..."},
      "edge_cases": {"weight": 10, "criteria": "..."}
    },
    "hints": ["Hint 1", "Hint 2", "Hint 3"],
    "example_inputs_outputs": [{"input": "func(1, 2)", "expected": "3"}],
    "common_mistakes": ["Mistake 1", "Mistake 2"],
    "max_lines": 30,
    "time_limit_minutes": 15,
    "related_lecture_concepts": ["concept name 1"]
  }
}"""

def _repair_json_escapes(text: str) -> str:
    r"""Fix invalid ``\X`` sequences the LLM puts in code strings.

    The LLM often emits raw code inside JSON string values, producing
    sequences like ``\d``, ``\s``, ``\p`` which are not valid JSON
    escapes.  This doubles the backslash so ``json.loads`` succeeds.

    Already-escaped sequences like ``\\d`` are left untouched because
    the regex consumes ``\\`` pairs first via alternation.
    """

    def _fix(m: re.Match) -> str:
        s = m.group(0)
        if s == '\\\\':
            # Already-escaped backslash pair — leave as-is.
            return s
        # Invalid escape like \d, \s, \p → double the backslash.
        return '\\' + s

    # Try \\  (escaped backslash) first so it's consumed as a unit,
    # then match \<invalid_char>.
    return re.sub(r'\\\\|\\[^"\\/bfnrtu]', _fix, text)


_CODING_INDICATORS = frozenset({
    "implement", "code", "program", "algorithm", "function",
    "debug", "write a", "develop", "script",
    "python", "java", "c++", "javascript", "sql", "matlab",
})


def detect_coding_relevance(
    assessment: dict,
    course_topics: list[str] | None = None,
) -> bool:
    """Heuristic: does this assessment likely require coding skills?"""
    if assessment.get("type") in ("homework", "project", "lab"):
        return True

    topics = assessment.get("topics") or []
    for topic in topics:
        topic_lower = topic.lower()
        if any(indicator in topic_lower for indicator in _CODING_INDICATORS):
            return True

    return False


def get_default_rubric(question_type: str) -> dict:
    """Return a sensible default grading rubric for a coding question type."""
    if question_type == "code_writing":
        return {
            "correctness": {
                "weight": 40,
                "criteria": "Does the solution produce correct results?",
            },
            "concept_understanding": {
                "weight": 30,
                "criteria": "Does it demonstrate understanding of the relevant concept?",
            },
            "code_quality": {
                "weight": 20,
                "criteria": "Clean, well-structured code?",
            },
            "edge_cases": {
                "weight": 10,
                "criteria": "Handles edge cases?",
            },
        }
    if question_type == "code_fix":
        return {
            "bug_identification": {
                "weight": 35,
                "criteria": "Did the student identify the bug correctly?",
            },
            "fix_correctness": {
                "weight": 35,
                "criteria": "Does the fix produce correct results?",
            },
            "explanation": {
                "weight": 20,
                "criteria": "Clear explanation of what was wrong and why?",
            },
            "code_quality": {
                "weight": 10,
                "criteria": "Clean, well-structured fix?",
            },
        }
    if question_type == "code_explain":
        return {
            "output_correctness": {
                "weight": 30,
                "criteria": "Did the student predict the correct output?",
            },
            "trace_accuracy": {
                "weight": 30,
                "criteria": "Accurate step-by-step trace of execution?",
            },
            "concept_identification": {
                "weight": 25,
                "criteria": "Identified the relevant concept correctly?",
            },
            "clarity": {
                "weight": 15,
                "criteria": "Clear and well-organized explanation?",
            },
        }
    return get_default_rubric("code_writing")


async def generate_coding_questions(
    quiz_plan: dict,
    language: str = "python",
    critic_feedback: list[dict] | None = None,
    type_distribution: dict | None = None,
) -> list[dict]:
    """Generate coding practice questions from a quiz plan.

    Follows the same structure as ``generate_questions`` in quiz_generator:
    builds concept blocks from grounding chunks, calls Gemini, validates output.
    """
    difficulty = quiz_plan["difficulty"]
    mastery = quiz_plan.get("mastery", 0.5)

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
        f"Programming language: {language}\n",
        f"Difficulty: {difficulty}\n",
        f"Student mastery level: {mastery}\n",
        f"Generate {quiz_plan['num_questions']} coding questions.\n",
        "\n---\n".join(concept_blocks),
    ]

    if type_distribution:
        dist_text = ", ".join(
            f"{int(pct * 100)}% {qtype}" for qtype, pct in type_distribution.items()
        )
        prompt_parts.append(
            f"\nDistribute question types approximately as follows: {dist_text}.\n"
        )
    else:
        prompt_parts.append(
            "\nVary the question types: prefer ~50% code_writing,"
            " ~30% code_fix, ~20% code_explain.\n"
        )

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
                "system_instruction": CODING_QUESTION_SYSTEM_PROMPT,
                "temperature": 0.7,
                "response_mime_type": "application/json",
            },
        )

        raw_text = response.text
        try:
            questions = json.loads(raw_text)
        except json.JSONDecodeError:
            # LLM code strings often contain invalid escapes (\d, \s, …)
            logger.debug("Repairing invalid JSON escapes from coding generator")
            questions = json.loads(_repair_json_escapes(raw_text))

        validated = []
        for i, q in enumerate(questions):
            q["question_index"] = i

            required = [
                "question_text", "question_type",
                "correct_answer", "explanation",
            ]
            if not all(q.get(f) for f in required):
                missing = [f for f in required if not q.get(f)]
                logger.warning(
                    "Coding question %d: Missing fields: %s", i, missing
                )
                continue

            if q["question_type"] not in (
                "code_writing", "code_fix", "code_explain",
            ):
                logger.warning(
                    "Coding question %d: Invalid type %s",
                    i, q["question_type"],
                )
                continue

            # Ensure code_metadata exists with defaults
            meta = q.get("code_metadata") or {}
            meta.setdefault("language", language)
            meta.setdefault("starter_code", "")
            meta.setdefault("reference_solution", q["correct_answer"])
            meta.setdefault(
                "grading_rubric",
                get_default_rubric(q["question_type"]),
            )
            meta.setdefault("hints", [])
            meta.setdefault("example_inputs_outputs", [])
            meta.setdefault("common_mistakes", [])
            meta.setdefault("max_lines", 30)
            meta.setdefault("time_limit_minutes", 15)
            meta.setdefault("related_lecture_concepts", [])
            q["code_metadata"] = meta

            validated.append(q)

        return validated

    except json.JSONDecodeError as e:
        logger.error("Coding generator returned invalid JSON: %s", e)
        raise
    except Exception as e:
        logger.error("Coding question generation failed: %s", e)
        raise
