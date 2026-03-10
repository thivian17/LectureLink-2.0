"""Badge system — definitions, checking, and awarding."""

from __future__ import annotations

import logging

from .mastery import compute_mastery

logger = logging.getLogger(__name__)

BADGE_DEFINITIONS = {
    # Streak badges
    "streak_3": {
        "name": "3-Day Starter",
        "category": "streak",
        "description": "Study 3 days in a row",
        "icon": "flame",
    },
    "streak_7": {
        "name": "Week Warrior",
        "category": "streak",
        "description": "Study 7 days in a row",
        "icon": "flame",
    },
    "streak_14": {
        "name": "Fortnight Force",
        "category": "streak",
        "description": "Study 14 days in a row",
        "icon": "flame",
    },
    "streak_30": {
        "name": "Monthly Machine",
        "category": "streak",
        "description": "Study 30 days in a row",
        "icon": "flame",
    },
    "streak_60": {
        "name": "Semester Scholar",
        "category": "streak",
        "description": "Study 60 days in a row",
        "icon": "trophy",
    },
    "streak_100": {
        "name": "Unstoppable",
        "category": "streak",
        "description": "Study 100 days in a row",
        "icon": "trophy",
    },
    # Mastery badges
    "first_concept_mastered": {
        "name": "First Mastery",
        "category": "mastery",
        "description": "Master your first concept (80%+)",
        "icon": "star",
    },
    "concepts_5": {
        "name": "5 Concepts Mastered",
        "category": "mastery",
        "description": "Master 5 concepts",
        "icon": "star",
    },
    "course_expert": {
        "name": "Course Expert",
        "category": "mastery",
        "description": "Master all concepts in a course (80%+)",
        "icon": "crown",
    },
    "subject_scholar": {
        "name": "Subject Scholar",
        "category": "mastery",
        "description": "Master all concepts in a course (90%+)",
        "icon": "crown",
    },
    # Assessment badges
    "exam_ready": {
        "name": "Exam Ready",
        "category": "assessment",
        "description": "Reach 80%+ readiness before an exam",
        "icon": "shield",
    },
    "perfect_prep": {
        "name": "Perfect Prep",
        "category": "assessment",
        "description": "Reach 100% readiness before an exam",
        "icon": "shield",
    },
    "clutch_player": {
        "name": "Clutch Player",
        "category": "assessment",
        "description": "Go from <50% to >80% readiness in final week",
        "icon": "zap",
    },
    # Learning behavior badges
    "night_owl": {
        "name": "Night Owl",
        "category": "behavior",
        "description": "Complete 5 sessions after 10pm",
        "icon": "moon",
    },
    "early_bird": {
        "name": "Early Bird",
        "category": "behavior",
        "description": "Complete 5 sessions before 8am",
        "icon": "sun",
    },
    "weekend_warrior": {
        "name": "Weekend Warrior",
        "category": "behavior",
        "description": "Complete 4 weekend sessions",
        "icon": "calendar",
    },
    "flash_master": {
        "name": "Flash Master",
        "category": "behavior",
        "description": "Complete 100 flash reviews",
        "icon": "zap",
    },
    # Rare / surprise badges
    "perfect_quiz": {
        "name": "Perfect Quiz",
        "category": "rare",
        "description": "100% accuracy on a Power Quiz",
        "icon": "sparkle",
    },
    "zero_to_hero": {
        "name": "Zero to Hero",
        "category": "rare",
        "description": "Take a concept from 0% to 100% mastery",
        "icon": "rocket",
    },
    "misconception_slayer": {
        "name": "Misconception Slayer",
        "category": "rare",
        "description": "Resolve 3 misconceptions in Master Mode",
        "icon": "sword",
    },
}


async def _has_badge(supabase, user_id: str, badge_id: str) -> bool:
    """Check if user already has a badge."""
    result = (
        supabase.table("badges_earned")
        .select("id")
        .eq("user_id", user_id)
        .eq("badge_id", badge_id)
        .execute()
    )
    return bool(result.data)


async def _award_badge(
    supabase, user_id: str, badge_id: str, metadata: dict | None = None
) -> dict | None:
    """Award a badge if not already earned. Returns badge info or None."""
    if badge_id not in BADGE_DEFINITIONS:
        return None

    if await _has_badge(supabase, user_id, badge_id):
        return None

    badge_def = BADGE_DEFINITIONS[badge_id]
    supabase.table("badges_earned").insert({
        "user_id": user_id,
        "badge_id": badge_id,
        "metadata": metadata or {},
    }).execute()

    return {
        "badge_id": badge_id,
        "name": badge_def["name"],
        "description": badge_def["description"],
        "icon": badge_def["icon"],
        "category": badge_def["category"],
    }


