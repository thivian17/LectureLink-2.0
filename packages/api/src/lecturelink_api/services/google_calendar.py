"""Google Calendar sync service."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

logger = logging.getLogger(__name__)

CALENDAR_SCOPES = ["https://www.googleapis.com/auth/calendar.events"]


def get_user_credentials(
    sb_service,
    user_id: str,
    client_id: str,
    client_secret: str,
) -> Credentials | None:
    """Load Google credentials from the database, refreshing if expired."""
    result = (
        sb_service.table("user_google_tokens")
        .select("*")
        .eq("user_id", user_id)
        .maybe_single()
        .execute()
    )
    row = result.data
    if not row:
        return None

    creds = Credentials(
        token=row["access_token"],
        refresh_token=row.get("refresh_token"),
        token_uri="https://oauth2.googleapis.com/token",
        client_id=client_id,
        client_secret=client_secret,
        scopes=CALENDAR_SCOPES,
    )

    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
        # Persist the refreshed token
        sb_service.table("user_google_tokens").update(
            {
                "access_token": creds.token,
                "token_expires_at": creds.expiry.isoformat() if creds.expiry else None,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }
        ).eq("user_id", user_id).execute()

    return creds


def build_calendar_event(assessment: dict, course: dict) -> dict:
    """Build a Google Calendar event payload for an assessment."""
    title = f"{assessment['title']} — {course.get('code') or course['name']}"
    due = assessment["due_date"][:10]  # YYYY-MM-DD

    weight = assessment.get("weight_percent")
    description_parts = [f"Course: {course['name']}"]
    if weight:
        description_parts.append(f"Weight: {weight}%")
    if assessment.get("type"):
        description_parts.append(f"Type: {assessment['type']}")

    return {
        "summary": title,
        "description": "\n".join(description_parts),
        "start": {"date": due},
        "end": {"date": due},
        "reminders": {
            "useDefault": False,
            "overrides": [
                {"method": "popup", "minutes": 1440},  # 1 day before
                {"method": "popup", "minutes": 60},     # 1 hour before
            ],
        },
    }


def create_calendar_event(creds: Credentials, assessment: dict, course: dict) -> str:
    """Create a Google Calendar event and return the event ID."""
    service = build("calendar", "v3", credentials=creds, cache_discovery=False)
    event_body = build_calendar_event(assessment, course)
    event = service.events().insert(calendarId="primary", body=event_body).execute()
    return event["id"]


def update_calendar_event(
    creds: Credentials, event_id: str, assessment: dict, course: dict
) -> None:
    """Update an existing Google Calendar event."""
    service = build("calendar", "v3", credentials=creds, cache_discovery=False)
    event_body = build_calendar_event(assessment, course)
    service.events().update(
        calendarId="primary", eventId=event_id, body=event_body
    ).execute()


def delete_calendar_event(creds: Credentials, event_id: str) -> None:
    """Delete a Google Calendar event."""
    service = build("calendar", "v3", credentials=creds, cache_discovery=False)
    service.events().delete(calendarId="primary", eventId=event_id).execute()


async def sync_all_assessments(
    sb_service,
    sb_user,
    user_id: str,
    client_id: str,
    client_secret: str,
) -> dict:
    """Full sync of all assessments with due dates to Google Calendar.

    Returns counts: {created, updated, deleted, errors}.
    """
    creds = await asyncio.to_thread(
        get_user_credentials, sb_service, user_id, client_id, client_secret
    )
    if not creds:
        raise ValueError("Google account not connected")

    # Get all courses for this user
    courses_result = (
        sb_user.table("courses").select("*").execute()
    )
    courses_by_id = {c["id"]: c for c in (courses_result.data or [])}

    # Get all assessments with due dates for these courses
    course_ids = list(courses_by_id.keys())
    if not course_ids:
        return {"created": 0, "updated": 0, "deleted": 0, "errors": 0}

    assessments_result = (
        sb_user.table("assessments")
        .select("*")
        .in_("course_id", course_ids)
        .not_.is_("due_date", "null")
        .execute()
    )

    counts = {"created": 0, "updated": 0, "deleted": 0, "errors": 0}

    for assessment in assessments_result.data or []:
        course = courses_by_id.get(assessment["course_id"])
        if not course:
            continue

        event_id = assessment.get("google_calendar_event_id")
        try:
            if event_id:
                # Update existing event
                await asyncio.to_thread(
                    update_calendar_event, creds, event_id, assessment, course
                )
                counts["updated"] += 1
            else:
                # Create new event
                new_event_id = await asyncio.to_thread(
                    create_calendar_event, creds, assessment, course
                )
                # Store event ID on the assessment
                sb_user.table("assessments").update(
                    {"google_calendar_event_id": new_event_id}
                ).eq("id", assessment["id"]).execute()
                counts["created"] += 1
        except Exception:
            logger.exception(
                "Failed to sync assessment %s to Google Calendar",
                assessment["id"],
            )
            counts["errors"] += 1

    return counts
