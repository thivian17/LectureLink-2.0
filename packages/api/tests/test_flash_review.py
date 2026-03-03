"""Tests for the flash review service."""

from __future__ import annotations

import json
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
    for method in ("select", "eq", "in_", "order", "limit", "single"):
        getattr(chain, method).return_value = chain
    return chain


def _make_mastery_row(
    concept_id="c1",
    title="Entropy",
    total_attempts=10,
    accuracy=0.6,
    recent_accuracy=0.8,
    **kw,
):
    return {
        "concept_id": concept_id,
        "concept_title": title,
        "total_attempts": total_attempts,
        "correct_attempts": kw.get("correct_attempts", 6),
        "accuracy": accuracy,
        "recent_accuracy": recent_accuracy,
        "trend": kw.get("trend", "stable"),
    }


class TestGetFlashReviewCards:
    @pytest.mark.asyncio
    async def test_prioritizes_low_mastery_concepts(self):
        from lecturelink_api.services.flash_review import get_flash_review_cards

        sb = MagicMock()

        mastery_data = [
            _make_mastery_row(concept_id="high", accuracy=0.9, recent_accuracy=0.9),
            _make_mastery_row(concept_id="low", accuracy=0.2, recent_accuracy=0.3),
        ]
        rpc_mock = MagicMock()
        rpc_mock.execute.return_value = _mock_execute(mastery_data)
        sb.rpc.return_value = rpc_mock

        # Mock quiz_questions table — return existing question for "low"
        existing_q = {
            "id": "q1",
            "question_text": "What is entropy?",
            "options": [
                {"text": "Disorder", "is_correct": True},
                {"text": "Energy", "is_correct": False},
            ],
            "correct_answer": "A",
            "question_type": "mcq",
        }

        def table_side_effect(name):
            if name == "quiz_questions":
                return _mock_chain([existing_q])
            return _mock_chain([])

        sb.table.side_effect = table_side_effect

        cards = await get_flash_review_cards(sb, "user1", "course1", count=2)

        # Should get cards (low mastery first)
        assert len(cards) >= 1
        assert cards[0]["concept_id"] == "low"

    @pytest.mark.asyncio
    async def test_reuses_existing_quiz_questions(self):
        from lecturelink_api.services.flash_review import get_flash_review_cards

        sb = MagicMock()

        mastery_data = [
            _make_mastery_row(concept_id="c1", accuracy=0.5, recent_accuracy=0.5),
        ]
        rpc_mock = MagicMock()
        rpc_mock.execute.return_value = _mock_execute(mastery_data)
        sb.rpc.return_value = rpc_mock

        existing_q = {
            "id": "q1",
            "question_text": "Define entropy",
            "options": ["Disorder", "Energy", "Force"],
            "correct_answer": "Disorder",
            "question_type": "mcq",
        }

        def table_side_effect(name):
            if name == "quiz_questions":
                return _mock_chain([existing_q])
            return _mock_chain([])

        sb.table.side_effect = table_side_effect

        cards = await get_flash_review_cards(sb, "user1", "course1", count=1)

        assert len(cards) == 1
        assert cards[0]["source"] == "existing"
        assert cards[0]["question_text"] == "Define entropy"

    @pytest.mark.asyncio
    async def test_gemini_fallback_when_no_existing_questions(self):
        from lecturelink_api.services.flash_review import get_flash_review_cards

        sb = MagicMock()

        mastery_data = [
            _make_mastery_row(concept_id="c1", accuracy=0.5, recent_accuracy=0.5),
        ]
        rpc_mock = MagicMock()
        rpc_mock.execute.return_value = _mock_execute(mastery_data)
        sb.rpc.return_value = rpc_mock

        # No existing questions
        def table_side_effect(name):
            return _mock_chain([])

        sb.table.side_effect = table_side_effect

        mock_response = MagicMock()
        mock_response.text = json.dumps({
            "question_text": "What describes entropy?",
            "options": ["Disorder", "Order"],
            "correct_index": 0,
        })

        mock_client = MagicMock()
        mock_client.aio.models.generate_content = AsyncMock(return_value=mock_response)

        with (
            patch(
                "lecturelink_api.services.flash_review._get_client",
                return_value=mock_client,
            ),
            patch(
                "lecturelink_api.services.flash_review.search_lectures",
                new_callable=AsyncMock,
                return_value=[{"content": "Entropy is disorder", "lecture_title": "L1"}],
            ),
        ):
            cards = await get_flash_review_cards(sb, "user1", "course1", count=1)

        assert len(cards) == 1
        assert cards[0]["source"] == "generated"
        assert cards[0]["question_text"] == "What describes entropy?"

    @pytest.mark.asyncio
    async def test_new_user_gets_cards_from_session_concepts(self):
        """New users (0 attempts) should get generated cards when session_concepts provided."""
        from lecturelink_api.services.flash_review import get_flash_review_cards

        sb = MagicMock()

        # All concepts have 0 attempts
        mastery_data = [
            _make_mastery_row(concept_id="c1", total_attempts=0),
        ]
        rpc_mock = MagicMock()
        rpc_mock.execute.return_value = _mock_execute(mastery_data)
        sb.rpc.return_value = rpc_mock

        existing_q = {
            "id": "q1",
            "question_text": "What is entropy?",
            "options": ["Disorder", "Energy"],
            "correct_answer": "Disorder",
            "question_type": "mcq",
        }

        def table_side_effect(name):
            if name == "quiz_questions":
                return _mock_chain([existing_q])
            return _mock_chain([])

        sb.table.side_effect = table_side_effect

        session_concepts = [
            {"concept_id": "c1", "concept_title": "Entropy"},
        ]
        cards = await get_flash_review_cards(
            sb, "user1", "course1", count=5, session_concepts=session_concepts,
        )
        assert len(cards) >= 1
        assert cards[0]["concept_id"] == "c1"

    @pytest.mark.asyncio
    async def test_returns_empty_when_no_concepts_at_all(self):
        """With no mastery, no session_concepts, and no course concepts, return empty."""
        from lecturelink_api.services.flash_review import get_flash_review_cards

        sb = MagicMock()

        mastery_data = [
            _make_mastery_row(concept_id="c1", total_attempts=0),
        ]
        rpc_mock = MagicMock()
        rpc_mock.execute.return_value = _mock_execute(mastery_data)
        sb.rpc.return_value = rpc_mock

        def table_side_effect(name):
            if name == "concepts":
                return _mock_chain([])
            return _mock_chain([])

        sb.table.side_effect = table_side_effect

        cards = await get_flash_review_cards(sb, "user1", "course1", count=5)
        assert cards == []

    @pytest.mark.asyncio
    async def test_respects_count_limit(self):
        from lecturelink_api.services.flash_review import get_flash_review_cards

        sb = MagicMock()

        mastery_data = [
            _make_mastery_row(concept_id=f"c{i}", accuracy=0.3, recent_accuracy=0.3)
            for i in range(10)
        ]
        rpc_mock = MagicMock()
        rpc_mock.execute.return_value = _mock_execute(mastery_data)
        sb.rpc.return_value = rpc_mock

        existing_q = {
            "id": "q1",
            "question_text": "Test?",
            "options": ["A", "B"],
            "correct_answer": "A",
            "question_type": "mcq",
        }

        def table_side_effect(name):
            if name == "quiz_questions":
                return _mock_chain([existing_q])
            return _mock_chain([])

        sb.table.side_effect = table_side_effect

        cards = await get_flash_review_cards(sb, "user1", "course1", count=3)
        assert len(cards) <= 3


