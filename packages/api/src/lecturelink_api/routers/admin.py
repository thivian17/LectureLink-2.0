"""Admin read API — analytics overview, user table, bugs, feedback."""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, status
from supabase import create_client

from lecturelink_api.auth import get_current_user
from lecturelink_api.config import Settings, get_settings

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/admin", tags=["admin"])


def _sb_service(settings: Settings):
    """Service-role client — bypasses RLS for admin reads."""
    if settings.SUPABASE_SERVICE_KEY:
        return create_client(settings.SUPABASE_URL, settings.SUPABASE_SERVICE_KEY)
    return create_client(settings.SUPABASE_URL, settings.SUPABASE_ANON_KEY)


async def require_admin(
    user: dict = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> dict:
    """Dependency: raises 403 if caller is not in admin_users table."""
    sb = _sb_service(settings)
    result = (
        sb.table("admin_users").select("role").eq("user_id", user["id"]).execute()
    )
    if not result.data:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required"
        )
    return {**user, "admin_role": result.data[0]["role"]}


@router.get("/overview")
async def get_overview(
    admin: dict = Depends(require_admin),
    settings: Settings = Depends(get_settings),
):
    sb = _sb_service(settings)
    now = datetime.now(UTC)
    day_ago = (now - timedelta(days=1)).isoformat()
    week_ago = (now - timedelta(days=7)).isoformat()
    month_ago = (now - timedelta(days=30)).isoformat()

    dau_res = sb.rpc("count_distinct_users", {"since": day_ago}).execute()
    wau_res = sb.rpc("count_distinct_users", {"since": week_ago}).execute()
    mau_res = sb.rpc("count_distinct_users", {"since": month_ago}).execute()
    total_users = sb.table("profiles").select("id", count="exact").execute()
    sessions_week = (
        sb.table("learn_sessions")
        .select("id", count="exact")
        .gte("created_at", week_ago)
        .execute()
    )
    quiz_week = (
        sb.table("quiz_attempts")
        .select("id", count="exact")
        .gte("created_at", week_ago)
        .execute()
    )
    bugs_open = (
        sb.table("bug_reports")
        .select("id", count="exact")
        .eq("status", "open")
        .execute()
    )
    feedback_unread = (
        sb.table("user_feedback")
        .select("id", count="exact")
        .eq("status", "unread")
        .execute()
    )

    return {
        "dau": dau_res.data or 0,
        "wau": wau_res.data or 0,
        "mau": mau_res.data or 0,
        "total_users": total_users.count or 0,
        "learn_sessions_week": sessions_week.count or 0,
        "quiz_attempts_week": quiz_week.count or 0,
        "bugs_open": bugs_open.count or 0,
        "feedback_unread": feedback_unread.count or 0,
    }


@router.get("/feature-usage")
async def get_feature_usage(
    days: int = Query(default=7, ge=1, le=90),
    admin: dict = Depends(require_admin),
    settings: Settings = Depends(get_settings),
):
    sb = _sb_service(settings)
    since = (datetime.now(UTC) - timedelta(days=days)).isoformat()
    result = (
        sb.table("analytics_events")
        .select("event_type, event_category, created_at")
        .gte("created_at", since)
        .execute()
    )
    counts: dict[str, int] = {}
    for row in result.data or []:
        key = row["event_type"]
        counts[key] = counts.get(key, 0) + 1
    return {"days": days, "event_counts": counts}


@router.get("/users")
async def list_users(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    admin: dict = Depends(require_admin),
    settings: Settings = Depends(get_settings),
):
    sb = _sb_service(settings)
    result = (
        sb.table("profiles")
        .select("id, email, display_name, created_at")
        .order("created_at", desc=True)
        .range(offset, offset + limit - 1)
        .execute()
    )
    users = []
    for profile in result.data or []:
        uid = profile["id"]
        last_event = (
            sb.table("analytics_events")
            .select("created_at")
            .eq("user_id", uid)
            .order("created_at", desc=True)
            .limit(1)
            .execute()
        )
        last_active = last_event.data[0]["created_at"] if last_event.data else None
        sessions = (
            sb.table("learn_sessions")
            .select("id", count="exact")
            .eq("user_id", uid)
            .execute()
        )
        level = (
            sb.table("user_levels")
            .select("current_level, total_xp")
            .eq("user_id", uid)
            .execute()
        )
        users.append(
            {
                **profile,
                "last_active": last_active,
                "session_count": sessions.count or 0,
                "level": level.data[0]
                if level.data
                else {"current_level": 1, "total_xp": 0},
            }
        )
    return {"users": users, "total": len(users), "offset": offset}


@router.get("/bugs")
async def list_bugs(
    status_filter: str | None = Query(default=None, alias="status"),
    severity: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    admin: dict = Depends(require_admin),
    settings: Settings = Depends(get_settings),
):
    sb = _sb_service(settings)
    query = sb.table("bug_reports").select("*").order("created_at", desc=True)
    if status_filter:
        query = query.eq("status", status_filter)
    if severity:
        query = query.eq("severity", severity)
    result = query.range(offset, offset + limit - 1).execute()
    return {"bugs": result.data or [], "offset": offset}


@router.patch("/bugs/{bug_id}")
async def update_bug(
    bug_id: str,
    status_update: str | None = None,
    admin_notes: str | None = None,
    admin: dict = Depends(require_admin),
    settings: Settings = Depends(get_settings),
):
    sb = _sb_service(settings)
    update: dict = {}
    if status_update:
        update["status"] = status_update
        if status_update == "resolved":
            update["resolved_at"] = datetime.now(UTC).isoformat()
    if admin_notes is not None:
        update["admin_notes"] = admin_notes
    if not update:
        raise HTTPException(status_code=400, detail="Nothing to update")
    result = sb.table("bug_reports").update(update).eq("id", bug_id).execute()
    return result.data[0] if result.data else {}


@router.get("/feedback")
async def list_feedback(
    feedback_type: str | None = Query(default=None),
    feature_tag: str | None = Query(default=None),
    status_filter: str | None = Query(default=None, alias="status"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    admin: dict = Depends(require_admin),
    settings: Settings = Depends(get_settings),
):
    sb = _sb_service(settings)
    query = sb.table("user_feedback").select("*").order("created_at", desc=True)
    if feedback_type:
        query = query.eq("feedback_type", feedback_type)
    if feature_tag:
        query = query.eq("feature_tag", feature_tag)
    if status_filter:
        query = query.eq("status", status_filter)
    result = query.range(offset, offset + limit - 1).execute()
    return {"feedback": result.data or [], "offset": offset}


@router.patch("/feedback/{feedback_id}/status")
async def update_feedback_status(
    feedback_id: str,
    new_status: str = Query(..., pattern="^(unread|read|actioned)$"),
    admin: dict = Depends(require_admin),
    settings: Settings = Depends(get_settings),
):
    sb = _sb_service(settings)
    result = (
        sb.table("user_feedback")
        .update({"status": new_status})
        .eq("id", feedback_id)
        .execute()
    )
    return result.data[0] if result.data else {}
