"""Reset the demo user's data and re-seed with fresh content.

Run:
  cd packages/api
  SUPABASE_URL=<url> SUPABASE_SERVICE_KEY=<service-role-key> python scripts/reset_demo_data.py

Deleting courses cascades to syllabi, assessments, lectures, concepts, etc.
"""

from __future__ import annotations

import os

from supabase import create_client

from seed_demo_user import DEMO_EMAIL, seed

TABLES_TO_CLEAR = [
    "courses",       # cascades to syllabi, assessments, lectures, concepts, materials
    "learn_sessions",
    "tutor_sessions",
    "learning_events",
    "xp_events",
    "user_streaks",
    "user_levels",
    "user_badges",
    "quiz_attempts",
]


def reset() -> None:
    url = os.environ["SUPABASE_URL"]
    key = os.environ["SUPABASE_SERVICE_KEY"]
    sb = create_client(url, key)

    # 1. Find demo user
    users = sb.auth.admin.list_users()
    demo_user = next((u for u in users if u.email == DEMO_EMAIL), None)
    if not demo_user:
        print("Demo user not found — running seed instead.")
        seed()
        return

    user_id = demo_user.id
    print(f"Resetting demo user: {user_id}")

    # 2. Delete all user data from each table
    for table in TABLES_TO_CLEAR:
        try:
            sb.table(table).delete().eq("user_id", user_id).execute()
            print(f"  Cleared {table}")
        except Exception as e:
            # Table might not exist or have no user_id column — skip
            print(f"  Skipped {table}: {e}")

    # 3. Re-seed fresh data
    print("\nRe-seeding...")
    seed()


if __name__ == "__main__":
    reset()
