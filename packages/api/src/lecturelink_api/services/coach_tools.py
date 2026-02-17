"""FunctionTool wrappers for the Study Coach agent."""

from __future__ import annotations

import json


async def get_performance_tool(
    course_id: str,
    user_id: str,
) -> str:
    """Get the student's performance analytics for a course.

    Returns concept mastery scores, overall metrics, weak areas,
    and quiz history as a JSON string.

    Args:
        course_id: The course to analyze
        user_id: The student's user ID
    """
    from supabase import create_client

    from lecturelink_api.config import get_settings
    from .performance import get_performance

    settings = get_settings()
    sb = create_client(settings.SUPABASE_URL, settings.SUPABASE_ANON_KEY)
    result = await get_performance(sb, course_id, user_id)
    return json.dumps(result, default=str)


async def get_upcoming_assessments_tool(
    course_id: str,
) -> str:
    """Get upcoming assessments for a course with their concept links.

    Returns assessments with due dates, weights, and linked concept IDs.

    Args:
        course_id: The course to check
    """
    from supabase import create_client

    from lecturelink_api.config import get_settings

    settings = get_settings()
    sb = create_client(settings.SUPABASE_URL, settings.SUPABASE_ANON_KEY)

    assessments_result = (
        sb.table("assessments")
        .select("id, title, type, due_date, weight_percent, topics")
        .eq("course_id", course_id)
        .order("due_date")
        .execute()
    )

    assessment_ids = [a["id"] for a in (assessments_result.data or [])]
    links_map: dict[str, list[str]] = {}
    if assessment_ids:
        links_result = (
            sb.table("concept_assessment_links")
            .select("assessment_id, concept_id, relevance_score")
            .in_("assessment_id", assessment_ids)
            .execute()
        )
        for link in links_result.data or []:
            links_map.setdefault(link["assessment_id"], []).append(
                link["concept_id"]
            )

    assessments = []
    for a in assessments_result.data or []:
        assessments.append({
            **a,
            "linked_concept_ids": links_map.get(a["id"], []),
        })

    return json.dumps(assessments, default=str)
