"""Invite and referral endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from supabase import create_client

from lecturelink_api.auth import get_current_user
from lecturelink_api.config import Settings, get_settings

router = APIRouter(prefix="/api/invites", tags=["invites"])


def _sb(user: dict, settings: Settings):
    client = create_client(settings.SUPABASE_URL, settings.SUPABASE_ANON_KEY)
    client.auth.set_session(user["token"], "")
    return client


class CreateInviteRequest(BaseModel):
    email: str | None = None
    max_uses: int = 10


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_invite(
    body: CreateInviteRequest,
    user: dict = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
):
    """Create an invite link."""
    sb = _sb(user, settings)
    from lecturelink_api.services.invites import create_invite as _create

    return await _create(sb, user["id"], body.email, body.max_uses)


@router.get("")
async def list_my_invites(
    user: dict = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
):
    """List invite links created by the current user."""
    sb = _sb(user, settings)
    from lecturelink_api.services.invites import get_my_invites

    return await get_my_invites(sb, user["id"])


@router.get("/validate/{invite_code}")
async def validate_invite(
    invite_code: str,
    settings: Settings = Depends(get_settings),
):
    """Validate an invite code (public -- no auth required)."""
    sb = create_client(settings.SUPABASE_URL, settings.SUPABASE_ANON_KEY)
    from lecturelink_api.services.invites import validate_invite as _validate

    invite = await _validate(sb, invite_code)
    if not invite:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Invalid or expired invite code",
        )
    return {"valid": True, "invite_code": invite_code}


@router.post("/use/{invite_code}")
async def use_invite(
    invite_code: str,
    user: dict = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
):
    """Record that the current user signed up via this invite."""
    sb = _sb(user, settings)
    from lecturelink_api.services.invites import record_invite_use

    await record_invite_use(sb, invite_code, user["id"])
    return {"status": "recorded"}


@router.post("/courses/{course_id}/share-token")
async def create_share_token(
    course_id: str,
    user: dict = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
):
    """Create a read-only share token for a course."""
    sb = _sb(user, settings)

    # Verify ownership
    course = (
        sb.table("courses")
        .select("id")
        .eq("id", course_id)
        .eq("user_id", user["id"])
        .execute()
    )
    if not course.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Course not found",
        )

    from lecturelink_api.services.invites import create_course_share_token

    return await create_course_share_token(sb, course_id, user["id"])