class TestGradeFlashReview:
    def test_correct_answer(self):
        from lecturelink_api.services.flash_review import grade_flash_review

        card = {
            "correct_index": 1,
            "options": ["Wrong", "Correct", "Also Wrong"],
        }
        result = grade_flash_review(card, 1)
        assert result["correct"] is True
        assert result["correct_answer"] == "Correct"
        assert result["xp_earned"] == 5

    def test_incorrect_answer(self):
        from lecturelink_api.services.flash_review import grade_flash_review

        card = {
            "correct_index": 0,
            "options": ["Right", "Wrong"],
        }
        result = grade_flash_review(card, 1)
        assert result["correct"] is False
        assert result["correct_answer"] == "Right"
        assert result["xp_earned"] == 2

    def test_deterministic_grading(self):
        from lecturelink_api.services.flash_review import grade_flash_review

        card = {
            "correct_index": 2,
            "options": ["A", "B", "C"],
        }
        # Same input always gives same output
        r1 = grade_flash_review(card, 2)
        r2 = grade_flash_review(card, 2)
        assert r1 == r2
        assert r1["correct"] is True

        r3 = grade_flash_review(card, 0)
        assert r3["correct"] is False


class TestGenerateFlashCard:
    @pytest.mark.asyncio
    async def test_generates_valid_card(self):
        from lecturelink_api.services.flash_review import generate_flash_card

        mock_response = MagicMock()
        mock_response.text = json.dumps({
            "question_text": "What is X?",
            "options": ["A", "B", "C"],
            "correct_index": 1,
        })

        mock_client = MagicMock()
        mock_client.aio.models.generate_content = AsyncMock(return_value=mock_response)

        with patch(
            "lecturelink_api.services.flash_review._get_client",
            return_value=mock_client,
        ):
            card = await generate_flash_card(
                {"concept_id": "c1", "concept_title": "Test"},
                [{"content": "Test content"}],
            )

        assert card is not None
        assert card["question_text"] == "What is X?"
        assert len(card["options"]) == 3
        assert card["correct_index"] == 1
        assert card["card_id"]  # Has a UUID

    @pytest.mark.asyncio
    async def test_returns_none_on_failure(self):
        from lecturelink_api.services.flash_review import generate_flash_card

        mock_client = MagicMock()
        mock_client.aio.models.generate_content = AsyncMock(
            side_effect=Exception("API error")
        )

        with patch(
            "lecturelink_api.services.flash_review._get_client",
            return_value=mock_client,
        ):
            card = await generate_flash_card(
                {"concept_id": "c1", "concept_title": "Test"},
                [],
            )

        assert card is None
