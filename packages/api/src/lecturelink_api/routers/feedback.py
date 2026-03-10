"""Feedback submission router with GitHub Issues integration."""

from __future__ import annotations

import logging
import uuid

import httpx
from fastapi import APIRouter, Depends, HTTPException, UploadFile, status
from supabase import create_client

from lecturelink_api.auth import get_current_user
from lecturelink_api.config import Settings, get_settings
from lecturelink_api.models.feedback_models import FeedbackResponse, FeedbackSubmitRequest

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["feedback"])

_ALLOWED_TYPES = {"image/png", "image/jpeg", "image/webp"}
_MAX_FILE_SIZE = 5 * 1024 * 1024  # 5 MB


def _sb(user: dict, settings: Settings):
    client = create_client(settings.SUPABASE_URL, settings.SUPABASE_ANON_KEY)
    client.auth.set_session(user["token"], "")
    return client


def _service_sb(settings: Settings):
    return create_client(
        settings.SUPABASE_URL,
        settings.SUPABASE_SERVICE_KEY or settings.SUPABASE_ANON_KEY,
    )


async def _create_github_issue(
    feedback_id: str,
    feedback_type: str,
    description: str,
    page_url: str,
    browser_info: dict | None,
    console_errors: list[str] | None,
    github_token: str,
    repo: str,
) -> str | None:
    type_emoji = {"bug": "\U0001f41b", "feature": "\U0001f4a1", "ux": "\U0001f615"}
    type_labels = {"bug": ["bug"], "feature": ["enhancement"], "ux": ["ux"]}

    emoji = type_emoji.get(feedback_type, "\U0001f4dd")
    title = f"{emoji} [{feedback_type.upper()}] {description[:80]}"

    body_parts = [
        f"## Feedback\n{description}\n",
        f"**Page:** `{page_url}`",
        f"**Feedback ID:** `{feedback_id}`",
    ]

    if browser_info:
        vw = browser_info.get("viewport_width")
        vh = browser_info.get("viewport_height")
        body_parts.append(
            f"**Browser:** {browser_info.get('user_agent', 'unknown')}\n"
            f"**Viewport:** {vw}x{vh}"
        )

    if console_errors:
        errors_block = "\n".join(f"- {e}" for e in console_errors[:10])
        body_parts.append(f"## Console Errors\n```\n{errors_block}\n```")

    body_parts.append("\n---\n*Submitted via in-app feedback widget*")

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"https://api.github.com/repos/{repo}/issues",
            json={
                "title": title,
                "body": "\n\n".join(body_parts),
                "labels": type_labels.get(feedback_type, ["feedback"]),
            },
            headers={
                "Authorization": f"Bearer {github_token}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
            },
            timeout=10.0,
        )
        resp.raise_for_status()
        return resp.json()["html_url"]


@router.post("/feedback/upload-screenshot")
async def upload_screenshot(
    file: UploadFile,
    user: dict = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
):
    """Upload a screenshot to the feedback-screenshots bucket."""
    if file.content_type not in _ALLOWED_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File type {file.content_type} not allowed. Must be PNG, JPEG, or WebP.",
        )

    contents = await file.read()
    if len(contents) > _MAX_FILE_SIZE:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="File size exceeds 5 MB limit.",
        )

    ext = file.filename.rsplit(".", 1)[-1] if file.filename and "." in file.filename else "png"
    storage_path = f"{user['id']}/{uuid.uuid4()}.{ext}"

    sb = _service_sb(settings)
    sb.storage.from_("feedback-screenshots").upload(storage_path, contents)

    return {"storage_path": f"feedback-screenshots/{storage_path}"}


@router.post("/feedback", response_model=FeedbackResponse)
async def submit_feedback(
    body: FeedbackSubmitRequest,
    user: dict = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
):
    """Submit feedback and optionally create a GitHub issue."""
    sb = _sb(user, settings)

    # Build screenshot URL if a storage path was provided
    screenshot_url = None
    if body.screenshot_storage_path:
        screenshot_url = body.screenshot_storage_path

    row = {
        "user_id": user["id"],
        "type": body.type,
        "description": body.description,
        "page_url": body.page_url,
        "page_title": body.page_title,
        "screenshot_url": screenshot_url,
        "annotation_bounds": (
            body.annotation_bounds.model_dump() if body.annotation_bounds else None
        ),
        "browser_info": (
            body.browser_info.model_dump() if body.browser_info else None
        ),
        "console_errors": body.console_errors,
    }

    result = sb.table("feedback").insert(row).execute()
    feedback_id = result.data[0]["id"]

    # Create GitHub issue for actionable feedback types (not praise)
    github_issue_url = None
    if body.type in ("bug", "feature", "ux") and settings.GITHUB_TOKEN:
        try:
            github_issue_url = await _create_github_issue(
                feedback_id=feedback_id,
                feedback_type=body.type,
                description=body.description,
                page_url=body.page_url,
                browser_info=body.browser_info.model_dump() if body.browser_info else None,
                console_errors=body.console_errors,
                github_token=settings.GITHUB_TOKEN,
                repo=settings.GITHUB_FEEDBACK_REPO,
            )
        except Exception:
            logger.warning(
                "Failed to create GitHub issue for feedback %s",
                feedback_id,
                exc_info=True,
            )

        if github_issue_url:
            (
                sb.table("feedback")
                .update({"github_issue_url": github_issue_url})
                .eq("id", feedback_id)
                .execute()
            )

    return FeedbackResponse(
        id=feedback_id,
        github_issue_url=github_issue_url,
        message="Thank you for your feedback!",
    )
