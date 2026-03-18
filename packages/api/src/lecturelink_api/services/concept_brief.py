"""Concept brief generator for Learn Mode sessions.

Generates mastery-calibrated concept briefs grounded in actual lecture content.
Each brief answers three questions (what, why, key relationship) and ends with
a gut-check MCQ.

CRITICAL: "Why it matters" is framed as real-world relevance, NOT exam focus.
"""

from __future__ import annotations

import asyncio
import json
import logging

from .chunk_fetcher import explain_concept, fetch_concept_chunks
from .genai_client import get_genai_client as _get_client
from .mastery import mastery_tier

logger = logging.getLogger(__name__)

BRIEF_MODEL = "gemini-2.5-flash"

CONCEPT_BRIEF_PROMPT = """\
You are creating a study brief for a university student.

CONCEPT: {concept_title}
DESCRIPTION: {concept_description}
COURSE: {course_name}
MASTERY TIER: {mastery_tier} (calibrate complexity accordingly)

LECTURE CONTENT (ground your explanation in this material):
{source_chunks_text}

LINKED ASSESSMENTS: {assessment_context}

Create a concept brief with three sections:

1. **What is this?** — Clear, concise explanation of the concept. Use analogies \
for novice tier. Be precise for advanced tier. Ground in the lecture content above.

2. **Why it matters** — Explain why this concept matters:
   - For THIS COURSE: How it connects to other topics, why the professor teaches it
   - For the REAL WORLD: Practical applications, career relevance, how professionals \
use this knowledge
   Do NOT frame this as "for your exam" — frame it as genuine intellectual and practical value.

3. **Key relationship** — The single most important connection to remember. Could be a \
formula, a cause-effect chain, a comparison, or a dependency on another concept.

Also create a **gut-check question**: A single MCQ (3-4 options) that tests basic \
recognition of the concept. This should be answerable from the brief alone. Include a \
brief explanation for the correct answer.

Respond ONLY with valid JSON, no markdown fences or preamble:
{{
    "what_is_this": "markdown text",
    "why_it_matters": "markdown text",
    "key_relationship": "markdown text",
    "gut_check": {{
        "question_text": "string",
        "options": ["A", "B", "C", "D"],
        "correct_index": 0,
        "explanation": "string"
    }}
}}"""

CLARIFICATION_PROMPT = """\
The student answered a gut-check question incorrectly.

Concept: {concept_title}
Question: {question_text}
Correct answer: {correct_answer}
Student's answer: {student_answer}

Lecture context:
{source_context}

Generate a targeted 2-3 sentence clarification addressing their specific mistake. \
Be direct and efficient — no Socratic dialogue, just a clear correction grounded in \
the lecture content."""


_mastery_tier = mastery_tier  # Use shared implementation


def _parse_json_response(text: str) -> dict | list:
    """Parse JSON from LLM response, stripping markdown fences if present."""
    cleaned = text.strip()
    if cleaned.startswith("```"):
        lines = cleaned.split("\n")
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        cleaned = "\n".join(lines)
    return json.loads(cleaned)


