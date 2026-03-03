"""Tests for the gamification service."""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest


def _mock_execute(data):
    resp = MagicMock()
    resp.data = data
    resp.count = 0
    return resp


def _mock_chain(final_data):
    chain = MagicMock()
    chain.execute.return_value = _mock_execute(final_data)
    for method in ("select", "eq", "in_", "order", "limit", "gte", "lte",
                    "single", "insert", "upsert", "update"):
        getattr(chain, method).return_value = chain
    return chain


def _make_sb(table_responses: dict | None = None):
    """Create a mock supabase client with table() responses."""
    sb = MagicMock()
    table_responses = table_responses or {}

    def table_side_effect(name):
        if name in table_responses:
            return _mock_chain(table_responses[name])
        return _mock_chain([])

    sb.table.side_effect = table_side_effect
    return sb


# ===========================================================================
# Pure function tests
# ===========================================================================


class TestComputeLevel:
    def test_level_1_at_zero_xp(self):
        from lecturelink_api.services.gamification import compute_level
        level, xp_into, xp_needed = compute_level(0)
        assert level == 1
        assert xp_into == 0
        assert xp_needed == 100

    def test_level_2_at_100_xp(self):
        from lecturelink_api.services.gamification import compute_level
        level, xp_into, xp_needed = compute_level(100)
        assert level == 2
        assert xp_into == 0

    def test_level_2_at_150_xp(self):
        from lecturelink_api.services.gamification import compute_level
        level, xp_into, xp_needed = compute_level(150)
        assert level == 2
        assert xp_into == 50

    def test_level_3_at_400_xp(self):
        from lecturelink_api.services.gamification import compute_level
        level, _, _ = compute_level(400)
        assert level == 3

    def test_level_4_at_900_xp(self):
        from lecturelink_api.services.gamification import compute_level
        level, _, _ = compute_level(900)
        assert level == 4


class TestGetComboMultiplier:
    def test_no_combo_below_3(self):
        from lecturelink_api.services.gamification import get_combo_multiplier
        assert get_combo_multiplier(0) == 1
        assert get_combo_multiplier(1) == 1
        assert get_combo_multiplier(2) == 1

    def test_2x_at_3(self):
        from lecturelink_api.services.gamification import get_combo_multiplier
        assert get_combo_multiplier(3) == 2
        assert get_combo_multiplier(4) == 2

    def test_3x_at_5(self):
        from lecturelink_api.services.gamification import get_combo_multiplier
        assert get_combo_multiplier(5) == 3
        assert get_combo_multiplier(7) == 3

    def test_4x_at_8(self):
        from lecturelink_api.services.gamification import get_combo_multiplier
        assert get_combo_multiplier(8) == 4
        assert get_combo_multiplier(100) == 4


class TestLevelThresholds:
    def test_first_thresholds(self):
        from lecturelink_api.services.gamification import LEVEL_THRESHOLDS
        assert LEVEL_THRESHOLDS[0] == 0
        assert LEVEL_THRESHOLDS[1] == 100
        assert LEVEL_THRESHOLDS[2] == 400

    def test_fibonacci_scaling(self):
        from lecturelink_api.services.gamification import LEVEL_THRESHOLDS
        # Each increment should be sum of previous two increments
        for i in range(4, len(LEVEL_THRESHOLDS)):
            inc = LEVEL_THRESHOLDS[i] - LEVEL_THRESHOLDS[i - 1]
            prev_inc = LEVEL_THRESHOLDS[i - 1] - LEVEL_THRESHOLDS[i - 2]
            prev_prev_inc = LEVEL_THRESHOLDS[i - 2] - LEVEL_THRESHOLDS[i - 3]
            assert inc == prev_inc + prev_prev_inc

    def test_50_levels_generated(self):
        from lecturelink_api.services.gamification import LEVEL_THRESHOLDS
        assert len(LEVEL_THRESHOLDS) == 50


class TestXPAmounts:
    def test_all_sources_positive(self):
        from lecturelink_api.services.gamification import XP_AMOUNTS
        for source, amount in XP_AMOUNTS.items():
            assert amount > 0, f"{source} has non-positive amount"

    def test_expected_sources_exist(self):
        from lecturelink_api.services.gamification import XP_AMOUNTS
        expected = [
            "flash_review_correct", "flash_review_incorrect",
            "gut_check_correct", "quiz_correct", "quiz_combo_bonus",
            "mastery_increase", "concept_mastered", "mastery_breakthrough",
            "session_complete", "misconception_resolved", "perfect_quiz",
        ]
        for source in expected:
            assert source in XP_AMOUNTS


# ===========================================================================
# Async service tests
# ===========================================================================


