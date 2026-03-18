"""
Email notification service using Resend.

Implements:
- Daily study digest (sent by daily-refresh job)
- Assessment deadline reminder (sent 48h before due_date)

All functions are no-ops if RESEND_API_KEY is not configured.
Respects user opt-out via user_onboarding.email_notifications_enabled.
"""
from __future__ import annotations

import logging
from datetime import date, datetime, timedelta, timezone

logger = logging.getLogger(__name__)

DIGEST_FROM = "LectureLink <noreply@lecturelink.ca>"
REMINDER_FROM = "LectureLink <reminders@lecturelink.ca>"


def _get_resend_client():
    """Return a configured Resend client or None if not configured."""
    try:
        from lecturelink_api.config.secrets import get_secret

        api_key = get_secret("RESEND_API_KEY")
        if not api_key:
            return None
        import resend

        resend.api_key = api_key
        return resend
    except Exception as e:
        logger.debug("Resend not configured: %s", e)
        return None


def _is_notifications_enabled(supabase, user_id: str) -> bool:
    """Check if user has email notifications enabled (default: True)."""
    try:
        result = (
            supabase.table("user_onboarding")
            .select("email_notifications_enabled")
            .eq("user_id", user_id)
            .single()
            .execute()
        )
        if result.data:
            return result.data.get("email_notifications_enabled", True)
    except Exception:
        pass
    return True


async def send_daily_digest(
    supabase,
    user_id: str,
    user_email: str,
    user_name: str,
) -> bool:
    """
    Send the daily study digest email for a user.

    Includes:
    - Upcoming assessments in the next 72 hours
    - Top 3 deterministic study action recommendations
    - Current streak

    Returns True if sent, False if skipped or failed.
    """
    resend = _get_resend_client()
    if not resend:
        return False
    if not _is_notifications_enabled(supabase, user_id):
        logger.debug("Skipping digest for user %s (opted out)", user_id)
        return False

    today = date.today()
    in_72h = today + timedelta(days=3)

    try:
        # 1. Upcoming assessments
        assessments_result = (
            supabase.table("assessments")
            .select("title, type, due_date, weight_percent, course_id")
            .eq("user_id", user_id)
            .gte("due_date", today.isoformat())
            .lte("due_date", in_72h.isoformat())
            .order("due_date")
            .limit(5)
            .execute()
        )
        upcoming = assessments_result.data or []

        # 2. Streak info
        streak = 0
        try:
            streak_result = (
                supabase.table("user_streaks")
                .select("current_streak")
                .eq("user_id", user_id)
                .single()
                .execute()
            )
            streak = streak_result.data.get("current_streak", 0) if streak_result.data else 0
        except Exception:
            pass

        # 3. Top study actions (deterministic, fast)
        from lecturelink_api.services.dashboard_actions import get_best_next_actions

        actions_resp = await get_best_next_actions(supabase, user_id, limit=3)
        actions = actions_resp.actions

        # Build HTML email
        html = _build_digest_html(
            name=user_name,
            upcoming=upcoming,
            actions=actions,
            streak=streak,
        )

        resend.Emails.send({
            "from": DIGEST_FROM,
            "to": user_email,
            "subject": f"Your study plan for today - {today.strftime('%B %d')}",
            "html": html,
        })

        # Update last sent time
        supabase.table("user_onboarding").upsert(
            {
                "user_id": user_id,
                "digest_last_sent_at": datetime.now(timezone.utc).isoformat(),
            },
            on_conflict="user_id",
        ).execute()

        logger.info("Sent daily digest to user %s", user_id)
        return True

    except Exception as e:
        logger.error("Failed to send digest to user %s: %s", user_id, e)
        return False


