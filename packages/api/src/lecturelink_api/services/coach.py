"""Study Coach service — Gemini-powered personalized study advice."""

from __future__ import annotations

import json
import logging
from collections.abc import AsyncIterator

from .genai_client import get_genai_client as _get_client

logger = logging.getLogger(__name__)

COACH_MODEL = "gemini-2.5-flash"


COACH_SYSTEM_PROMPT = """\
You are an expert study coach helping a university student. You will be provided with:
1. The student's performance data (concept mastery, quiz scores, trends)
2. Upcoming assessments with their linked concepts
3. The student's message/question

Respond conversationally with actionable study advice. Your response should include:
- A brief assessment of their current standing
- Specific recommendations (which concepts to focus on, which lectures to revisit)
- Encouragement based on their progress and trends

If the student asks a specific content question, answer it and relate it back to their \
study plan. If they ask for a study plan, generate one prioritized by upcoming assessments \
and weak concepts.

Keep responses focused and concise. Use concept names and lecture references.
Output as JSON:
{
    "message": "Your conversational response with study advice...",
    "recommendations": [
        {"concept": "Concept Name", "action": "What to do", "priority": "high/medium/low"}
    ],
    "suggested_quiz": {"focus": "concept_id or null", "difficulty": "adaptive"}
}"""


async def chat_with_coach(
    supabase,
    course_id: str,
    user_id: str,
    message: str,
    conversation_history: list[dict] | None = None,
) -> dict:
    """Process a single conversation turn with the Study Coach.

    Args:
        supabase: Supabase client
        course_id: Course context
        user_id: Student's user ID
        message: Student's message
        conversation_history: Previous messages [{role, content}]

    Returns:
        {message, recommendations[{concept, action, priority}], suggested_quiz}
    """
    from .performance import get_performance

    # 1. Fetch performance data
    performance = await get_performance(supabase, course_id, user_id)

    # 2. Fetch upcoming assessments
    assessments_result = (
        supabase.table("assessments")
        .select("id, title, type, due_date, weight_percent, topics")
        .eq("course_id", course_id)
        .order("due_date")
        .execute()
    )

    # 3. Get course name
    course_result = (
        supabase.table("courses")
        .select("name")
        .eq("id", course_id)
        .single()
        .execute()
    )
    course_name = course_result.data.get("name", "") if course_result.data else ""

    # 4. Build compact context
    perf_summary = {
        "overall": performance["overall"],
        "weak_concepts": [
            {"title": c["title"], "mastery": c["mastery"], "trend": c["trend"]}
            for c in performance["concepts"]
            if c["concept_id"] in performance["weak_concepts"]
        ][:10],
        "strong_concepts_count": len(performance["strong_concepts"]),
        "total_concepts": len(performance["concepts"]),
        "recent_quizzes": performance["quiz_history"][:5],
    }

    context = (
        f"Course: {course_name}\n\n"
        f"Student Performance:\n{json.dumps(perf_summary, indent=2, default=str)}\n\n"
        f"Upcoming Assessments:\n"
        f"{json.dumps(assessments_result.data or [], indent=2, default=str)}"
    )

    # 5. Build prompt with conversation history
    full_prompt = f"{context}\n\nStudent's message: {message}"

    # 6. Call Gemini
    try:
        response = await _get_client().aio.models.generate_content(
            model=COACH_MODEL,
            contents=full_prompt,
            config={
                "system_instruction": COACH_SYSTEM_PROMPT,
                "temperature": 0.4,
                "response_mime_type": "application/json",
            },
        )

        result = json.loads(response.text)
        return {
            "message": result.get("message", "I'm not sure how to help with that."),
            "recommendations": result.get("recommendations", []),
            "suggested_quiz": result.get("suggested_quiz"),
        }

    except json.JSONDecodeError:
        logger.warning("Coach response was not valid JSON, using raw text")
        return {
            "message": response.text,
            "recommendations": [],
            "suggested_quiz": None,
        }
    except Exception as e:
        logger.error("Study Coach failed: %s", e)
        raise


async def stream_coach_response(
    supabase,
    course_id: str,
    user_id: str,
    message: str,
    conversation_history: list[dict] | None = None,
) -> AsyncIterator[str]:
    """Stream a coach chat response as SSE-formatted chunks.

    Mirrors chat_with_coach() context assembly but streams Gemini output
    instead of waiting for the full response.
    """
    from .performance import get_performance

    # 1. Fetch performance data
    performance = await get_performance(supabase, course_id, user_id)

    # 2. Fetch upcoming assessments
    assessments_result = (
        supabase.table("assessments")
        .select("id, title, type, due_date, weight_percent, topics")
        .eq("course_id", course_id)
        .order("due_date")
        .execute()
    )

    # 3. Get course name
    course_result = (
        supabase.table("courses")
        .select("name")
        .eq("id", course_id)
        .single()
        .execute()
    )
    course_name = course_result.data.get("name", "") if course_result.data else ""

    # 4. Build compact context
    perf_summary = {
        "overall": performance["overall"],
        "weak_concepts": [
            {"title": c["title"], "mastery": c["mastery"], "trend": c["trend"]}
            for c in performance["concepts"]
            if c["concept_id"] in performance["weak_concepts"]
        ][:10],
        "strong_concepts_count": len(performance["strong_concepts"]),
        "total_concepts": len(performance["concepts"]),
        "recent_quizzes": performance["quiz_history"][:5],
    }

    context = (
        f"Course: {course_name}\n\n"
        f"Student Performance:\n{json.dumps(perf_summary, indent=2, default=str)}\n\n"
        f"Upcoming Assessments:\n"
        f"{json.dumps(assessments_result.data or [], indent=2, default=str)}"
    )

    full_prompt = f"{context}\n\nStudent's message: {message}"

    # 5. Stream from Gemini
    STREAM_SYSTEM_PROMPT = (
        "You are an expert study coach helping a university student. "
        "Respond conversationally with actionable study advice. "
        "Keep responses focused, concise, and encouraging. "
        "Reference specific concept names and lecture content when available."
    )

    try:
        async for chunk in await _get_client().aio.models.generate_content_stream(
            model=COACH_MODEL,
            contents=full_prompt,
            config={
                "system_instruction": STREAM_SYSTEM_PROMPT,
                "temperature": 0.4,
            },
        ):
            if chunk.text:
                data = json.dumps({"type": "chunk", "content": chunk.text})
                yield f"data: {data}\n\n"
    except Exception as e:
        logger.error("Coach streaming failed: %s", e)
        error_data = json.dumps({"type": "error", "content": "Sorry, I had trouble generating a response."})
        yield f"data: {error_data}\n\n"

    yield f"data: {json.dumps({'type': 'done'})}\n\n"
