"""Invite and referral service for beta sharing."""

from __future__ import annotations

import logging
import random
import string
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

INVITE_CODE_LENGTH = 8


def _generate_code(length: int = INVITE_CODE_LENGTH) -> str:
    """Generate a short random alphanumeric invite code."""
    chars = string.ascii_lowercase + string.digits
    return "".join(random.choices(chars, k=length))


def _generate_share_token() -> str:
    """Generate a longer random token for course sharing."""
    chars = string.ascii_lowercase + string.digits
    return "".join(random.choices(chars, k=24))


async def create_invite(
    supabase,
    inviter_user_id: str,
    email: str | None = None,
    max_uses: int = 10,
) -> dict:
    """Create an invite link. Returns {invite_code, invite_url, expires_at}."""
    code = _generate_code()

    result = supabase.table("user_invites").insert({
        "inviter_user_id": inviter_user_id,
        "invite_code": code,
        "email": email,
        "max_uses": max_uses,
    }).execute()

    row = result.data[0] if result.data else {}
    return {
        "invite_code": code,
        "invite_url": f"https://lecturelink.ca/signup?invite={code}",
        "expires_at": row.get("expires_at"),
        "max_uses": max_uses,
        "use_count": 0,
    }


async def validate_invite(supabase, invite_code: str) -> dict | None:
    """Validate an invite code. Returns invite dict or None if invalid/expired.

    Does NOT consume the invite -- call record_invite_use() at signup.
    """
    result = (
        supabase.table("user_invites")
        .select("*")
        .eq("invite_code", invite_code)
        .single()
        .execute()
    )
    if not result.data:
        return None

    invite = result.data

    # Check expiry
    expires_at = invite.get("expires_at")
    if expires_at:
        if isinstance(expires_at, str):
            expires_at = datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
        if expires_at < datetime.now(timezone.utc):
            return None

    # Check usage limit
    if invite.get("use_count", 0) >= invite.get("max_uses", 10):
        return None

    return invite


async def record_invite_use(
    supabase,
    invite_code: str,
    new_user_id: str,
) -> None:
    """Record that a new user signed up via this invite code.

    Call after successful user creation.
    """
    invite = (
        supabase.table("user_invites")
        .select("use_count, inviter_user_id")
        .eq("invite_code", invite_code)
        .single()
        .execute()
    ).data

    if not invite:
        return

    supabase.table("user_invites").update({
        "use_count": invite["use_count"] + 1,
    }).eq("invite_code", invite_code).execute()

    # Store referral attribution
    supabase.table("user_onboarding").upsert({
        "user_id": new_user_id,
        "invited_by_user_id": invite["inviter_user_id"],
        "invite_code_used": invite_code,
    }, on_conflict="user_id").execute()


async def get_my_invites(supabase, user_id: str) -> list[dict]:
    """Get all invite links created by a user."""
    result = (
        supabase.table("user_invites")
        .select("invite_code, email, max_uses, use_count, expires_at, created_at")
        .eq("inviter_user_id", user_id)
        .order("created_at", desc=True)
        .execute()
    )
    invites = result.data or []
    for inv in invites:
        inv["invite_url"] = f"https://lecturelink.ca/signup?invite={inv['invite_code']}"
    return invites


async def create_course_share_token(
    supabase,
    course_id: str,
    user_id: str,
) -> dict:
    """Create (or return existing) a share token for a course."""
    existing = (
        supabase.table("course_share_tokens")
        .select("token, expires_at")
        .eq("course_id", course_id)
        .eq("user_id", user_id)
        .execute()
    )
    if existing.data:
        token = existing.data[0]["token"]
    else:
        token = _generate_share_token()
        supabase.table("course_share_tokens").insert({
            "course_id": course_id,
            "user_id": user_id,
            "token": token,
        }).execute()

    return {
        "share_token": token,
        "share_url": f"https://lecturelink.ca/preview/{token}",
    }