async def send_assessment_reminder(
    supabase,
    user_id: str,
    user_email: str,
    user_name: str,
    assessment: dict,
) -> bool:
    """
    Send a 48-hour assessment deadline reminder.

    Includes:
    - Assessment name, weight, due date
    - Readiness score from readiness.py
    - Direct link to course tutor page

    Returns True if sent, False if already sent or failed.
    """
    resend = _get_resend_client()
    if not resend:
        return False
    if not _is_notifications_enabled(supabase, user_id):
        return False

    assessment_id = assessment["id"]

    # Check if reminder already sent for this assessment
    try:
        existing = (
            supabase.table("assessment_reminder_log")
            .select("id")
            .eq("user_id", user_id)
            .eq("assessment_id", assessment_id)
            .eq("reminder_type", "48h")
            .execute()
        )
        if existing.data:
            logger.debug("48h reminder already sent for assessment %s", assessment_id)
            return False
    except Exception:
        pass

    try:
        # Get readiness score (best-effort)
        readiness_score = None
        try:
            from lecturelink_api.services.readiness import get_assessment_readiness

            readiness_data = await get_assessment_readiness(
                supabase, user_id, assessment_id
            )
            readiness_score = readiness_data.get("readiness_score")
        except Exception:
            pass

        due_date = assessment.get("due_date", "")
        course_id = assessment.get("course_id", "")
        weight = assessment.get("weight_percent", 0)
        title = assessment.get("title", "Assessment")

        html = _build_reminder_html(
            name=user_name,
            assessment_title=title,
            due_date=due_date,
            weight=weight,
            readiness_score=readiness_score,
            course_id=course_id,
        )

        resend.Emails.send({
            "from": REMINDER_FROM,
            "to": user_email,
            "subject": f"{title} is due in 48 hours ({weight:.0f}% of grade)",
            "html": html,
        })

        # Log that reminder was sent
        supabase.table("assessment_reminder_log").insert({
            "user_id": user_id,
            "assessment_id": assessment_id,
            "reminder_type": "48h",
        }).execute()

        logger.info("Sent 48h reminder for assessment %s to user %s", assessment_id, user_id)
        return True

    except Exception as e:
        logger.error("Failed to send reminder for assessment %s: %s", assessment_id, e)
        return False


def _build_digest_html(
    name: str,
    upcoming: list,
    actions: list,
    streak: int,
) -> str:
    """Build a clean HTML digest email."""
    upcoming_html = ""
    for a in upcoming:
        due = a.get("due_date", "")
        weight = a.get("weight_percent", 0)
        upcoming_html += (
            f"<li><strong>{a.get('title')}</strong> "
            f"&mdash; due {due} ({weight:.0f}%)</li>"
        )

    actions_html = ""
    for action in actions[:3]:
        desc = action.description if hasattr(action, "description") else str(action)
        actions_html += f"<li>{desc}</li>"

    streak_line = (
        f'<p><strong>{streak}-day streak</strong> &mdash; keep it going!</p>'
        if streak >= 2
        else ""
    )

    upcoming_section = (
        f"<h3>Due in the next 72 hours</h3><ul>{upcoming_html}</ul>"
        if upcoming
        else "<p>No assessments due in the next 72 hours.</p>"
    )

    actions_section = (
        f"<h3>Today's study priorities</h3><ul>{actions_html}</ul>" if actions else ""
    )

    return f"""\
<html><body style="font-family: sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
<h2 style="color: #2563EB;">Good morning, {name}!</h2>
{streak_line}
{upcoming_section}
{actions_section}
<hr>
<p style="font-size: 12px; color: #888;">
    <a href="https://lecturelink.ca/dashboard">Open LectureLink</a> &middot;
    <a href="https://lecturelink.ca/dashboard/settings">Unsubscribe</a>
</p>
</body></html>"""


def _build_reminder_html(
    name: str,
    assessment_title: str,
    due_date: str,
    weight: float,
    readiness_score: float | None,
    course_id: str,
) -> str:
    """Build a clean HTML reminder email."""
    readiness_html = ""
    if readiness_score is not None:
        # readiness_score is already 0-100 from readiness.py
        pct = int(readiness_score)
        color = "#16a34a" if pct >= 70 else "#d97706" if pct >= 40 else "#dc2626"
        readiness_html = (
            f'<p>Readiness score: '
            f'<strong style="color: {color};">{pct}%</strong></p>'
        )

    return f"""\
<html><body style="font-family: sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
<h2 style="color: #2563EB;">Assessment reminder</h2>
<p>Hi {name}, <strong>{assessment_title}</strong> is due in 48 hours.</p>
<ul>
    <li>Due: <strong>{due_date}</strong></li>
    <li>Grade weight: <strong>{weight:.0f}%</strong></li>
</ul>
{readiness_html}
<p>
    <a href="https://lecturelink.ca/dashboard/courses/{course_id}"
       style="background: #2563EB; color: white; padding: 10px 20px;
              text-decoration: none; border-radius: 6px;">
        Study now
    </a>
</p>
<hr>
<p style="font-size: 12px; color: #888;">
    <a href="https://lecturelink.ca/dashboard/settings">Unsubscribe from reminders</a>
</p>
</body></html>"""
