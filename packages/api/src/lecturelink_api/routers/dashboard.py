"""Dashboard endpoints — study briefing agent and cross-course chat."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from lecturelink_api.auth import get_authenticated_supabase, get_current_user
from lecturelink_api.config import Settings, get_settings

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])




@router.get("/briefing")
async def get_dashboard_briefing(
    user: dict = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
):
    """Get personalized dashboard briefing.

    Returns deterministic context + LLM-generated greeting.
    Cached in Redis for 3 hours per user.
    """
    from lecturelink_api.services.dashboard_briefing import get_briefing

    sb = get_authenticated_supabase(user, settings)
    return await get_briefing(sb, user["id"])


class DashboardChatRequest(BaseModel):
    message: str
    conversation_history: list[dict] | None = None


@router.post("/chat")
async def dashboard_chat(
    body: DashboardChatRequest,
    user: dict = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
):
    """Cross-course study chat — emotional support + practical advice.

    Unlike the per-course coach chat, this gathers context across ALL
    courses for holistic advice.
    """
    from lecturelink_api.services.dashboard_briefing import chat_cross_course

    sb = get_authenticated_supabase(user, settings)
    return await chat_cross_course(
        sb, user["id"], body.message, body.conversation_history
    )


@router.delete("/briefing/cache")
async def invalidate_briefing_cache(
    user: dict = Depends(get_current_user),
):
    """Invalidate the cached briefing (e.g., after completing a session)."""
    from lecturelink_api.services.redis_client import cache_delete

    await cache_delete(f"dashboard_briefing:{user['id']}")
    return {"status": "cleared"}
