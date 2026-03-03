"""Gamification engine — XP awarding, streaks, levels, and combos."""

from __future__ import annotations

import logging
from datetime import UTC, date, datetime, timedelta

from lecturelink_api.services.badges import BADGE_DEFINITIONS

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# XP award amounts by source
# ---------------------------------------------------------------------------
XP_AMOUNTS = {
    # Flash Review (recognition-based MCQ)
    "flash_review_correct": 5,
    "flash_review_incorrect": 2,
    # Concept Brief gut-check
    "gut_check_correct": 15,
    # Power Quiz
    "quiz_correct": 10,
    "quiz_combo_bonus": 10,
    # Mastery milestones
    "mastery_increase": 50,
    "concept_mastered": 100,
    "mastery_breakthrough": 150,
    # Session
    "session_complete": 25,
    # Master Mode
    "misconception_resolved": 75,
    # Bonus
    "perfect_quiz": 100,
}

# Combo thresholds: {consecutive_correct: multiplier}
COMBO_THRESHOLDS = {3: 2, 5: 3, 8: 4}

# Streak milestones
STREAK_MILESTONES = [3, 7, 14, 30, 60, 100]


def get_level_thresholds(max_level: int = 50) -> list[int]:
    """Generate Fibonacci-style XP thresholds."""
    thresholds = [0, 100]
    increments = [100, 200]
    for _ in range(2, max_level):
        next_inc = increments[-1] + increments[-2]
        increments.append(next_inc)
        thresholds.append(thresholds[-1] + next_inc)
    return thresholds


LEVEL_THRESHOLDS = get_level_thresholds()


# ---------------------------------------------------------------------------
# Pure computation helpers
# ---------------------------------------------------------------------------


def get_combo_multiplier(consecutive_correct: int) -> int:
    """Return combo multiplier based on consecutive correct answers."""
    multiplier = 1
    for threshold, mult in sorted(COMBO_THRESHOLDS.items()):
        if consecutive_correct >= threshold:
            multiplier = mult
    return multiplier


def compute_level(total_xp: int) -> tuple[int, int, int]:
    """Compute (level, xp_into_current_level, xp_needed_for_next).

    Uses LEVEL_THRESHOLDS (Fibonacci-style scaling).
    """
    level = 1
    for i in range(1, len(LEVEL_THRESHOLDS)):
        if total_xp >= LEVEL_THRESHOLDS[i]:
            level = i + 1
        else:
            break

    current_threshold = LEVEL_THRESHOLDS[level - 1]
    xp_into_level = total_xp - current_threshold

    if level < len(LEVEL_THRESHOLDS):
        xp_needed = LEVEL_THRESHOLDS[level] - current_threshold
    else:
        xp_needed = LEVEL_THRESHOLDS[-1] - LEVEL_THRESHOLDS[-2]

    return level, xp_into_level, xp_needed


# ---------------------------------------------------------------------------
# Async DB operations
# ---------------------------------------------------------------------------


async def award_xp(
    supabase,
    user_id: str,
    source: str,
    course_id: str | None = None,
    session_id: str | None = None,
    concept_id: str | None = None,
    metadata: dict | None = None,
    combo_multiplier: int = 1,
) -> dict:
    """Award XP and handle level-ups.

    Returns ``{amount, total_xp, level, leveled_up}``.
    """
    metadata = metadata or {}
    base_amount = XP_AMOUNTS.get(source, 0)

    # Anti-gaming: cap XP for mastered content
    if source == "flash_review_correct" and metadata.get("mastery", 0) > 0.8:
        base_amount = min(base_amount, 2)

    # Anti-gaming: disable combo for speed-run answers
    effective_multiplier = combo_multiplier
    if metadata.get("response_time_ms", 999999) < 3000:
        effective_multiplier = 1

    amount = base_amount * effective_multiplier

    # 1. Insert XP event
    event_data = {
        "user_id": user_id,
        "amount": amount,
        "source": source,
        "metadata": {**metadata, "combo_multiplier": effective_multiplier},
    }
    if course_id:
        event_data["course_id"] = course_id
    if session_id:
        event_data["session_id"] = session_id
    if concept_id:
        event_data["concept_id"] = concept_id

    supabase.table("xp_events").insert(event_data).execute()

    # 2. Get or create user_levels row
    levels_result = (
        supabase.table("user_levels")
        .select("*")
        .eq("user_id", user_id)
        .execute()
    )
    if levels_result.data:
        current_row = levels_result.data[0]
        new_total = current_row["total_xp"] + amount
    else:
        new_total = amount

    # 3. Compute new level
    new_level, xp_into, xp_needed = compute_level(new_total)
    old_level = levels_result.data[0]["current_level"] if levels_result.data else 1
    leveled_up = new_level > old_level

    # 4. Upsert user_levels
    supabase.table("user_levels").upsert(
        {
            "user_id": user_id,
            "total_xp": new_total,
            "current_level": new_level,
            "xp_to_next_level": xp_needed - xp_into,
            "updated_at": datetime.now(UTC).isoformat(),
        },
        on_conflict="user_id",
    ).execute()

    return {
        "amount": amount,
        "total_xp": new_total,
        "level": new_level,
        "leveled_up": leveled_up,
    }