class TestAwardXP:
    @pytest.mark.asyncio
    async def test_basic_xp_award(self):
        from lecturelink_api.services.gamification import award_xp

        sb = _make_sb({"xp_events": [], "user_levels": []})
        result = await award_xp(sb, "user-1", "quiz_correct")

        assert result["amount"] == 10
        assert result["total_xp"] == 10
        assert result["level"] == 1
        assert result["leveled_up"] is False

    @pytest.mark.asyncio
    async def test_xp_with_combo_multiplier(self):
        from lecturelink_api.services.gamification import award_xp

        sb = _make_sb({"xp_events": [], "user_levels": []})
        result = await award_xp(sb, "user-1", "quiz_correct", combo_multiplier=3)

        assert result["amount"] == 30

    @pytest.mark.asyncio
    async def test_anti_gaming_mastered_content(self):
        from lecturelink_api.services.gamification import award_xp

        sb = _make_sb({"xp_events": [], "user_levels": []})
        result = await award_xp(
            sb, "user-1", "flash_review_correct",
            metadata={"mastery": 0.9},
        )
        assert result["amount"] == 2  # Capped from 5 to 2

    @pytest.mark.asyncio
    async def test_anti_gaming_speed_run(self):
        from lecturelink_api.services.gamification import award_xp

        sb = _make_sb({"xp_events": [], "user_levels": []})
        result = await award_xp(
            sb, "user-1", "quiz_correct",
            combo_multiplier=3,
            metadata={"response_time_ms": 1000},
        )
        # Combo disabled due to speed: 10 * 1 = 10 instead of 10 * 3 = 30
        assert result["amount"] == 10

    @pytest.mark.asyncio
    async def test_level_up_detection(self):
        from lecturelink_api.services.gamification import award_xp

        sb = _make_sb({
            "xp_events": [],
            "user_levels": [{"total_xp": 95, "current_level": 1}],
        })
        result = await award_xp(sb, "user-1", "quiz_correct")
        # 95 + 10 = 105 → level 2
        assert result["leveled_up"] is True
        assert result["level"] == 2

    @pytest.mark.asyncio
    async def test_unknown_source_gives_zero_xp(self):
        from lecturelink_api.services.gamification import award_xp

        sb = _make_sb({"xp_events": [], "user_levels": []})
        result = await award_xp(sb, "user-1", "nonexistent_source")
        assert result["amount"] == 0


class TestUpdateStreak:
    @pytest.mark.asyncio
    async def test_first_session_creates_streak(self):
        from lecturelink_api.services.gamification import update_streak

        sb = _make_sb({"user_streaks": []})
        result = await update_streak(sb, "user-1")

        assert result["current_streak"] == 1
        assert result["is_new_streak"] is True

    @pytest.mark.asyncio
    async def test_same_day_no_change(self):
        from lecturelink_api.services.gamification import update_streak

        today = date.today()
        sb = _make_sb({
            "user_streaks": [{
                "current_streak": 5,
                "longest_streak": 10,
                "last_session_date": today.isoformat(),
                "streak_freezes_available": 1,
                "streak_freezes_used": 0,
                "freeze_last_reset_at": datetime.now(timezone.utc).isoformat(),
            }],
        })
        result = await update_streak(sb, "user-1")

        assert result["current_streak"] == 5
        assert result["is_new_streak"] is False

    @pytest.mark.asyncio
    async def test_next_day_increments(self):
        from lecturelink_api.services.gamification import update_streak

        yesterday = (date.today() - timedelta(days=1))
        sb = _make_sb({
            "user_streaks": [{
                "current_streak": 5,
                "longest_streak": 10,
                "last_session_date": yesterday.isoformat(),
                "streak_freezes_available": 1,
                "streak_freezes_used": 0,
                "freeze_last_reset_at": datetime.now(timezone.utc).isoformat(),
            }],
        })
        result = await update_streak(sb, "user-1")

        assert result["current_streak"] == 6
        assert result["is_new_streak"] is True

    @pytest.mark.asyncio
    async def test_skip_day_with_freeze(self):
        from lecturelink_api.services.gamification import update_streak

        two_days_ago = (date.today() - timedelta(days=2))
        sb = _make_sb({
            "user_streaks": [{
                "current_streak": 5,
                "longest_streak": 10,
                "last_session_date": two_days_ago.isoformat(),
                "streak_freezes_available": 1,
                "streak_freezes_used": 0,
                "freeze_last_reset_at": datetime.now(timezone.utc).isoformat(),
            }],
        })
        result = await update_streak(sb, "user-1")

        assert result["current_streak"] == 6
        assert result["is_new_streak"] is True

    @pytest.mark.asyncio
    async def test_skip_day_without_freeze_resets(self):
        from lecturelink_api.services.gamification import update_streak

        two_days_ago = (date.today() - timedelta(days=2))
        sb = _make_sb({
            "user_streaks": [{
                "current_streak": 5,
                "longest_streak": 10,
                "last_session_date": two_days_ago.isoformat(),
                "streak_freezes_available": 0,
                "streak_freezes_used": 1,
                "freeze_last_reset_at": datetime.now(timezone.utc).isoformat(),
            }],
        })
        result = await update_streak(sb, "user-1")

        assert result["current_streak"] == 1
        assert result["is_new_streak"] is True

    @pytest.mark.asyncio
    async def test_long_gap_resets(self):
        from lecturelink_api.services.gamification import update_streak

        week_ago = (date.today() - timedelta(days=7))
        sb = _make_sb({
            "user_streaks": [{
                "current_streak": 20,
                "longest_streak": 20,
                "last_session_date": week_ago.isoformat(),
                "streak_freezes_available": 1,
                "streak_freezes_used": 0,
                "freeze_last_reset_at": datetime.now(timezone.utc).isoformat(),
            }],
        })
        result = await update_streak(sb, "user-1")

        assert result["current_streak"] == 1

    @pytest.mark.asyncio
    async def test_streak_milestone_detected(self):
        from lecturelink_api.services.gamification import update_streak

        yesterday = (date.today() - timedelta(days=1))
        sb = _make_sb({
            "user_streaks": [{
                "current_streak": 6,
                "longest_streak": 6,
                "last_session_date": yesterday.isoformat(),
                "streak_freezes_available": 1,
                "streak_freezes_used": 0,
                "freeze_last_reset_at": datetime.now(timezone.utc).isoformat(),
            }],
        })
        result = await update_streak(sb, "user-1")

        assert result["current_streak"] == 7
        assert result["streak_milestone"] == 7

    @pytest.mark.asyncio
    async def test_longest_streak_updated(self):
        from lecturelink_api.services.gamification import update_streak

        yesterday = (date.today() - timedelta(days=1))
        sb = _make_sb({
            "user_streaks": [{
                "current_streak": 10,
                "longest_streak": 10,
                "last_session_date": yesterday.isoformat(),
                "streak_freezes_available": 1,
                "streak_freezes_used": 0,
                "freeze_last_reset_at": datetime.now(timezone.utc).isoformat(),
            }],
        })
        result = await update_streak(sb, "user-1")

        assert result["longest_streak"] == 11


