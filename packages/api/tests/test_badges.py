"""Tests for the badge system service."""

from __future__ import annotations

from unittest.mock import MagicMock

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
    sb = MagicMock()
    table_responses = table_responses or {}

    def table_side_effect(name):
        if name in table_responses:
            return _mock_chain(table_responses[name])
        return _mock_chain([])

    sb.table.side_effect = table_side_effect
    return sb


# ===========================================================================
# Badge definitions
# ===========================================================================


class TestBadgeDefinitions:
    def test_all_badges_have_required_fields(self):
        from lecturelink_api.services.badges import BADGE_DEFINITIONS
        for badge_id, badge in BADGE_DEFINITIONS.items():
            assert "name" in badge, f"{badge_id} missing name"
            assert "category" in badge, f"{badge_id} missing category"
            assert "description" in badge, f"{badge_id} missing description"
            assert "icon" in badge, f"{badge_id} missing icon"

    def test_expected_categories(self):
        from lecturelink_api.services.badges import BADGE_DEFINITIONS
        categories = {b["category"] for b in BADGE_DEFINITIONS.values()}
        assert "streak" in categories
        assert "mastery" in categories
        assert "assessment" in categories
        assert "behavior" in categories
        assert "rare" in categories

    def test_badge_count(self):
        from lecturelink_api.services.badges import BADGE_DEFINITIONS
        assert len(BADGE_DEFINITIONS) >= 20


# ===========================================================================
# Badge awarding
# ===========================================================================


class TestCheckAndAwardBadges:
    @pytest.mark.asyncio
    async def test_streak_badge_awarded(self):
        from lecturelink_api.services.badges import check_and_award_badges

        # No existing badges
        sb = _make_sb({"badges_earned": []})
        result = await check_and_award_badges(
            sb, "user-1", "session_complete",
            {"streak_count": 7, "session_hour": 14, "is_weekend": False, "flash_review_count": 0},
        )

        # Should get streak_3 and streak_7
        badge_ids = [b["badge_id"] for b in result]
        assert "streak_3" in badge_ids
        assert "streak_7" in badge_ids

    @pytest.mark.asyncio
    async def test_no_duplicate_badges(self):
        from lecturelink_api.services.badges import check_and_award_badges

        # Already has streak_3
        sb = _make_sb({
            "badges_earned": [{"id": "x", "badge_id": "streak_3"}],
        })
        result = await check_and_award_badges(
            sb, "user-1", "session_complete",
            {"streak_count": 3, "session_hour": 14, "is_weekend": False, "flash_review_count": 0},
        )

        badge_ids = [b["badge_id"] for b in result]
        assert "streak_3" not in badge_ids

    @pytest.mark.asyncio
    async def test_perfect_quiz_badge(self):
        from lecturelink_api.services.badges import check_and_award_badges

        sb = _make_sb({"badges_earned": []})
        result = await check_and_award_badges(
            sb, "user-1", "quiz_complete",
            {"accuracy": 1.0, "total": 10, "score": 10},
        )

        badge_ids = [b["badge_id"] for b in result]
        assert "perfect_quiz" in badge_ids

    @pytest.mark.asyncio
    async def test_imperfect_quiz_no_badge(self):
        from lecturelink_api.services.badges import check_and_award_badges

        sb = _make_sb({"badges_earned": []})
        result = await check_and_award_badges(
            sb, "user-1", "quiz_complete",
            {"accuracy": 0.9, "total": 10, "score": 9},
        )

        badge_ids = [b["badge_id"] for b in result]
        assert "perfect_quiz" not in badge_ids

    @pytest.mark.asyncio
    async def test_mastery_first_concept(self):
        from lecturelink_api.services.badges import check_and_award_badges

        sb = _make_sb({"badges_earned": []})
        # RPC for mastery check
        rpc_mock = MagicMock()
        rpc_mock.execute.return_value = _mock_execute([
            {"concept_id": "c1", "total_attempts": 10, "accuracy": 0.9,
             "recent_accuracy": 0.9, "concept_title": "Topic A"},
        ])
        sb.rpc.return_value = rpc_mock

        result = await check_and_award_badges(
            sb, "user-1", "mastery_update",
            {"concept_id": "c1", "mastery_before": 0.5, "mastery_after": 0.85,
             "course_id": "c1"},
        )

        badge_ids = [b["badge_id"] for b in result]
        assert "first_concept_mastered" in badge_ids

    @pytest.mark.asyncio
    async def test_zero_to_hero(self):
        from lecturelink_api.services.badges import check_and_award_badges

        sb = _make_sb({"badges_earned": []})
        rpc_mock = MagicMock()
        rpc_mock.execute.return_value = _mock_execute([])
        sb.rpc.return_value = rpc_mock

        result = await check_and_award_badges(
            sb, "user-1", "mastery_update",
            {"concept_id": "c1", "mastery_before": 0, "mastery_after": 1.0,
             "course_id": "c1"},
        )

        badge_ids = [b["badge_id"] for b in result]
        assert "zero_to_hero" in badge_ids

    @pytest.mark.asyncio
    async def test_exam_ready_badge(self):
        from lecturelink_api.services.badges import check_and_award_badges

        sb = _make_sb({"badges_earned": []})
        result = await check_and_award_badges(
            sb, "user-1", "readiness_update",
            {"assessment_id": "a1", "readiness": 85, "readiness_7d_ago": None},
        )

        badge_ids = [b["badge_id"] for b in result]
        assert "exam_ready" in badge_ids

    @pytest.mark.asyncio
    async def test_clutch_player_badge(self):
        from lecturelink_api.services.badges import check_and_award_badges

        sb = _make_sb({"badges_earned": []})
        result = await check_and_award_badges(
            sb, "user-1", "readiness_update",
            {"assessment_id": "a1", "readiness": 85, "readiness_7d_ago": 40},
        )

        badge_ids = [b["badge_id"] for b in result]
        assert "clutch_player" in badge_ids

    @pytest.mark.asyncio
    async def test_misconception_slayer(self):
        from lecturelink_api.services.badges import check_and_award_badges

        sb = _make_sb({"badges_earned": []})
        result = await check_and_award_badges(
            sb, "user-1", "misconception_resolved",
            {"resolved_count": 3},
        )

        badge_ids = [b["badge_id"] for b in result]
        assert "misconception_slayer" in badge_ids

    @pytest.mark.asyncio
    async def test_unknown_trigger_returns_empty(self):
        from lecturelink_api.services.badges import check_and_award_badges

        sb = _make_sb({"badges_earned": []})
        result = await check_and_award_badges(
            sb, "user-1", "unknown_trigger", {},
        )
        assert result == []


