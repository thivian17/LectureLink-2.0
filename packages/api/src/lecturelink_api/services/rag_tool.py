"""FunctionTool wrapper for RAG Q&A — used by the Phase 3 Study Coach agent."""

from __future__ import annotations

import json

from .rag import ask_lecture_question


async def ask_question_tool(
    question: str,
    course_id: str,
    lecture_ids: str = "",
) -> str:
    """Ask a question about lecture content and get a cited answer.

    This is a FunctionTool callable for the Study Coach agent.

    Args:
        question: The student's question about the lecture
        course_id: ID of the course to search within
        lecture_ids: Comma-separated lecture IDs to filter (optional)

    Returns:
        JSON string with answer, sources, and follow-up suggestions
    """
    from supabase import create_client

    from lecturelink_api.config import get_settings

    settings = get_settings()
    supabase = create_client(settings.SUPABASE_URL, settings.SUPABASE_ANON_KEY)

    lecture_id_list = (
        [lid.strip() for lid in lecture_ids.split(",") if lid.strip()] or None
    )

    result = await ask_lecture_question(
        supabase=supabase,
        course_id=course_id,
        question=question,
        lecture_ids=lecture_id_list,
    )

    return json.dumps(result)
