"""Seed a demo user with pre-populated data for the landing page.

Run:
  cd packages/api
  SUPABASE_URL=<url> SUPABASE_SERVICE_KEY=<service-role-key> python scripts/seed_demo_user.py
"""

from __future__ import annotations

import os
from datetime import date, timedelta

from supabase import create_client

DEMO_EMAIL = "demo@lecturelink.ca"
DEMO_PASSWORD = "demodemo123"
DEMO_FIRST = "Alex"
DEMO_LAST = "Demo"


def seed() -> None:
    url = os.environ["SUPABASE_URL"]
    key = os.environ["SUPABASE_SERVICE_KEY"]
    sb = create_client(url, key)

    # 1. Create demo user via admin auth API (or skip if exists)
    try:
        user_resp = sb.auth.admin.create_user(
            {
                "email": DEMO_EMAIL,
                "password": DEMO_PASSWORD,
                "email_confirm": True,
                "user_metadata": {
                    "first_name": DEMO_FIRST,
                    "last_name": DEMO_LAST,
                },
            }
        )
        user_id = user_resp.user.id
        print(f"Created demo user: {user_id}")
    except Exception as e:
        if "already been registered" in str(e).lower() or "already exists" in str(
            e
        ).lower():
            users = sb.auth.admin.list_users()
            user_id = next(u.id for u in users if u.email == DEMO_EMAIL)
            print(f"Demo user already exists: {user_id}")
        else:
            raise

    # 2. Create a demo course
    today = date.today()
    course_data = {
        "user_id": user_id,
        "name": "CS 301 \u2014 Data Structures & Algorithms",
        "code": "CS301",
        "semester_start": today.replace(month=1, day=6).isoformat(),
        "semester_end": today.replace(month=4, day=30).isoformat(),
        "meeting_days": ["Monday", "Wednesday", "Friday"],
        "meeting_time": "10:00",
        "target_grade": 0.9,
        "onboarding_completed_at": today.isoformat(),
    }

    existing = (
        sb.table("courses")
        .select("id")
        .eq("user_id", user_id)
        .eq("code", "CS301")
        .execute()
    )
    if existing.data:
        course_id = existing.data[0]["id"]
        print(f"Demo course already exists: {course_id}")
    else:
        result = sb.table("courses").insert(course_data).execute()
        course_id = result.data[0]["id"]
        print(f"Created demo course: {course_id}")

    # 3. Create gamification data (streak, XP, level)
    sb.table("user_streaks").upsert(
        {
            "user_id": user_id,
            "current_streak": 12,
            "longest_streak": 18,
            "last_session_date": today.isoformat(),
            "streak_freezes_available": 2,
        },
        on_conflict="user_id",
    ).execute()

    sb.table("user_levels").upsert(
        {
            "user_id": user_id,
            "total_xp": 2450,
            "current_level": 7,
        },
        on_conflict="user_id",
    ).execute()

    print(f"\nDemo account ready!")
    print(f"  Email:    {DEMO_EMAIL}")
    print(f"  Password: {DEMO_PASSWORD}")
    print(f"  Course:   CS 301 ({course_id})")


if __name__ == "__main__":
    seed()
