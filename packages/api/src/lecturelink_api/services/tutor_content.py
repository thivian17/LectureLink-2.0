"""Content generator — handles on-demand content for the Study Tutor.

Generates teaching blocks, reteach explanations, chat responses,
and pre-generates upcoming concept content.
"""

from __future__ import annotations

import json
import logging
import uuid

from . import tutor_prompts
from .genai_client import get_genai_client as _get_client
from .search import search_lectures

logger = logging.getLogger(__name__)

TUTOR_MODEL = "gemini-2.5-flash"


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


# ---------------------------------------------------------------------------
# 1. Generate next block
# ---------------------------------------------------------------------------


async def generate_next_block(
    supabase,
    session: dict,
    concept_index: int,
    step_index: int,
) -> dict:
    """Generate content for the next step in the current concept.

    Reads the lesson plan from the session and generates the appropriate
    block type (teaching, question, practice, summary, transition).

    Args:
        supabase: Supabase client
        session: Current session dict with lesson_plan
        concept_index: Index into lesson_plan.concepts
        step_index: Index into the concept's outline

    Returns:
        {block_type, content, question?, rubric?}
    """
    plan = session.get("lesson_plan", {})
    concepts = plan.get("concepts", [])

    if concept_index >= len(concepts):
        return {
            "block_type": "complete",
            "content": "All concepts covered! Great work.",
        }

    concept = concepts[concept_index]
    outline = concept.get("outline", [])

    if step_index >= len(outline):
        return {
            "block_type": "concept_complete",
            "content": f'Finished covering "{concept["title"]}".',
        }

    step = outline[step_index]
    step_type = step.get("type", "explain")
    description = step.get("description", "")
    course_id = session.get("course_id", "")
    title = concept["title"]
    mastery = concept.get("mastery", 0.5)
    approach = concept.get("teaching_approach", "application")

    # Check for pre-generated content
    pre_generated = concept.get("generated_content", {})
    blocks = pre_generated.get("blocks", [])
    if step_index < len(blocks):
        block = blocks[step_index]
        if block.get("content") is not None and not block.get("pending"):
            return block

    # Generate content on demand
    chunks = await _get_concept_chunks(supabase, course_id, title)

    if step_type in ("activate", "explain"):
        prompt = tutor_prompts.get_teaching_block_prompt(
            concept_title=title,
            teaching_approach=approach,
            mastery=mastery,
            lecture_chunks=chunks,
            step_description=description,
        )
        content = await _call_gemini(prompt, temperature=0.4)
        return {"block_type": step_type, "content": content}

    if step_type == "check":
        return await _generate_check(
            title,
            step.get("question_type", "short_answer"),
            step.get("targets", title),
            chunks,
            mastery,
        )

    if step_type == "practice":
        prompt = tutor_prompts.get_practice_prompt(
            concept_title=title,
            mastery=mastery,
            lecture_chunks=chunks,
        )
        content = await _call_gemini(prompt, temperature=0.4)
        return {"block_type": "practice", "content": content}

    if step_type == "summary":
        # Get performance from session state
        perf = session.get("concept_performance", {}).get(title, {})
        prompt = tutor_prompts.get_summary_prompt(
            concept_title=title,
            questions_asked=perf.get("questions_asked", 0),
            questions_correct=perf.get("questions_correct", 0),
            key_misconceptions=perf.get("misconceptions", []),
        )
        content = await _call_gemini(prompt, temperature=0.4)
        return {"block_type": "summary", "content": content}

    if step_type == "transition":
        next_title = ""
        if concept_index + 1 < len(concepts):
            next_title = concepts[concept_index + 1]["title"]
        if next_title:
            prompt = tutor_prompts.get_transition_prompt(
                completed_concept=title,
                next_concept=next_title,
            )
            content = await _call_gemini(prompt, temperature=0.4)
        else:
            content = "Let's wrap up this session."
        return {"block_type": "transition", "content": content}

    return {"block_type": step_type, "content": description}


# ---------------------------------------------------------------------------
# 2. Reteach
# ---------------------------------------------------------------------------