# ===========================================================================
# Get badges
# ===========================================================================


class TestGetUserBadges:
    @pytest.mark.asyncio
    async def test_no_earned_badges(self):
        from lecturelink_api.services.badges import get_user_badges

        sb = _make_sb({"badges_earned": []})
        result = await get_user_badges(sb, "user-1")

        assert result["total_earned"] == 0
        assert len(result["available"]) > 0

    @pytest.mark.asyncio
    async def test_earned_badge_appears(self):
        from lecturelink_api.services.badges import get_user_badges

        sb = _make_sb({
            "badges_earned": [
                {"badge_id": "streak_3", "earned_at": "2025-01-01T00:00:00Z", "metadata": {}},
            ],
        })
        result = await get_user_badges(sb, "user-1")

        assert result["total_earned"] == 1
        assert result["earned"][0]["badge_id"] == "streak_3"
        assert result["earned"][0]["name"] == "3-Day Starter"


class TestGetBadgeProgress:
    @pytest.mark.asyncio
    async def test_already_earned(self):
        from lecturelink_api.services.badges import get_badge_progress

        sb = _make_sb({"badges_earned": [{"id": "x"}]})
        result = await get_badge_progress(sb, "user-1", "streak_3")

        assert result["percent"] == 100

    @pytest.mark.asyncio
    async def test_streak_progress(self):
        from lecturelink_api.services.badges import get_badge_progress

        # Not earned, streak at 5
        call_count = {"n": 0}
        def table_side_effect(name):
            call_count["n"] += 1
            if name == "badges_earned":
                return _mock_chain([])  # not earned
            if name == "user_streaks":
                return _mock_chain([{"current_streak": 5}])
            return _mock_chain([])

        sb = MagicMock()
        sb.table.side_effect = table_side_effect

        result = await get_badge_progress(sb, "user-1", "streak_7")
        assert result["current"] == 5
        assert result["target"] == 7
        assert 71 <= result["percent"] <= 72

    @pytest.mark.asyncio
    async def test_unknown_badge(self):
        from lecturelink_api.services.badges import get_badge_progress

        sb = _make_sb({})
        result = await get_badge_progress(sb, "user-1", "nonexistent")
        assert result["current"] == 0
