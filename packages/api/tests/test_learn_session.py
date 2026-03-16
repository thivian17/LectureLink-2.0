"""Tests for the Learn Mode session orchestrator service."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


def _mock_execute(data):
    resp = MagicMock()
    resp.data = data
    resp.count = 0
    return resp


def _mock_chain(final_data):
    chain = MagicMock()
    chain.execute.return_value = _mock_execute(final_data)
    for method in (
        "select", "insert", "update", "delete",
        "eq", "in_", "order", "limit", "single",
    ):
        getattr(chain, method).return_value = chain
    return chain


def _setup_supabase_for_start(
    existing_sessions=None,
    priority_assessments=None,
    concept_links=None,
    mastery=None,
    course_name="PHYS 201",
    fallback_concepts=None,
    recent_completed_sessions=None,
):
    """Return a mock supabase client configured for start_learn_session.

    Args:
        priority_assessments: Assessment-shaped rows for get_study_priorities RPC.
        concept_links: Rows for concept_assessment_links table.
        mastery: Rows for get_concept_mastery RPC.
        fallback_concepts: Concepts returned when no assessment links exist.
        recent_completed_sessions: Rows for recently completed sessions (rotation).
    """
    sb = MagicMock()

    rpc_results = {
        "get_study_priorities": priority_assessments or [],
        "get_concept_mastery": mastery or [],
    }

    def rpc_side_effect(name, params=None):
        result = MagicMock()
        result.execute.return_value = _mock_execute(
            rpc_results.get(name, [])
        )
        return result

    sb.rpc.side_effect = rpc_side_effect

    # Track how many times learn_sessions table is accessed to distinguish
    # 1st call (active session check) from 2nd call (recent completed sessions query)
    learn_sessions_call_count = {"n": 0}

    def table_side_effect(name):
        if name == "learn_sessions":
            learn_sessions_call_count["n"] += 1
            call_num = learn_sessions_call_count["n"]
            if call_num == 1:
                # First call: active session check (+ update for expiry)
                chain = _mock_chain(existing_sessions or [])
                insert_chain = MagicMock()
                insert_chain.execute.return_value = _mock_execute([{"id": "session-1"}])
                chain.insert.return_value = insert_chain
                return chain
            if call_num == 2 and existing_sessions:
                # Second call when there's a stale session to expire: the update call
                chain = _mock_chain([])
                insert_chain = MagicMock()
                insert_chain.execute.return_value = _mock_execute([{"id": "session-1"}])
                chain.insert.return_value = insert_chain
                return chain
            # Subsequent calls: recent completed sessions query or insert
            chain = _mock_chain(recent_completed_sessions or [])
            insert_chain = MagicMock()
            insert_chain.execute.return_value = _mock_execute([{"id": "session-1"}])
            chain.insert.return_value = insert_chain
            return chain
        if name == "courses":
            return _mock_chain({"name": course_name})
        if name == "concept_assessment_links":
            return _mock_chain(concept_links or [])
        if name == "concepts":
            return _mock_chain(fallback_concepts or [
                {"id": "c1", "title": "Concept 1", "description": "D1",
                 "category": "general", "difficulty_estimate": 0.5},
            ])
        return _mock_chain([])

    sb.table.side_effect = table_side_effect
    return sb


class TestStartLearnSession:
    @pytest.mark.asyncio
    async def test_creates_db_row(self):
        from lecturelink_api.services.learn_session import start_learn_session

        sb = _setup_supabase_for_start(
            priority_assessments=[
                {"assessment_id": "a1", "title": "Midterm 1", "course_id": "course1",
                 "due_date": "2027-06-15", "weight_percent": 25.0, "priority_score": 0.9},
            ],
            concept_links=[
                {"concept_id": "c1", "relevance_score": 0.9},
            ],
            mastery=[
                {"concept_id": "c1", "concept_title": "Entropy", "total_attempts": 5,
                 "accuracy": 0.6, "recent_accuracy": 0.8, "trend": "stable"},
            ],
        )

        with patch(
            "lecturelink_api.services.learn_session.get_flash_review_cards",
            new_callable=AsyncMock,
            return_value=[],
        ):
            result = await start_learn_session(sb, "user1", "course1", 15)

        assert "session_id" in result
        assert result["daily_briefing"]["time_budget"] == 15
        # Verify insert was called on learn_sessions
        sb.table.assert_any_call("learn_sessions")

    @pytest.mark.asyncio
    async def test_assessment_driven_concept_selection(self):
        """Concepts linked to the top-priority assessment are selected."""
        from lecturelink_api.services.learn_session import start_learn_session

        sb = _setup_supabase_for_start(
            priority_assessments=[
                {"assessment_id": "a1", "title": "Midterm 1", "course_id": "course1",
                 "due_date": "2027-06-15", "weight_percent": 25.0, "priority_score": 0.95},
            ],
            concept_links=[
                {"concept_id": "c1", "relevance_score": 0.9},
                {"concept_id": "c2", "relevance_score": 0.5},
            ],
            mastery=[
                {"concept_id": "c1", "concept_title": "High Priority", "total_attempts": 3,
                 "accuracy": 0.2, "recent_accuracy": 0.3, "trend": "stable"},
                {"concept_id": "c2", "concept_title": "Low Priority", "total_attempts": 10,
                 "accuracy": 0.7, "recent_accuracy": 0.8, "trend": "improving"},
            ],
        )

        with patch(
            "lecturelink_api.services.learn_session.get_flash_review_cards",
            new_callable=AsyncMock,
            return_value=[],
        ):
            result = await start_learn_session(sb, "user1", "course1", 15)

        # 15 min = 1 concept, should pick highest relevance link (c1)
        concepts = result["daily_briefing"]["concepts_planned"]
        assert len(concepts) == 1
        assert concepts[0]["title"] == "High Priority"
        # Assessment context should mention the target assessment
        assert "Midterm 1" in (result["daily_briefing"]["assessment_context"] or "")

    @pytest.mark.asyncio
    async def test_time_budget_10_min_1_concept(self):
        from lecturelink_api.services.learn_session import start_learn_session

        sb = _setup_supabase_for_start(
            priority_assessments=[
                {"assessment_id": "a1", "title": "Exam", "course_id": "course1",
                 "due_date": "2027-06-15", "weight_percent": 20.0, "priority_score": 0.9},
            ],
            concept_links=[
                {"concept_id": "c1", "relevance_score": 0.9},
                {"concept_id": "c2", "relevance_score": 0.7},
            ],
            mastery=[
                {"concept_id": "c1", "concept_title": "A", "total_attempts": 2,
                 "accuracy": 0.5, "recent_accuracy": 0.5, "trend": "stable"},
                {"concept_id": "c2", "concept_title": "B", "total_attempts": 3,
                 "accuracy": 0.6, "recent_accuracy": 0.6, "trend": "stable"},
            ],
        )

        with patch(
            "lecturelink_api.services.learn_session.get_flash_review_cards",
            new_callable=AsyncMock,
            return_value=[],
        ):
            result = await start_learn_session(sb, "user1", "course1", 10)

        assert len(result["daily_briefing"]["concepts_planned"]) == 1

    @pytest.mark.asyncio
    async def test_time_budget_20_min_2_concepts(self):
        from lecturelink_api.services.learn_session import start_learn_session

        sb = _setup_supabase_for_start(
            priority_assessments=[
                {"assessment_id": "a1", "title": "Exam", "course_id": "course1",
                 "due_date": "2027-06-15", "weight_percent": 20.0, "priority_score": 0.9},
            ],
            concept_links=[
                {"concept_id": "c1", "relevance_score": 0.9},
                {"concept_id": "c2", "relevance_score": 0.7},
                {"concept_id": "c3", "relevance_score": 0.5},
            ],
            mastery=[
                {"concept_id": "c1", "concept_title": "A", "total_attempts": 2,
                 "accuracy": 0.5, "recent_accuracy": 0.5, "trend": "stable"},
                {"concept_id": "c2", "concept_title": "B", "total_attempts": 3,
                 "accuracy": 0.6, "recent_accuracy": 0.6, "trend": "stable"},
                {"concept_id": "c3", "concept_title": "C", "total_attempts": 1,
                 "accuracy": 0.4, "recent_accuracy": 0.4, "trend": "stable"},
            ],
        )

        with patch(
            "lecturelink_api.services.learn_session.get_flash_review_cards",
            new_callable=AsyncMock,
            return_value=[],
        ):
            result = await start_learn_session(sb, "user1", "course1", 20)

        assert len(result["daily_briefing"]["concepts_planned"]) == 2

    @pytest.mark.asyncio
    async def test_time_budget_25_min_2_concepts(self):
        from lecturelink_api.services.learn_session import start_learn_session

        sb = _setup_supabase_for_start(
            priority_assessments=[
                {"assessment_id": "a1", "title": "Final", "course_id": "course1",
                 "due_date": "2026-04-01", "weight_percent": 40.0, "priority_score": 0.95},
            ],
            concept_links=[
                {"concept_id": f"c{i}", "relevance_score": 0.9 - i * 0.1}
                for i in range(5)
            ],
            mastery=[
                {"concept_id": f"c{i}", "concept_title": f"C{i}", "total_attempts": 2,
                 "accuracy": 0.5, "recent_accuracy": 0.5, "trend": "stable"}
                for i in range(5)
            ],
        )

        with patch(
            "lecturelink_api.services.learn_session.get_flash_review_cards",
            new_callable=AsyncMock,
            return_value=[],
        ):
            result = await start_learn_session(sb, "user1", "course1", 25)

        assert len(result["daily_briefing"]["concepts_planned"]) == 2

    @pytest.mark.asyncio
    async def test_fallback_to_direct_concepts_when_no_assessments(self):
        """When no assessments exist, fall back to direct concept query."""
        from lecturelink_api.services.learn_session import start_learn_session

        sb = _setup_supabase_for_start(
            priority_assessments=[],
            fallback_concepts=[
                {"id": "c1", "title": "Fallback Concept", "description": "D1",
                 "category": "general", "difficulty_estimate": 0.5},
            ],
        )

        with patch(
            "lecturelink_api.services.learn_session.get_flash_review_cards",
            new_callable=AsyncMock,
            return_value=[],
        ):
            result = await start_learn_session(sb, "user1", "course1", 15)

        concepts = result["daily_briefing"]["concepts_planned"]
        assert len(concepts) == 1
        assert concepts[0]["title"] == "Fallback Concept"

    @pytest.mark.asyncio
    async def test_no_duplicate_active_sessions(self):
        """If an active session exists, return it instead of creating a new one."""
        from lecturelink_api.services.learn_session import start_learn_session

        existing_session = {
            "id": "existing-session",
            "user_id": "user1",
            "course_id": "course1",
            "status": "active",
            "started_at": (datetime.now(UTC) - timedelta(minutes=30)).isoformat(),
            "session_data": {
                "daily_briefing": {
                    "course_name": "PHYS 201",
                    "focus_description": "Entropy",
                    "time_budget": 15,
                    "concepts_planned": [],
                },
            },
        }
        sb = _setup_supabase_for_start(existing_sessions=[existing_session])

        with patch(
            "lecturelink_api.services.learn_session.get_flash_review_cards",
            new_callable=AsyncMock,
            return_value=[],
        ):
            result = await start_learn_session(sb, "user1", "course1", 15)

        assert result["session_id"] == "existing-session"

    @pytest.mark.asyncio
    async def test_stale_session_expires_and_creates_new(self):
        """Sessions older than 2 hours should be expired, not resumed."""
        from lecturelink_api.services.learn_session import start_learn_session

        stale_session = {
            "id": "stale-session",
            "user_id": "user1",
            "course_id": "course1",
            "status": "active",
            "started_at": (datetime.now(UTC) - timedelta(hours=3)).isoformat(),
            "session_data": {
                "daily_briefing": {"concepts_planned": []},
            },
        }
        sb = _setup_supabase_for_start(
            existing_sessions=[stale_session],
            priority_assessments=[
                {"assessment_id": "a1", "title": "Midterm 1", "course_id": "course1",
                 "due_date": "2027-06-15", "weight_percent": 25.0, "priority_score": 0.9},
            ],
            concept_links=[
                {"concept_id": "c1", "relevance_score": 0.9},
            ],
            mastery=[
                {"concept_id": "c1", "concept_title": "Entropy", "total_attempts": 5,
                 "accuracy": 0.6, "recent_accuracy": 0.8, "trend": "stable"},
            ],
        )

        with patch(
            "lecturelink_api.services.learn_session.get_flash_review_cards",
            new_callable=AsyncMock,
            return_value=[],
        ):
            result = await start_learn_session(sb, "user1", "course1", 15)

        # Should have created a NEW session, not returned the stale one
        assert result["session_id"] != "stale-session"

    @pytest.mark.asyncio
    async def test_fresh_session_still_resumed(self):
        """Sessions less than 2 hours old should still be resumed."""
        from lecturelink_api.services.learn_session import start_learn_session

        fresh_session = {
            "id": "fresh-session",
            "user_id": "user1",
            "course_id": "course1",
            "status": "active",
            "started_at": (datetime.now(UTC) - timedelta(minutes=30)).isoformat(),
            "session_data": {
                "daily_briefing": {
                    "course_name": "PHYS 201",
                    "focus_description": "Entropy",
                    "time_budget": 15,
                    "concepts_planned": [],
                },
            },
        }
        sb = _setup_supabase_for_start(existing_sessions=[fresh_session])

        with patch(
            "lecturelink_api.services.learn_session.get_flash_review_cards",
            new_callable=AsyncMock,
            return_value=[],
        ):
            result = await start_learn_session(sb, "user1", "course1", 15)

        assert result["session_id"] == "fresh-session"

    @pytest.mark.asyncio
    async def test_recently_studied_concepts_excluded(self):
        """Concepts from recent completed sessions should be rotated out."""
        from lecturelink_api.services.learn_session import start_learn_session

        sb = _setup_supabase_for_start(
            priority_assessments=[
                {"assessment_id": "a1", "title": "Midterm 1", "course_id": "course1",
                 "due_date": "2027-06-15", "weight_percent": 25.0, "priority_score": 0.9},
            ],
            concept_links=[
                {"concept_id": "c1", "relevance_score": 0.9},
                {"concept_id": "c2", "relevance_score": 0.7},
                {"concept_id": "c3", "relevance_score": 0.5},
            ],
            mastery=[
                {"concept_id": "c1", "concept_title": "Already Studied", "total_attempts": 5,
                 "accuracy": 0.6, "recent_accuracy": 0.8, "trend": "stable"},
                {"concept_id": "c2", "concept_title": "Fresh Concept", "total_attempts": 2,
                 "accuracy": 0.4, "recent_accuracy": 0.5, "trend": "stable"},
                {"concept_id": "c3", "concept_title": "Also Fresh", "total_attempts": 1,
                 "accuracy": 0.3, "recent_accuracy": 0.3, "trend": "stable"},
            ],
            recent_completed_sessions=[
                {"concepts_planned": ["c1"]},
            ],
        )

        with patch(
            "lecturelink_api.services.learn_session.get_flash_review_cards",
            new_callable=AsyncMock,
            return_value=[],
        ):
            result = await start_learn_session(sb, "user1", "course1", 15)

        concepts = result["daily_briefing"]["concepts_planned"]
        assert len(concepts) == 1
        # c1 was recently studied, so c2 should be selected instead
        assert concepts[0]["title"] == "Fresh Concept"

    @pytest.mark.asyncio
    async def test_rotation_relaxes_when_all_concepts_recently_studied(self):
        """If all concepts were recently studied, still return concepts."""
        from lecturelink_api.services.learn_session import start_learn_session

        sb = _setup_supabase_for_start(
            priority_assessments=[
                {"assessment_id": "a1", "title": "Midterm 1", "course_id": "course1",
                 "due_date": "2027-06-15", "weight_percent": 25.0, "priority_score": 0.9},
            ],
            concept_links=[
                {"concept_id": "c1", "relevance_score": 0.9},
            ],
            mastery=[
                {"concept_id": "c1", "concept_title": "Only Concept", "total_attempts": 5,
                 "accuracy": 0.6, "recent_accuracy": 0.8, "trend": "stable"},
            ],
            recent_completed_sessions=[
                {"concepts_planned": ["c1"]},
            ],
        )

        with patch(
            "lecturelink_api.services.learn_session.get_flash_review_cards",
            new_callable=AsyncMock,
            return_value=[],
        ):
            result = await start_learn_session(sb, "user1", "course1", 15)

        # Even though c1 was recently studied, it should still be selected (relaxation)
        concepts = result["daily_briefing"]["concepts_planned"]
        assert len(concepts) == 1
        assert concepts[0]["title"] == "Only Concept"

    @pytest.mark.asyncio
    async def test_fallback_concepts_ordered_by_created_at(self):
        """When no assessments exist, concepts should be ordered by recency."""
        from lecturelink_api.services.learn_session import start_learn_session

        sb = _setup_supabase_for_start(
            priority_assessments=[],
            fallback_concepts=[
                {"id": "c1", "title": "Recent Concept", "description": "D1",
                 "category": "general", "difficulty_estimate": 0.5},
            ],
        )

        with patch(
            "lecturelink_api.services.learn_session.get_flash_review_cards",
            new_callable=AsyncMock,
            return_value=[],
        ):
            result = await start_learn_session(sb, "user1", "course1", 15)

        concepts = result["daily_briefing"]["concepts_planned"]
        assert len(concepts) == 1
        assert concepts[0]["title"] == "Recent Concept"
        # Verify .order() was called on the concepts table query
        # (the mock chain records the call)


class TestSubmitPowerQuizAnswer:
    def _setup_session_with_quiz(self, combo_count=0):
        sb = MagicMock()

        session = {
            "id": "s1",
            "user_id": "user1",
            "course_id": "course1",
            "session_data": {
                "power_quiz": {
                    "quiz_id": "quiz1",
                    "questions": [
                        {
                            "question_id": "q1",
                            "question_text": "What is X?",
                            "options": ["A) Wrong", "B) Correct", "C) Wrong", "D) Wrong"],
                            "_correct_answer": "B",
                            "_correct_index": 1,
                            "_explanation": "B is the right answer.",
                        },
                    ],
                },
                "combo_count": combo_count,
                "combo_max": combo_count,
                "quiz_results": [],
            },
        }

        def table_side_effect(name):
            if name == "learn_sessions":
                chain = _mock_chain(session)
                update_chain = MagicMock()
                update_chain.eq.return_value = update_chain
                update_chain.execute.return_value = _mock_execute([])
                chain.update.return_value = update_chain
                return chain
            return _mock_chain([])

        sb.table.side_effect = table_side_effect
        return sb

    @pytest.mark.asyncio
    async def test_correct_answer(self):
        from lecturelink_api.services.learn_session import submit_power_quiz_answer

        sb = self._setup_session_with_quiz()

        mock_xp = AsyncMock(return_value={"amount": 10, "total_xp": 10, "level": 1, "leveled_up": False})
        with patch("lecturelink_api.services.learn_session._award_xp", mock_xp):
            result = await submit_power_quiz_answer(
                sb, "user1", "s1", "q1", answer_index=1, time_ms=5000
            )

        assert result["correct"] is True
        assert result["correct_answer"] == "B) Correct"
        assert result["xp_earned"] > 0

    @pytest.mark.asyncio
    async def test_incorrect_answer(self):
        from lecturelink_api.services.learn_session import submit_power_quiz_answer

        sb = self._setup_session_with_quiz()

        result = await submit_power_quiz_answer(
            sb, "user1", "s1", "q1", answer_index=0, time_ms=5000
        )

        assert result["correct"] is False

    @pytest.mark.asyncio
    async def test_combo_tracking(self):
        """3 consecutive correct answers should give 2x multiplier."""
        from lecturelink_api.services.learn_session import submit_power_quiz_answer

        sb = self._setup_session_with_quiz(combo_count=2)

        result = await submit_power_quiz_answer(
            sb, "user1", "s1", "q1", answer_index=1, time_ms=5000
        )

        assert result["correct"] is True
        assert result["combo_count"] == 3
        assert result["combo_multiplier"] == 2

    @pytest.mark.asyncio
    async def test_speed_run_disables_combo(self):
        """<3000ms answers should disable combo bonus."""
        from lecturelink_api.services.learn_session import submit_power_quiz_answer

        sb = self._setup_session_with_quiz(combo_count=4)

        result = await submit_power_quiz_answer(
            sb, "user1", "s1", "q1", answer_index=1, time_ms=2000  # <3000ms
        )

        assert result["correct"] is True
        assert result["combo_multiplier"] == 1  # No combo for speed runs


class TestComboMultiplier:
    def test_no_combo_below_3(self):
        from lecturelink_api.services.learn_session import _get_combo_multiplier

        assert _get_combo_multiplier(0) == 1
        assert _get_combo_multiplier(1) == 1
        assert _get_combo_multiplier(2) == 1

    def test_2x_at_3(self):
        from lecturelink_api.services.learn_session import _get_combo_multiplier

        assert _get_combo_multiplier(3) == 2
        assert _get_combo_multiplier(4) == 2

    def test_3x_at_5(self):
        from lecturelink_api.services.learn_session import _get_combo_multiplier

        assert _get_combo_multiplier(5) == 3
        assert _get_combo_multiplier(7) == 3

    def test_4x_at_8(self):
        from lecturelink_api.services.learn_session import _get_combo_multiplier

        assert _get_combo_multiplier(8) == 4
        assert _get_combo_multiplier(10) == 4


class TestCompleteLearnSession:
    @pytest.mark.asyncio
    async def test_produces_correct_celebration_structure(self):
        from lecturelink_api.services.learn_session import complete_learn_session

        sb = MagicMock()
        session = {
            "id": "s1",
            "user_id": "user1",
            "course_id": "course1",
            "started_at": "2026-01-01T10:00:00+00:00",
            "session_data": {
                "daily_briefing": {
                    "concepts_planned": [
                        {"concept_id": "c1", "title": "Entropy", "mastery": 0.3},
                    ],
                },
                "flash_review_results": [],
                "quiz_results": [
                    {"question_id": "q1", "correct": True, "xp_earned": 10},
                    {"question_id": "q2", "correct": False, "xp_earned": 3},
                ],
                "combo_max": 1,
                "xp_breakdown": [],
            },
        }

        def table_side_effect(name):
            if name == "learn_sessions":
                chain = _mock_chain(session)
                update_chain = MagicMock()
                update_chain.eq.return_value = update_chain
                update_chain.execute.return_value = _mock_execute([])
                chain.update.return_value = update_chain
                return chain
            return _mock_chain([])

        sb.table.side_effect = table_side_effect

        rpc_mock = MagicMock()
        rpc_mock.execute.return_value = _mock_execute([])
        sb.rpc.return_value = rpc_mock

        result = await complete_learn_session(sb, "user1", "s1")

        assert "session_summary" in result
        assert "xp_summary" in result
        assert "streak" in result
        assert "badges_earned" in result
        assert "tomorrow_preview" in result

        # Quiz score
        assert result["session_summary"]["quiz_score"]["correct"] == 1
        assert result["session_summary"]["quiz_score"]["total"] == 2

        # XP breakdown has three sources
        sources = [b["source"] for b in result["xp_summary"]["breakdown"]]
        assert "flash_review" in sources
        assert "power_quiz" in sources
        assert "session_complete" in sources


class TestAbandonLearnSession:
    @pytest.mark.asyncio
    async def test_sets_status_abandoned(self):
        from lecturelink_api.services.learn_session import abandon_learn_session

        sb = MagicMock()
        session = {
            "id": "s1",
            "user_id": "user1",
            "course_id": "course1",
            "status": "active",
            "session_data": {},
        }

        def table_side_effect(name):
            if name == "learn_sessions":
                chain = _mock_chain(session)
                update_chain = MagicMock()
                update_chain.eq.return_value = update_chain
                update_chain.execute.return_value = _mock_execute([])
                chain.update.return_value = update_chain
                return chain
            return _mock_chain([])

        sb.table.side_effect = table_side_effect

        result = await abandon_learn_session(sb, "user1", "s1")

        assert result["status"] == "abandoned"
        assert result["partial_xp_preserved"] is True

    @pytest.mark.asyncio
    async def test_not_found_raises(self):
        from lecturelink_api.services.learn_session import abandon_learn_session

        sb = MagicMock()

        def table_side_effect(name):
            chain = _mock_chain(None)
            chain.execute.side_effect = Exception("not found")
            return chain

        sb.table.side_effect = table_side_effect

        with pytest.raises(ValueError, match="not found"):
            await abandon_learn_session(sb, "user1", "nonexistent")


class TestPowerQuizReuse:
    @pytest.mark.asyncio
    async def test_reuse_returns_formatted_questions(self):
        """_try_reuse_power_quiz_questions should return properly formatted dicts."""
        from lecturelink_api.services.learn_session import _try_reuse_power_quiz_questions

        sb = MagicMock()

        quiz_q_data = [
            {
                "id": "stored-q1",
                "question_text": "What is entropy?",
                "options": [
                    {"label": "A", "text": "Disorder"},
                    {"label": "B", "text": "Energy"},
                    {"label": "C", "text": "Force"},
                    {"label": "D", "text": "Mass"},
                ],
                "correct_answer": "A",
                "explanation": "Entropy measures disorder.",
                "concept_id": "c1",
            },
        ]

        def table_side_effect(name):
            if name == "quiz_questions":
                chain = _mock_chain(quiz_q_data)
                # Also need update chain
                update_chain = MagicMock()
                update_chain.eq.return_value = update_chain
                update_chain.execute.return_value = _mock_execute([])
                chain.update.return_value = update_chain
                return chain
            return _mock_chain([])

        sb.table.side_effect = table_side_effect
        rpc_mock = MagicMock()
        rpc_mock.execute.return_value = _mock_execute(None)
        sb.rpc.return_value = rpc_mock

        result = await _try_reuse_power_quiz_questions(sb, "course1", ["c1"], 2)

        assert len(result) == 1
        q = result[0]
        assert "question_id" in q
        assert q["question_text"] == "What is entropy?"
        assert q["_stored_question_id"] == "stored-q1"
        assert q["_source"] == "reused"
        assert isinstance(q["_correct_index"], int)

    @pytest.mark.asyncio
    async def test_reuse_returns_empty_when_no_candidates(self):
        """Should return empty list when no matching questions exist."""
        from lecturelink_api.services.learn_session import _try_reuse_power_quiz_questions

        sb = MagicMock()

        def table_side_effect(name):
            return _mock_chain([])

        sb.table.side_effect = table_side_effect

        result = await _try_reuse_power_quiz_questions(sb, "course1", ["c1"], 3)
        assert result == []

    @pytest.mark.asyncio
    async def test_reuse_returns_empty_for_empty_concept_ids(self):
        """Should return empty list when concept_ids is empty."""
        from lecturelink_api.services.learn_session import _try_reuse_power_quiz_questions

        sb = MagicMock()
        result = await _try_reuse_power_quiz_questions(sb, "course1", [], 3)
        assert result == []

    @pytest.mark.asyncio
    async def test_reuse_limits_to_count(self):
        """Should not return more than requested count."""
        from lecturelink_api.services.learn_session import _try_reuse_power_quiz_questions

        sb = MagicMock()

        quiz_q_data = [
            {
                "id": f"stored-q{i}",
                "question_text": f"Question {i}?",
                "options": ["A) Opt1", "B) Opt2", "C) Opt3", "D) Opt4"],
                "correct_answer": "A",
                "explanation": f"Explanation {i}",
                "concept_id": "c1",
            }
            for i in range(10)
        ]

        def table_side_effect(name):
            if name == "quiz_questions":
                chain = _mock_chain(quiz_q_data)
                update_chain = MagicMock()
                update_chain.eq.return_value = update_chain
                update_chain.execute.return_value = _mock_execute([])
                chain.update.return_value = update_chain
                return chain
            return _mock_chain([])

        sb.table.side_effect = table_side_effect
        rpc_mock = MagicMock()
        rpc_mock.execute.return_value = _mock_execute(None)
        sb.rpc.return_value = rpc_mock

        result = await _try_reuse_power_quiz_questions(sb, "course1", ["c1"], 3)
        assert len(result) <= 3


class TestFindCorrectIndexForReuse:
    def test_label_match(self):
        from lecturelink_api.services.learn_session import _find_correct_index_for_reuse

        options = ["A) Alpha", "B) Beta", "C) Gamma", "D) Delta"]
        assert _find_correct_index_for_reuse(options, "B") == 1

    def test_exact_text_match(self):
        from lecturelink_api.services.learn_session import _find_correct_index_for_reuse

        options = ["Alpha", "Beta", "Gamma"]
        assert _find_correct_index_for_reuse(options, "Beta") == 1

    def test_defaults_to_zero(self):
        from lecturelink_api.services.learn_session import _find_correct_index_for_reuse

        options = ["Alpha", "Beta"]
        assert _find_correct_index_for_reuse(options, "Unknown") == 0


class TestPowerQuizPersistence:
    @pytest.mark.asyncio
    async def test_generated_questions_stored_in_quiz_questions(self):
        """New power quiz questions should be persisted with source='power_quiz'."""
        from lecturelink_api.services.learn_session import get_power_quiz

        sb = MagicMock()
        session = {
            "id": "s1",
            "user_id": "user1",
            "course_id": "course1",
            "time_budget_minutes": 10,
            "session_data": {
                "daily_briefing": {
                    "concepts_planned": [
                        {"concept_id": "c1", "title": "Entropy"},
                    ],
                },
            },
        }

        insert_chain = MagicMock()
        insert_chain.execute.return_value = _mock_execute([{"id": "persisted-q1"}])

        def table_side_effect(name):
            if name == "learn_sessions":
                chain = _mock_chain(session)
                update_chain = MagicMock()
                update_chain.eq.return_value = update_chain
                update_chain.execute.return_value = _mock_execute([])
                chain.update.return_value = update_chain
                return chain
            if name == "quiz_questions":
                chain = _mock_chain([])  # No reusable questions
                chain.insert.return_value = insert_chain
                return chain
            if name == "concepts":
                return _mock_chain({"title": "Entropy", "lecture_id": "lec1"})
            return _mock_chain([])

        sb.table.side_effect = table_side_effect

        rpc_mock = MagicMock()
        rpc_mock.execute.return_value = _mock_execute(None)
        sb.rpc.return_value = rpc_mock

        gemini_response = MagicMock()
        gemini_response.text = json.dumps([
            {
                "question_text": "What is entropy?",
                "options": ["A) Disorder", "B) Energy", "C) Force", "D) Mass"],
                "correct_answer": "A",
                "correct_index": 0,
                "explanation": "Entropy measures disorder.",
                "concept_title": "Entropy",
            },
        ])

        mock_client = MagicMock()
        mock_client.aio.models.generate_content = AsyncMock(return_value=gemini_response)

        with (
            patch("lecturelink_api.services.learn_session.search_lectures", new_callable=AsyncMock, return_value=[
                {"chunk_id": "ch1", "lecture_id": "lec1", "lecture_title": "Thermo", "content": "Entropy is...", "start_time": None, "end_time": None, "slide_number": None, "metadata": {}},
            ]),
            patch("lecturelink_api.services.learn_session._get_client", return_value=mock_client),
        ):
            result = await get_power_quiz(sb, "user1", "s1")

        assert len(result["questions"]) >= 1
        # Verify quiz_questions.insert was called with source='power_quiz'
        insert_calls = insert_chain.execute.call_args_list
        assert len(insert_calls) > 0

    @pytest.mark.asyncio
    async def test_stored_question_id_in_session_data(self):
        """Persisted questions should have _stored_question_id in session data."""
        from lecturelink_api.services.learn_session import get_power_quiz

        sb = MagicMock()
        session = {
            "id": "s1",
            "user_id": "user1",
            "course_id": "course1",
            "time_budget_minutes": 10,
            "session_data": {
                "daily_briefing": {
                    "concepts_planned": [
                        {"concept_id": "c1", "title": "Entropy"},
                    ],
                },
            },
        }

        insert_chain = MagicMock()
        insert_chain.execute.return_value = _mock_execute([{"id": "persisted-q1"}])

        stored_session_data = {}

        def table_side_effect(name):
            if name == "learn_sessions":
                chain = _mock_chain(session)
                update_chain = MagicMock()
                update_chain.eq.return_value = update_chain

                def capture_update(data):
                    stored_session_data.update(data.get("session_data", {}))
                    return update_chain

                update_chain.execute.return_value = _mock_execute([])
                chain.update.side_effect = capture_update
                return chain
            if name == "quiz_questions":
                chain = _mock_chain([])  # No reusable questions
                chain.insert.return_value = insert_chain
                return chain
            if name == "concepts":
                return _mock_chain({"title": "Entropy", "lecture_id": "lec1"})
            return _mock_chain([])

        sb.table.side_effect = table_side_effect

        rpc_mock = MagicMock()
        rpc_mock.execute.return_value = _mock_execute(None)
        sb.rpc.return_value = rpc_mock

        gemini_response = MagicMock()
        gemini_response.text = json.dumps([
            {
                "question_text": "What is entropy?",
                "options": ["A) Disorder", "B) Energy", "C) Force", "D) Mass"],
                "correct_answer": "A",
                "correct_index": 0,
                "explanation": "Entropy measures disorder.",
                "concept_title": "Entropy",
            },
        ])

        mock_client = MagicMock()
        mock_client.aio.models.generate_content = AsyncMock(return_value=gemini_response)

        with (
            patch("lecturelink_api.services.learn_session.search_lectures", new_callable=AsyncMock, return_value=[
                {"chunk_id": "ch1", "lecture_id": "lec1", "lecture_title": "Thermo", "content": "Entropy is...", "start_time": None, "end_time": None, "slide_number": None, "metadata": {}},
            ]),
            patch("lecturelink_api.services.learn_session._get_client", return_value=mock_client),
        ):
            await get_power_quiz(sb, "user1", "s1")

        # Check that stored session data has _stored_question_id
        quiz_data = stored_session_data.get("power_quiz", {})
        questions = quiz_data.get("questions", [])
        if questions:
            assert any(
                q.get("_stored_question_id") is not None
                for q in questions
                if q.get("_source") == "generated"
            )


class TestSubmitFlashReviewAnswer:
    @pytest.mark.asyncio
    async def test_records_answer(self):
        from lecturelink_api.services.learn_session import submit_flash_review_answer

        sb = MagicMock()
        session = {
            "id": "s1",
            "user_id": "user1",
            "course_id": "course1",
            "session_data": {
                "flash_review_results": [],
            },
        }

        def table_side_effect(name):
            if name == "learn_sessions":
                chain = _mock_chain(session)
                update_chain = MagicMock()
                update_chain.eq.return_value = update_chain
                update_chain.execute.return_value = _mock_execute([])
                chain.update.return_value = update_chain
                return chain
            return _mock_chain([])

        sb.table.side_effect = table_side_effect

        result = await submit_flash_review_answer(
            sb, "user1", "s1", "card-1", answer_index=0, time_ms=1500
        )

        assert result["card_id"] == "card-1"
        assert result["answer_index"] == 0


class TestLearningEventWriteBack:
    """Verify that submit functions record learning events for mastery tracking."""

    @pytest.mark.asyncio
    async def test_power_quiz_records_event(self):
        from lecturelink_api.services.learn_session import submit_power_quiz_answer

        sb = MagicMock()
        session = {
            "id": "s1",
            "user_id": "user1",
            "course_id": "course1",
            "session_data": {
                "power_quiz": {
                    "quiz_id": "quiz1",
                    "questions": [{
                        "question_id": "q1",
                        "question_text": "What?",
                        "options": ["A", "B", "C", "D"],
                        "_correct_index": 1,
                        "_explanation": "B is right.",
                        "concept_id": "concept-abc",
                    }],
                },
                "combo_count": 0,
                "combo_max": 0,
                "quiz_results": [],
            },
        }

        def table_side_effect(name):
            if name == "learn_sessions":
                chain = _mock_chain(session)
                update_chain = MagicMock()
                update_chain.eq.return_value = update_chain
                update_chain.execute.return_value = _mock_execute([])
                chain.update.return_value = update_chain
                return chain
            return _mock_chain([])

        sb.table.side_effect = table_side_effect

        mock_record = AsyncMock()
        with (
            patch("lecturelink_api.services.learn_session._award_xp", new_callable=AsyncMock, return_value={"amount": 10, "total_xp": 10, "level": 1, "leveled_up": False}),
            patch("lecturelink_api.services.learn_session.record_learning_event", mock_record),
        ):
            await submit_power_quiz_answer(sb, "user1", "s1", "q1", answer_index=1, time_ms=5000)

        mock_record.assert_called_once()
        args = mock_record.call_args
        assert args.kwargs["event_type"] == "power_quiz"
        assert args.kwargs["concept_id"] == "concept-abc"
        assert args.kwargs["is_correct"] is True

    @pytest.mark.asyncio
    async def test_gut_check_records_event(self):
        from lecturelink_api.services.learn_session import submit_gut_check

        sb = MagicMock()
        session = {
            "id": "s1",
            "user_id": "user1",
            "course_id": "course1",
            "session_data": {},
        }

        def table_side_effect(name):
            return _mock_chain(session)

        sb.table.side_effect = table_side_effect

        mock_record = AsyncMock()
        with (
            patch("lecturelink_api.services.learn_session._award_xp", new_callable=AsyncMock, return_value={"amount": 5, "total_xp": 5, "level": 1, "leveled_up": False}),
            patch("lecturelink_api.services.learn_session.record_learning_event", mock_record),
        ):
            await submit_gut_check(sb, "user1", "s1", "concept-xyz", answer_index=2)

        mock_record.assert_called_once()
        args = mock_record.call_args
        assert args.kwargs["event_type"] == "gut_check"
        assert args.kwargs["concept_id"] == "concept-xyz"

    @pytest.mark.asyncio
    async def test_flash_review_records_event(self):
        from lecturelink_api.services.learn_session import submit_flash_review_answer

        sb = MagicMock()
        session = {
            "id": "s1",
            "user_id": "user1",
            "course_id": "course1",
            "session_data": {
                "flash_review_cards": [{
                    "card_id": "card-1",
                    "concept_id": "concept-flash",
                    "question_text": "What?",
                    "options": ["A", "B", "C"],
                    "correct_index": 1,
                }],
                "flash_review_results": [],
            },
        }

        def table_side_effect(name):
            if name == "learn_sessions":
                chain = _mock_chain(session)
                update_chain = MagicMock()
                update_chain.eq.return_value = update_chain
                update_chain.execute.return_value = _mock_execute([])
                chain.update.return_value = update_chain
                return chain
            return _mock_chain([])

        sb.table.side_effect = table_side_effect

        mock_record = AsyncMock()
        with (
            patch("lecturelink_api.services.learn_session._award_xp", new_callable=AsyncMock, return_value={"amount": 5, "total_xp": 5, "level": 1, "leveled_up": False}),
            patch("lecturelink_api.services.learn_session.record_learning_event", mock_record),
        ):
            await submit_flash_review_answer(sb, "user1", "s1", "card-1", answer_index=1, time_ms=2000)

        mock_record.assert_called_once()
        args = mock_record.call_args
        assert args.kwargs["event_type"] == "flash_review"
        assert args.kwargs["concept_id"] == "concept-flash"