async def generate_reteach(
    supabase,
    session: dict,
    concept_title: str,
    original_explanation: str,
    misconception: str,
    misconception_type: str,
) -> str:
    """Generate a reteach explanation from a different angle.

    Args:
        supabase: Supabase client
        session: Current session dict
        concept_title: The concept being reteaught
        original_explanation: What was taught before
        misconception: What the student got wrong
        misconception_type: "near_miss" or "fundamental"

    Returns:
        Reteach content string
    """
    course_id = session.get("course_id", "")
    chunks = await _get_concept_chunks(supabase, course_id, concept_title)

    prompt = tutor_prompts.get_reteach_prompt(
        concept_title=concept_title,
        original_explanation=original_explanation,
        misconception=misconception,
        misconception_type=misconception_type,
        lecture_chunks=chunks,
    )

    return await _call_gemini(prompt, temperature=0.4)


# ---------------------------------------------------------------------------
# 3. Chat response
# ---------------------------------------------------------------------------


async def generate_chat_response(
    supabase,
    session: dict,
    student_message: str,
) -> dict:
    """Handle an inline student chat message during a tutoring session.

    1. Classify relevance
    2. If on_topic/related: generate grounded answer
    3. If off_topic: return redirect message

    Returns:
        {response, relevance}
    """
    course_id = session.get("course_id", "")
    plan = session.get("lesson_plan", {})
    current_concept_idx = session.get("current_concept_index", 0)
    concepts = plan.get("concepts", [])
    current_concept = (
        concepts[current_concept_idx]["title"]
        if current_concept_idx < len(concepts)
        else "general review"
    )

    assessment_ctx = plan.get("_assessment_context", {})
    assessment_topics = assessment_ctx.get("topics", [])

    # Step 1: Classify relevance
    relevance_prompt = tutor_prompts.get_chat_relevance_prompt(
        student_message=student_message,
        current_concept=current_concept,
        assessment_topics=assessment_topics,
    )

    try:
        relevance_response = await _call_gemini_json(
            relevance_prompt,
            temperature=0.1,
        )
        relevance = relevance_response.get("relevance", "related")
        should_answer = relevance_response.get("should_answer", True)
        redirect_msg = relevance_response.get("redirect_message")
    except Exception:
        logger.debug("Relevance classification failed, defaulting to related")
        relevance = "related"
        should_answer = True
        redirect_msg = None

    # Step 2: Respond based on relevance
    if relevance == "off_topic" and not should_answer:
        return {
            "response": redirect_msg
            or (
                "That's a bit outside what we're covering right now. "
                f'Let\'s stay focused on "{current_concept}" — '
                "we can come back to that later."
            ),
            "relevance": "off_topic",
        }

    # For on_topic or related: get lecture context and answer
    chunks = await _get_concept_chunks(supabase, course_id, student_message)

    assessment_context_str = ""
    if assessment_ctx:
        assessment_context_str = (
            f"Preparing for {assessment_ctx.get('assessment_title', 'upcoming assessment')} "
            f"({assessment_ctx.get('days_until', '?')} days away)."
        )

    answer_prompt = tutor_prompts.get_chat_answer_prompt(
        student_message=student_message,
        current_concept=current_concept,
        lecture_chunks=chunks,
        assessment_context=assessment_context_str,
    )

    answer = await _call_gemini(answer_prompt, temperature=0.4)

    return {"response": answer, "relevance": relevance}


# ---------------------------------------------------------------------------
# 4. Pre-generate next concept
# ---------------------------------------------------------------------------


async def pre_generate_next_concept(
    supabase,
    session: dict,
    next_concept_index: int,
) -> dict:
    """Pre-generate content for the next concept in the plan.

    Called in background when student is ~75% through current concept.

    Returns:
        Concept content dict for caching in the session.
    """
    from .tutor_planner import generate_concept_content

    plan = session.get("lesson_plan", {})
    concepts = plan.get("concepts", [])

    if next_concept_index >= len(concepts):
        return {}

    concept = concepts[next_concept_index]
    course_id = session.get("course_id", "")
    assessment_ctx = plan.get("_assessment_context", {})
    assessment_context_str = (
        f"Assessment: {assessment_ctx.get('assessment_title', 'upcoming')} "
        f"({assessment_ctx.get('days_until', '?')} days away)."
    )

    try:
        content = await generate_concept_content(
            supabase,
            course_id,
            concept,
            assessment_context_str,
        )
        logger.info(
            "Pre-generated content for concept %d: %s",
            next_concept_index,
            concept["title"],
        )
        return content
    except Exception:
        logger.warning(
            "Pre-generation failed for concept %d",
            next_concept_index,
            exc_info=True,
        )
        return {}


