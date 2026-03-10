"""Tests for the BKT mastery service."""

import pytest

from lecturelink_api.services.mastery import (
    BKTState,
    DEFAULT_P_GUESS,
    DEFAULT_P_MASTERY,
    DEFAULT_P_SLIP,
    DEFAULT_P_TRANSIT,
    bkt_update,
    compute_mastery,
    mastery_tier,
)


def _default_state(p_mastery: float = DEFAULT_P_MASTERY) -> BKTState:
    return BKTState(
        concept_id="test-concept",
        p_mastery=p_mastery,
        p_transit=DEFAULT_P_TRANSIT,
        p_guess=DEFAULT_P_GUESS,
        p_slip=DEFAULT_P_SLIP,
        total_attempts=0,
        correct_attempts=0,
    )


class TestBKTUpdate:
    def test_correct_answer_increases_mastery(self):
        state = _default_state(0.3)
        updated = bkt_update(state, is_correct=True)
        assert updated.p_mastery > state.p_mastery

    def test_incorrect_answer_decreases_mastery(self):
        state = _default_state(0.5)
        updated = bkt_update(state, is_correct=False)
        assert updated.p_mastery < state.p_mastery

    def test_mastery_clamped_to_lower_bound(self):
        """Even with many wrong answers, p_mastery should not go below 0.01."""
        state = _default_state(0.02)
        for _ in range(50):
            state = bkt_update(state, is_correct=False)
        assert state.p_mastery >= 0.01

    def test_mastery_clamped_to_upper_bound(self):
        """Even with many correct answers, p_mastery should not exceed 0.99."""
        state = _default_state(0.98)
        for _ in range(50):
            state = bkt_update(state, is_correct=True)
        assert state.p_mastery <= 0.99

    def test_attempt_count_increments(self):
        state = _default_state()
        updated = bkt_update(state, is_correct=True)
        assert updated.total_attempts == 1
        assert updated.correct_attempts == 1

        updated2 = bkt_update(updated, is_correct=False)
        assert updated2.total_attempts == 2
        assert updated2.correct_attempts == 1

    def test_concept_id_preserved(self):
        state = _default_state()
        updated = bkt_update(state, is_correct=True)
        assert updated.concept_id == state.concept_id

    def test_parameters_preserved(self):
        state = _default_state()
        updated = bkt_update(state, is_correct=True)
        assert updated.p_transit == state.p_transit
        assert updated.p_guess == state.p_guess
        assert updated.p_slip == state.p_slip

    def test_repeated_correct_converges_high(self):
        """Many correct answers should push mastery toward the upper bound."""
        state = _default_state(0.3)
        for _ in range(30):
            state = bkt_update(state, is_correct=True)
        assert state.p_mastery > 0.9

    def test_repeated_incorrect_converges_low(self):
        """Many incorrect answers should push mastery toward the lower bound."""
        state = _default_state(0.7)
        for _ in range(30):
            state = bkt_update(state, is_correct=False)
        # Should be low but not below clamp
        assert state.p_mastery < 0.15
        assert state.p_mastery >= 0.01

    def test_mastery_always_valid_probability(self):
        """After any sequence of updates, mastery must be in [0.01, 0.99]."""
        import random

        random.seed(42)
        state = _default_state(0.5)
        for _ in range(100):
            state = bkt_update(state, is_correct=random.choice([True, False]))
            assert 0.01 <= state.p_mastery <= 0.99

    def test_high_mastery_correct_stays_high(self):
        """A student who knows the material (high p) answering correctly stays high."""
        state = _default_state(0.9)
        updated = bkt_update(state, is_correct=True)
        assert updated.p_mastery >= 0.9

    def test_low_mastery_incorrect_stays_low(self):
        """A student with low mastery answering incorrectly stays low."""
        state = _default_state(0.1)
        updated = bkt_update(state, is_correct=False)
        assert updated.p_mastery < 0.15

    def test_different_guess_probability(self):
        """Short answer questions have lower p_guess = 0.15."""
        state = BKTState(
            concept_id="test",
            p_mastery=0.3,
            p_transit=0.1,
            p_guess=0.15,
            p_slip=0.1,
            total_attempts=0,
            correct_attempts=0,
        )
        updated = bkt_update(state, is_correct=True)
        # With lower p_guess, a correct answer is stronger evidence of knowing
        default_updated = bkt_update(_default_state(0.3), is_correct=True)
        assert updated.p_mastery > default_updated.p_mastery


class TestComputeMastery:
    def test_zero_attempts_returns_zero(self):
        assert compute_mastery(0.8, 0.9, 0) == 0.0

    def test_weighted_formula(self):
        result = compute_mastery(1.0, 1.0, 5)
        assert result == 1.0

    def test_mixed_scores(self):
        result = compute_mastery(0.8, 0.6, 10)
        expected = round(0.8 * 0.6 + 0.6 * 0.4, 4)
        assert result == expected

    def test_rounding(self):
        result = compute_mastery(0.333, 0.777, 3)
        expected = round(0.333 * 0.6 + 0.777 * 0.4, 4)
        assert result == expected

    def test_zero_accuracy(self):
        assert compute_mastery(0.0, 0.0, 5) == 0.0


class TestMasteryTier:
    @pytest.mark.parametrize("score,expected", [
        (0.0, "novice"),
        (0.29, "novice"),
        (0.3, "developing"),
        (0.59, "developing"),
        (0.6, "proficient"),
        (0.79, "proficient"),
        (0.8, "advanced"),
        (1.0, "advanced"),
    ])
    def test_tier_boundaries(self, score, expected):
        assert mastery_tier(score) == expected