async def check_and_award_badges(
    supabase, user_id: str, trigger: str, context: dict
) -> list[dict]:
    """Check badge conditions and award newly earned badges.

    Triggers:
      - session_complete: streak, behavior (time of day, weekend)
      - mastery_update: mastery badges
      - quiz_complete: perfect_quiz, flash_master
      - readiness_update: exam_ready, perfect_prep, clutch_player
      - misconception_resolved: misconception_slayer
    """
    awarded: list[dict] = []

    if trigger == "session_complete":
        awarded.extend(await _check_streak_badges(supabase, user_id, context))
        awarded.extend(await _check_behavior_badges(supabase, user_id, context))

    elif trigger == "mastery_update":
        awarded.extend(await _check_mastery_badges(supabase, user_id, context))

    elif trigger == "quiz_complete":
        awarded.extend(await _check_quiz_badges(supabase, user_id, context))

    elif trigger == "readiness_update":
        awarded.extend(await _check_readiness_badges(supabase, user_id, context))

    elif trigger == "misconception_resolved":
        awarded.extend(
            await _check_misconception_badges(supabase, user_id, context)
        )

    return [b for b in awarded if b is not None]


async def _check_streak_badges(
    supabase, user_id: str, context: dict
) -> list[dict | None]:
    """Check streak-based badges."""
    streak_count = context.get("streak_count", 0)
    results = []
    streak_badges = {3: "streak_3", 7: "streak_7", 14: "streak_14",
                     30: "streak_30", 60: "streak_60", 100: "streak_100"}
    for threshold, badge_id in streak_badges.items():
        if streak_count >= threshold:
            result = await _award_badge(
                supabase, user_id, badge_id,
                {"streak_count": streak_count},
            )
            if result:
                results.append(result)
    return results


async def _check_behavior_badges(
    supabase, user_id: str, context: dict
) -> list[dict | None]:
    """Check behavior-based badges (time of day, weekend)."""
    results = []
    session_hour = context.get("session_hour")
    is_weekend = context.get("is_weekend", False)

    # Night owl: session after 10pm
    if session_hour is not None and session_hour >= 22:
        night_sessions = (
            supabase.table("learn_sessions")
            .select("id")
            .eq("user_id", user_id)
            .eq("status", "completed")
            .execute()
        )
        # Count sessions in late hours (rough estimate from total)
        count = len(night_sessions.data or [])
        if count >= 5:
            r = await _award_badge(supabase, user_id, "night_owl")
            if r:
                results.append(r)

    # Early bird: session before 8am
    if session_hour is not None and session_hour < 8:
        early_sessions = (
            supabase.table("learn_sessions")
            .select("id")
            .eq("user_id", user_id)
            .eq("status", "completed")
            .execute()
        )
        count = len(early_sessions.data or [])
        if count >= 5:
            r = await _award_badge(supabase, user_id, "early_bird")
            if r:
                results.append(r)

    # Weekend warrior
    if is_weekend:
        weekend_sessions = (
            supabase.table("learn_sessions")
            .select("id")
            .eq("user_id", user_id)
            .eq("status", "completed")
            .execute()
        )
        count = len(weekend_sessions.data or [])
        if count >= 4:
            r = await _award_badge(supabase, user_id, "weekend_warrior")
            if r:
                results.append(r)

    # Flash master
    flash_count = context.get("flash_review_count", 0)
    if flash_count >= 100:
        r = await _award_badge(supabase, user_id, "flash_master")
        if r:
            results.append(r)

    return results


async def _check_mastery_badges(
    supabase, user_id: str, context: dict
) -> list[dict | None]:
    """Check mastery-based badges."""
    results = []
    mastery_after = context.get("mastery_after", 0)
    mastery_before = context.get("mastery_before", 0)
    course_id = context.get("course_id")

    # First concept mastered
    if mastery_after >= 0.8:
        r = await _award_badge(
            supabase, user_id, "first_concept_mastered",
            {"concept_id": context.get("concept_id")},
        )
        if r:
            results.append(r)

    # Zero to hero: 0% → 100%
    if mastery_before == 0 and mastery_after >= 1.0:
        r = await _award_badge(
            supabase, user_id, "zero_to_hero",
            {"concept_id": context.get("concept_id")},
        )
        if r:
            results.append(r)

    # 5 concepts mastered + course expert / subject scholar
    if course_id and mastery_after >= 0.8:
        try:
            mastery_result = supabase.rpc(
                "get_concept_mastery",
                {"p_course_id": course_id, "p_user_id": user_id},
            ).execute()
            mastery_data = mastery_result.data or []
            mastered_count = 0
            all_mastered_80 = True
            all_mastered_90 = True
            for m in mastery_data:
                attempts = m.get("total_attempts", 0)
                accuracy = m.get("accuracy", 0.0)
                recent = m.get("recent_accuracy", 0.0)
                mastery = compute_mastery(accuracy, recent, attempts)
                if mastery >= 0.8:
                    mastered_count += 1
                else:
                    all_mastered_80 = False
                if mastery < 0.9:
                    all_mastered_90 = False

            if mastered_count >= 5:
                r = await _award_badge(supabase, user_id, "concepts_5")
                if r:
                    results.append(r)

            if mastery_data and all_mastered_80:
                r = await _award_badge(
                    supabase, user_id, "course_expert",
                    {"course_id": course_id},
                )
                if r:
                    results.append(r)

            if mastery_data and all_mastered_90:
                r = await _award_badge(
                    supabase, user_id, "subject_scholar",
                    {"course_id": course_id},
                )
                if r:
                    results.append(r)
        except Exception:
            logger.warning("Failed to check mastery badges", exc_info=True)

    return results