async def update_streak(supabase, user_id: str) -> dict:
    """Update user's study streak after completing a session.

    Returns ``{current_streak, longest_streak, is_new_streak, streak_milestone}``.
    """
    today = date.today()
    now = datetime.now(UTC)

    # Get or create streak row
    result = (
        supabase.table("user_streaks")
        .select("*")
        .eq("user_id", user_id)
        .execute()
    )

    if not result.data:
        # First session ever
        supabase.table("user_streaks").insert({
            "user_id": user_id,
            "current_streak": 1,
            "longest_streak": 1,
            "last_session_date": today.isoformat(),
            "updated_at": now.isoformat(),
        }).execute()
        milestone = 1 if 1 in STREAK_MILESTONES else None
        return {
            "current_streak": 1,
            "longest_streak": 1,
            "is_new_streak": True,
            "streak_milestone": milestone,
        }

    row = result.data[0]
    current_streak = row["current_streak"]
    longest_streak = row["longest_streak"]
    last_date = row["last_session_date"]
    is_new_streak = False
    streak_milestone = None

    # Parse last_session_date
    if last_date:
        if isinstance(last_date, str):
            last_date = date.fromisoformat(last_date)
        days_since = (today - last_date).days
    else:
        days_since = 999

    if days_since == 0:
        # Already studied today — no change
        pass
    elif days_since == 1:
        # Consecutive day
        current_streak += 1
        is_new_streak = True
    elif days_since == 2:
        # Missed one day — check freeze
        freezes = row.get("streak_freezes_available", 0)
        if freezes > 0:
            supabase.table("user_streaks").update({
                "streak_freezes_available": freezes - 1,
                "streak_freezes_used": row.get("streak_freezes_used", 0) + 1,
            }).eq("user_id", user_id).execute()
            current_streak += 1
            is_new_streak = True
        else:
            current_streak = 1
            is_new_streak = True
    else:
        # Missed 2+ days — reset
        current_streak = 1
        is_new_streak = True

    if current_streak > longest_streak:
        longest_streak = current_streak

    # Check milestone
    for m in STREAK_MILESTONES:
        if current_streak == m:
            streak_milestone = m
            break

    # Weekly freeze reset
    freeze_reset = row.get("freeze_last_reset_at")
    update_data: dict = {
        "current_streak": current_streak,
        "longest_streak": longest_streak,
        "last_session_date": today.isoformat(),
        "updated_at": now.isoformat(),
    }
    if freeze_reset:
        if isinstance(freeze_reset, str):
            freeze_reset = datetime.fromisoformat(freeze_reset)
        if (now - freeze_reset).days >= 7:
            update_data["streak_freezes_available"] = 1
            update_data["freeze_last_reset_at"] = now.isoformat()

    supabase.table("user_streaks").update(update_data).eq(
        "user_id", user_id
    ).execute()

    return {
        "current_streak": current_streak,
        "longest_streak": longest_streak,
        "is_new_streak": is_new_streak,
        "streak_milestone": streak_milestone,
    }