class TestUseStreakFreeze:
    @pytest.mark.asyncio
    async def test_use_freeze_success(self):
        from lecturelink_api.services.gamification import use_streak_freeze

        sb = _make_sb({
            "user_streaks": [{
                "streak_freezes_available": 1,
                "streak_freezes_used": 0,
            }],
        })
        result = await use_streak_freeze(sb, "user-1")

        assert result["success"] is True
        assert result["freezes_remaining"] == 0

    @pytest.mark.asyncio
    async def test_use_freeze_no_available(self):
        from lecturelink_api.services.gamification import use_streak_freeze

        sb = _make_sb({
            "user_streaks": [{
                "streak_freezes_available": 0,
                "streak_freezes_used": 1,
            }],
        })
        result = await use_streak_freeze(sb, "user-1")

        assert result["success"] is False

    @pytest.mark.asyncio
    async def test_use_freeze_no_streak_row(self):
        from lecturelink_api.services.gamification import use_streak_freeze

        sb = _make_sb({"user_streaks": []})
        result = await use_streak_freeze(sb, "user-1")

        assert result["success"] is False


class TestGetUserGamification:
    @pytest.mark.asyncio
    async def test_empty_state(self):
        from lecturelink_api.services.gamification import get_user_gamification

        sb = _make_sb({
            "user_streaks": [],
            "user_levels": [],
            "xp_events": [],
            "badges_earned": [],
        })
        result = await get_user_gamification(sb, "user-1")

        assert result["streak"]["current"] == 0
        assert result["level"]["current"] == 1
        assert result["today_xp"] == 0
        assert result["badges_count"] == 0

    @pytest.mark.asyncio
    async def test_with_existing_data(self):
        from lecturelink_api.services.gamification import get_user_gamification

        today = date.today()
        sb = _make_sb({
            "user_streaks": [{
                "current_streak": 5,
                "longest_streak": 10,
                "last_session_date": today.isoformat(),
                "streak_freezes_available": 1,
            }],
            "user_levels": [{"total_xp": 250, "current_level": 2}],
            "xp_events": [{"amount": 50}, {"amount": 25}],
            "badges_earned": [{"badge_id": "streak_3", "earned_at": "2025-01-01"}],
        })
        result = await get_user_gamification(sb, "user-1")

        assert result["streak"]["current"] == 5
        assert result["streak"]["studied_today"] is True
        assert result["today_xp"] == 75


class TestGetXPHistory:
    @pytest.mark.asyncio
    async def test_empty_history(self):
        from lecturelink_api.services.gamification import get_xp_history

        sb = _make_sb({"xp_events": []})
        result = await get_xp_history(sb, "user-1", days=7)

        assert len(result) == 7
        assert all(d["xp"] == 0 for d in result)

    @pytest.mark.asyncio
    async def test_history_with_events(self):
        from lecturelink_api.services.gamification import get_xp_history

        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        sb = _make_sb({
            "xp_events": [
                {"amount": 10, "created_at": f"{today}T10:00:00+00:00"},
                {"amount": 20, "created_at": f"{today}T11:00:00+00:00"},
            ],
        })
        result = await get_xp_history(sb, "user-1", days=7)

        assert len(result) == 7
        # Last day should have 30 XP
        assert result[-1]["xp"] == 30