async def _check_quiz_badges(
    supabase, user_id: str, context: dict
) -> list[dict | None]:
    """Check quiz-related badges."""
    results = []
    accuracy = context.get("accuracy", 0)
    total = context.get("total", 0)

    if total > 0 and accuracy == 1.0:
        r = await _award_badge(supabase, user_id, "perfect_quiz")
        if r:
            results.append(r)

    return results


async def _check_readiness_badges(
    supabase, user_id: str, context: dict
) -> list[dict | None]:
    """Check readiness-based badges."""
    results = []
    readiness = context.get("readiness", 0)
    readiness_7d_ago = context.get("readiness_7d_ago")

    if readiness >= 80:
        r = await _award_badge(
            supabase, user_id, "exam_ready",
            {"assessment_id": context.get("assessment_id")},
        )
        if r:
            results.append(r)

    if readiness >= 100:
        r = await _award_badge(
            supabase, user_id, "perfect_prep",
            {"assessment_id": context.get("assessment_id")},
        )
        if r:
            results.append(r)

    # Clutch player: <50% → >80% in final week
    if readiness_7d_ago is not None and readiness_7d_ago < 50 and readiness > 80:
        r = await _award_badge(
            supabase, user_id, "clutch_player",
            {"assessment_id": context.get("assessment_id")},
        )
        if r:
            results.append(r)

    return results


async def _check_misconception_badges(
    supabase, user_id: str, context: dict
) -> list[dict | None]:
    """Check misconception-related badges."""
    results = []
    resolved_count = context.get("resolved_count", 0)
    if resolved_count >= 3:
        r = await _award_badge(supabase, user_id, "misconception_slayer")
        if r:
            results.append(r)
    return results


async def get_user_badges(supabase, user_id: str) -> dict:
    """Get all earned badges + all available badges with progress."""
    earned_result = (
        supabase.table("badges_earned")
        .select("badge_id, earned_at, metadata")
        .eq("user_id", user_id)
        .order("earned_at", desc=True)
        .execute()
    )
    earned_ids = {b["badge_id"] for b in (earned_result.data or [])}

    earned = []
    for b in earned_result.data or []:
        badge_def = BADGE_DEFINITIONS.get(b["badge_id"], {})
        earned.append({
            "badge_id": b["badge_id"],
            "name": badge_def.get("name", b["badge_id"]),
            "description": badge_def.get("description", ""),
            "icon": badge_def.get("icon", "star"),
            "category": badge_def.get("category", "other"),
            "earned_at": b["earned_at"],
        })

    available = []
    for badge_id, badge_def in BADGE_DEFINITIONS.items():
        if badge_id not in earned_ids:
            available.append({
                "badge_id": badge_id,
                "name": badge_def["name"],
                "description": badge_def["description"],
                "icon": badge_def["icon"],
                "category": badge_def["category"],
                "progress": 0,
                "target": 1,
            })

    return {
        "earned": earned,
        "available": available,
        "total_earned": len(earned),
        "total_available": len(BADGE_DEFINITIONS),
    }


async def get_badge_progress(supabase, user_id: str, badge_id: str) -> dict:
    """Get progress toward a specific badge."""
    if badge_id not in BADGE_DEFINITIONS:
        return {"current": 0, "target": 1, "percent": 0}

    # Check if already earned
    if await _has_badge(supabase, user_id, badge_id):
        return {"current": 1, "target": 1, "percent": 100}

    # For streak badges, get current streak
    if badge_id.startswith("streak_"):
        target = int(badge_id.split("_")[1])
        streak_result = (
            supabase.table("user_streaks")
            .select("current_streak")
            .eq("user_id", user_id)
            .execute()
        )
        current = streak_result.data[0]["current_streak"] if streak_result.data else 0
        return {
            "current": min(current, target),
            "target": target,
            "percent": round(min(current / target * 100, 100), 1),
        }

    return {"current": 0, "target": 1, "percent": 0}