# ---------------------------------------------------------------------------
# 5. Session summary text
# ---------------------------------------------------------------------------


async def generate_session_summary_text(session_data: dict) -> str:
    """Generate a natural-language summary of a completed tutoring session."""
    prompt = tutor_prompts.get_session_summary_prompt(session_data)
    return await _call_gemini(prompt, temperature=0.3)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


async def _get_concept_chunks(
    supabase,
    course_id: str,
    query: str,
) -> list[dict]:
    """Fetch lecture chunks for a concept or query."""
    if not course_id:
        return []
    try:
        chunks = await search_lectures(
            supabase=supabase,
            course_id=course_id,
            query=query,
            limit=6,
        )
        return [
            {
                "content": c["content"],
                "lecture_title": c["lecture_title"],
                "start_time": c.get("start_time"),
            }
            for c in chunks
        ]
    except Exception:
        logger.debug("Chunk retrieval failed for %r", query[:40], exc_info=True)
        return []


async def _call_gemini(prompt: str, temperature: float = 0.4) -> str:
    """Make a text-generation Gemini call with error handling."""
    try:
        response = await _get_client().aio.models.generate_content(
            model=TUTOR_MODEL,
            contents=prompt,
            config={"temperature": temperature},
        )
        logger.info(
            "Gemini call: %d input tokens, %d output tokens",
            response.usage_metadata.prompt_token_count,
            response.usage_metadata.candidates_token_count,
        )
        return response.text
    except Exception:
        logger.error("Gemini text generation failed", exc_info=True)
        return "I'm having trouble generating a response. Let me try again."


async def _call_gemini_json(
    prompt: str,
    temperature: float = 0.3,
) -> dict | list:
    """Make a JSON-mode Gemini call with error handling."""
    try:
        response = await _get_client().aio.models.generate_content(
            model=TUTOR_MODEL,
            contents=prompt,
            config={
                "temperature": temperature,
                "response_mime_type": "application/json",
            },
        )
        logger.info(
            "Gemini JSON call: %d input tokens, %d output tokens",
            response.usage_metadata.prompt_token_count,
            response.usage_metadata.candidates_token_count,
        )
        return _parse_json_response(response.text)
    except json.JSONDecodeError:
        logger.error("Gemini returned invalid JSON")
        return {}
    except Exception:
        logger.error("Gemini JSON generation failed", exc_info=True)
        return {}


async def _generate_check(
    concept_title: str,
    question_type: str,
    targets: str,
    chunks: list[dict],
    mastery: float,
) -> dict:
    """Generate a check question with rubric."""
    prompt = tutor_prompts.get_check_question_prompt(
        concept_title=concept_title,
        question_type=question_type,
        target_understanding=targets,
        lecture_chunks=chunks,
        mastery=mastery,
    )

    try:
        data = await _call_gemini_json(prompt, temperature=0.3)
        if isinstance(data, dict) and data.get("question_text"):
            data["question_id"] = str(uuid.uuid4())
            data["concept_title"] = concept_title
            return {
                "block_type": "check",
                "content": data["question_text"],
                "question": data,
                "rubric": data.get("rubric", {}),
            }
    except Exception:
        logger.debug("Check question JSON parse failed", exc_info=True)

    return {
        "block_type": "check",
        "content": f"Can you explain the key idea behind {concept_title}?",
        "question": {
            "question_id": str(uuid.uuid4()),
            "concept_title": concept_title,
            "question_text": f"Can you explain the key idea behind {concept_title}?",
            "question_type": "short_answer",
            "correct_answer": concept_title,
        },
        "rubric": {"must_mention": [concept_title], "model_answer": concept_title},
    }
