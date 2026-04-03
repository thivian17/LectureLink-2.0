"""Routes for lecture search and Q&A."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from lecturelink_api.auth import get_authenticated_supabase, get_current_user
from lecturelink_api.config import Settings, get_settings
from lecturelink_api.middleware.rate_limit import check_rate_limit
from lecturelink_api.models.api_models import (
    QARequest,
    QAResponse,
    SearchRequest,
    SearchResult,
)
from lecturelink_api.services.rag import ask_lecture_question
from lecturelink_api.services.search import highlight_search_terms, search_lectures

router = APIRouter(prefix="/api", tags=["search"])




@router.post("/search", response_model=list[SearchResult])
async def search(
    body: SearchRequest,
    user: dict = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
):
    sb = get_authenticated_supabase(user, settings)

    # Verify course ownership
    course = (
        sb.table("courses")
        .select("id, name")
        .eq("id", body.course_id)
        .eq("user_id", user["id"])
        .execute()
    )
    if not course.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Course not found"
        )

    chunks = await search_lectures(
        supabase=sb,
        course_id=body.course_id,
        query=body.query,
        lecture_ids=body.lecture_ids,
        limit=body.limit,
        user_id=user["id"],
    )

    # Add highlights
    results = []
    for chunk in chunks:
        results.append(
            SearchResult(
                chunk_id=chunk["chunk_id"],
                lecture_id=chunk["lecture_id"],
                lecture_title=chunk["lecture_title"],
                content=chunk["content"],
                start_time=chunk.get("start_time"),
                end_time=chunk.get("end_time"),
                slide_number=chunk.get("slide_number"),
                score=chunk["score"],
                highlight=highlight_search_terms(chunk["content"], body.query),
            )
        )

    try:
        from lecturelink_api.services.observability import track_event

        track_event(user["id"], "search_performed", {
            "course_id": body.course_id,
            "result_count": len(results),
            "search_type": "hybrid",
        })
    except Exception:
        pass

    return results


@router.post("/qa", response_model=QAResponse)
async def question_answer(
    body: QARequest,
    user: dict = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
):
    sb = get_authenticated_supabase(user, settings)

    # Rate limit
    check_rate_limit(sb, user["id"], "qa_question")

    # Verify course ownership and get name
    course = (
        sb.table("courses")
        .select("id, name")
        .eq("id", body.course_id)
        .eq("user_id", user["id"])
        .execute()
    )
    if not course.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Course not found"
        )

    result = await ask_lecture_question(
        supabase=sb,
        course_id=body.course_id,
        question=body.question,
        lecture_ids=body.lecture_ids,
        course_name=course.data[0].get("name", ""),
        user_id=user["id"],
    )

    return QAResponse(**result)