async def use_streak_freeze(supabase, user_id: str) -> dict:
    """Use a streak freeze to prevent streak reset.

    Returns ``{success, freezes_remaining}``.
    """
    result = (
        supabase.table("user_streaks")
        .select("*")
        .eq("user_id", user_id)
        .execute()
    )
    if not result.data:
        return {"success": False, "freezes_remaining": 0}

    row = result.data[0]
    freezes = row.get("streak_freezes_available", 0)
    if freezes <= 0:
        return {"success": False, "freezes_remaining": 0}

    supabase.table("user_streaks").update({
        "streak_freezes_available": freezes - 1,
        "streak_freezes_used": row.get("streak_freezes_used", 0) + 1,
        "updated_at": datetime.now(UTC).isoformat(),
    }).eq("user_id", user_id).execute()

    return {"success": True, "freezes_remaining": freezes - 1}


async def get_user_gamification(supabase, user_id: str) -> dict:
    """Get complete gamification state for home screen rendering."""
    today = date.today()

    # Streak
    streak_result = (
        supabase.table("user_streaks")
        .select("*")
        .eq("user_id", user_id)
        .execute()
    )
    streak_row = streak_result.data[0] if streak_result.data else None

    studied_today = False
    if streak_row and streak_row.get("last_session_date"):
        last = streak_row["last_session_date"]
        if isinstance(last, str):
            last = date.fromisoformat(last)
        studied_today = last == today

    streak = {
        "current": streak_row["current_streak"] if streak_row else 0,
        "longest": streak_row["longest_streak"] if streak_row else 0,
        "studied_today": studied_today,
        "freeze_available": (streak_row.get("streak_freezes_available", 0) > 0)
        if streak_row
        else False,
    }

    # Level
    level_result = (
        supabase.table("user_levels")
        .select("*")
        .eq("user_id", user_id)
        .execute()
    )
    level_row = level_result.data[0] if level_result.data else None

    if level_row:
        total_xp = level_row["total_xp"]
        current_level, xp_into, xp_needed = compute_level(total_xp)
        progress = (xp_into / xp_needed * 100) if xp_needed > 0 else 100.0
    else:
        total_xp = 0
        current_level = 1
        xp_needed = 100
        xp_into = 0
        progress = 0.0

    level = {
        "current": current_level,
        "total_xp": total_xp,
        "xp_to_next": xp_needed - xp_into,
        "progress_percent": round(progress, 1),
    }

    # Today's XP
    start_of_day = datetime(today.year, today.month, today.day, tzinfo=UTC)
    xp_today_result = (
        supabase.table("xp_events")
        .select("amount")
        .eq("user_id", user_id)
        .gte("created_at", start_of_day.isoformat())
        .execute()
    )
    today_xp = sum(e["amount"] for e in (xp_today_result.data or []))

    # Badges
    badges_result = (
        supabase.table("badges_earned")
        .select("badge_id, earned_at")
        .eq("user_id", user_id)
        .order("earned_at", desc=True)
        .limit(3)
        .execute()
    )
    badges_count_result = (
        supabase.table("badges_earned")
        .select("id")
        .eq("user_id", user_id)
        .execute()
    )

    # Enrich badge records with BADGE_DEFINITIONS data
    enriched_badges = []
    for b in (badges_result.data or []):
        defn = BADGE_DEFINITIONS.get(b["badge_id"], {})
        enriched_badges.append({
            "badge_id": b["badge_id"],
            "name": defn.get("name", b["badge_id"]),
            "description": defn.get("description", ""),
            "icon": defn.get("icon", "trophy"),
            "category": defn.get("category", "general"),
            "earned_at": b.get("earned_at"),
        })

    return {
        "streak": streak,
        "level": level,
        "today_xp": today_xp,
        "badges_count": len(badges_count_result.data or []),
        "recent_badges": enriched_badges,
    }


async def get_xp_history(supabase, user_id: str, days: int = 7) -> list[dict]:
    """Get XP earned per day for the last N days."""
    cutoff = datetime.now(UTC) - timedelta(days=days)
    result = (
        supabase.table("xp_events")
        .select("amount, created_at")
        .eq("user_id", user_id)
        .gte("created_at", cutoff.isoformat())
        .order("created_at", desc=False)
        .execute()
    )

    # Aggregate by day
    daily: dict[str, int] = {}
    for event in result.data or []:
        day = event["created_at"][:10]  # YYYY-MM-DD
        daily[day] = daily.get(day, 0) + event["amount"]

    # Fill in missing days
    history = []
    for i in range(days):
        d = (datetime.now(UTC) - timedelta(days=days - 1 - i)).strftime(
            "%Y-%m-%d"
        )
        history.append({"date": d, "xp": daily.get(d, 0)})

    return history