async def generate_concept_brief(
    supabase,
    user_id: str,
    concept_id: str,
    course_id: str,
    mastery_score: float = 0.0,
) -> dict:
    """Generate a concept brief for Learn Mode.

    Returns a dict with sections (what_is_this, why_it_matters, key_relationship),
    a gut_check MCQ, source citations, and mastery tier.
    """
    # 1. Get concept + course name (fast sync DB calls)
    try:
        concept_result = (
            supabase.table("concepts")
            .select("*")
            .eq("id", concept_id)
            .single()
            .execute()
        )
        concept = concept_result.data
    except Exception:
        logger.warning("Failed to fetch concept %s", concept_id)
        concept = {"id": concept_id, "title": "Unknown", "description": ""}

    concept_title = concept.get("title", "Unknown")
    concept_description = concept.get("description", "")

    try:
        course_result = (
            supabase.table("courses")
            .select("name")
            .eq("id", course_id)
            .single()
            .execute()
        )
        course_name = course_result.data.get("name", "")
    except Exception:
        course_name = ""

    # 2. Fetch assessment context
    assessment_context = ""
    try:
        links_result = await asyncio.to_thread(
            lambda: (
                supabase.table("concept_assessment_links")
                .select("assessment_id, relevance_score")
                .eq("concept_id", concept_id)
                .execute()
            )
        )
        if links_result.data:
            assessment_ids = [lnk["assessment_id"] for lnk in links_result.data]
            assessments_result = await asyncio.to_thread(
                lambda: (
                    supabase.table("assessments")
                    .select("id, title")
                    .in_("id", assessment_ids)
                    .execute()
                )
            )
            if assessments_result.data:
                assessment_context = ", ".join(a["title"] for a in assessments_result.data)
    except Exception:
        logger.debug("Failed to fetch assessment links", exc_info=True)

    if not assessment_context:
        assessment_context = "No specific assessments linked"

    # 3. Determine mastery tier
    tier = _mastery_tier(mastery_score)

    # 4. Build prompt (with {source_chunks_text} placeholder for explain_concept)
    prompt = CONCEPT_BRIEF_PROMPT.format(
        concept_title=concept_title,
        concept_description=concept_description or "No description available",
        course_name=course_name or "Unknown course",
        mastery_tier=tier,
        source_chunks_text="{source_chunks_text}",
        assessment_context=assessment_context,
    )

    # 5. Fetch chunks + call Gemini via explain_concept
    result = await explain_concept(
        supabase,
        concept_id=concept_id,
        course_id=course_id,
        query=f"{concept_title} {concept_description}",
        prompt=prompt,
        temperature=0.4,
        response_mime_type="application/json",
    )

    if not isinstance(result, dict) or not result:
        result = {
            "what_is_this": "Unable to generate brief. Please try again.",
            "why_it_matters": "",
            "key_relationship": "",
            "gut_check": {
                "question_text": f"What is {concept_title}?",
                "options": ["I know this", "I need to review", "Not sure"],
                "correct_index": 0,
                "explanation": "Review the concept brief above.",
            },
        }

    # 6. Fetch chunks again for source citations (lightweight — may be cached)
    try:
        chunks = await fetch_concept_chunks(
            supabase,
            concept_id=concept_id,
            course_id=course_id,
            limit=5,
            concept_title=f"{concept_title} {concept_description}",
        )
    except Exception:
        chunks = []

    sources = []
    for chunk in chunks[:5]:
        sources.append({
            "lecture_title": chunk.get("lecture_title", "Unknown"),
            "timestamp_seconds": chunk.get("start_time"),
            "chunk_id": chunk.get("chunk_id", ""),
        })

    # 8. Validate gut_check
    gut_check = result.get("gut_check", {})
    if not gut_check.get("question_text") or not gut_check.get("options"):
        gut_check = {
            "question_text": f"Which of the following best describes {concept_title}?",
            "options": [
                result.get("what_is_this", concept_title)[:80],
                "None of the above",
                "All of the above",
            ],
            "correct_index": 0,
            "explanation": "Review the 'What is this?' section above.",
        }

    return {
        "concept_id": concept_id,
        "concept_title": concept_title,
        "sections": {
            "what_is_this": result.get("what_is_this", ""),
            "why_it_matters": result.get("why_it_matters", ""),
            "key_relationship": result.get("key_relationship", ""),
        },
        "gut_check": gut_check,
        "sources": sources,
        "mastery_tier": tier,
    }


async def generate_expanded_clarification(
    concept_title: str,
    question_text: str,
    correct_answer: str,
    student_answer: str,
    source_chunks: list[str],
) -> str:
    """Generate a targeted 2-3 sentence clarification for a wrong gut-check answer.

    No Socratic dialogue — just efficient correction grounded in lecture content.
    """
    source_context = "\n---\n".join(source_chunks) if source_chunks else "(No content)"

    prompt = CLARIFICATION_PROMPT.format(
        concept_title=concept_title,
        question_text=question_text,
        correct_answer=correct_answer,
        student_answer=student_answer,
        source_context=source_context,
    )

    try:
        response = await _get_client().aio.models.generate_content(
            model=BRIEF_MODEL,
            contents=prompt,
            config={"temperature": 0.3},
        )
        return response.text
    except Exception:
        logger.error("Clarification generation failed", exc_info=True)
        return (
            f"The correct answer is: {correct_answer}. "
            "Review the concept brief for more details."
        )
