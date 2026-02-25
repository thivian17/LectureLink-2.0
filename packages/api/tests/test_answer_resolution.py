"""Tests for _resolve_correct_answer and _resolve_correct_option_index helpers."""

from __future__ import annotations

from lecturelink_api.routers.quizzes import (
    _resolve_correct_answer,
    _resolve_correct_option_index,
)

# ── Shared fixtures ───────────────────────────────────────────────

DICT_OPTIONS = [
    {"label": "A", "text": "A region of space", "is_correct": True},
    {"label": "B", "text": "A heat engine", "is_correct": False},
    {"label": "C", "text": "A chemical compound", "is_correct": False},
    {"label": "D", "text": "A physical force", "is_correct": False},
]

DICT_OPTIONS_C_CORRECT = [
    {"label": "A", "text": "Option Alpha"},
    {"label": "B", "text": "Option Beta"},
    {"label": "C", "text": "Option Gamma", "is_correct": True},
    {"label": "D", "text": "Option Delta"},
]

PLAIN_STRING_OPTIONS = ["Option 1", "Option 2", "Option 3", "Option 4"]

TF_OPTIONS = [
    {"text": "True", "is_correct": True},
    {"text": "False", "is_correct": False},
]

TF_OPTIONS_FALSE = [
    {"text": "True", "is_correct": False},
    {"text": "False", "is_correct": True},
]

TF_OPTIONS_NO_FLAG = [
    {"text": "True"},
    {"text": "False"},
]


# ── _resolve_correct_answer ──────────────────────────────────────


class TestResolveCorrectAnswer:
    def test_already_option_text(self):
        result = _resolve_correct_answer(DICT_OPTIONS, "A region of space")
        assert result == "A region of space"

    def test_label_resolves_to_text(self):
        result = _resolve_correct_answer(DICT_OPTIONS, "A")
        assert result == "A region of space"

    def test_label_lowercase(self):
        result = _resolve_correct_answer(DICT_OPTIONS, "a")
        assert result == "A region of space"

    def test_label_dot_text_format(self):
        result = _resolve_correct_answer(DICT_OPTIONS, "A. A region of space")
        assert result == "A region of space"

    def test_label_paren_text_format(self):
        result = _resolve_correct_answer(DICT_OPTIONS, "A) A region of space")
        assert result == "A region of space"

    def test_fallback_to_is_correct(self):
        result = _resolve_correct_answer(DICT_OPTIONS, "garbage answer")
        assert result == "A region of space"

    def test_none_correct_answer(self):
        assert _resolve_correct_answer(DICT_OPTIONS, None) is None

    def test_none_options(self):
        assert _resolve_correct_answer(None, "some answer") == "some answer"

    def test_plain_string_options_with_label(self):
        result = _resolve_correct_answer(PLAIN_STRING_OPTIONS, "A")
        assert result == "Option 1"

    def test_plain_string_options_direct_match(self):
        result = _resolve_correct_answer(PLAIN_STRING_OPTIONS, "Option 3")
        assert result == "Option 3"

    def test_c_correct(self):
        result = _resolve_correct_answer(DICT_OPTIONS_C_CORRECT, "C")
        assert result == "Option Gamma"


# ── _resolve_correct_option_index ────────────────────────────────


class TestResolveCorrectOptionIndex:
    """Tests for _resolve_correct_option_index."""

    # Strategy 1: is_correct flag

    def test_is_correct_flag_first_option(self):
        assert _resolve_correct_option_index(DICT_OPTIONS, "irrelevant") == 0

    def test_is_correct_flag_third_option(self):
        assert _resolve_correct_option_index(DICT_OPTIONS_C_CORRECT, "irrelevant") == 2

    def test_is_correct_flag_true_false(self):
        assert _resolve_correct_option_index(TF_OPTIONS, "True") == 0
        assert _resolve_correct_option_index(TF_OPTIONS_FALSE, "False") == 1

    # Strategy 2: text match (no is_correct flags)

    def test_exact_text_match(self):
        assert _resolve_correct_option_index(PLAIN_STRING_OPTIONS, "Option 3") == 2

    def test_case_insensitive_text_match(self):
        assert _resolve_correct_option_index(PLAIN_STRING_OPTIONS, "option 1") == 0

    # Strategy 3: label match

    def test_label_match(self):
        assert _resolve_correct_option_index(PLAIN_STRING_OPTIONS, "B") == 1

    def test_label_match_lowercase(self):
        assert _resolve_correct_option_index(PLAIN_STRING_OPTIONS, "d") == 3

    # Strategy 4: "A. text" format

    def test_label_dot_text(self):
        assert _resolve_correct_option_index(PLAIN_STRING_OPTIONS, "C. Option 3") == 2

    def test_label_paren_text(self):
        assert _resolve_correct_option_index(PLAIN_STRING_OPTIONS, "A) Option 1") == 0

    # Strategy 5: true_false normalization

    def test_true_false_true_variants(self):
        for val in ("true", "t", "True", "TRUE", "yes"):
            assert (
                _resolve_correct_option_index(TF_OPTIONS_NO_FLAG, val, "true_false")
                == 0
            ), f"Failed for {val!r}"

    def test_true_false_false_variants(self):
        for val in ("false", "f", "False", "FALSE", "no"):
            assert (
                _resolve_correct_option_index(TF_OPTIONS_NO_FLAG, val, "true_false")
                == 1
            ), f"Failed for {val!r}"

    # Edge cases

    def test_none_options_returns_none(self):
        assert _resolve_correct_option_index(None, "anything") is None

    def test_empty_options_returns_none(self):
        assert _resolve_correct_option_index([], "anything") is None

    def test_none_correct_answer_no_flag(self):
        assert _resolve_correct_option_index(PLAIN_STRING_OPTIONS, None) is None

    def test_no_match_returns_none(self):
        assert _resolve_correct_option_index(PLAIN_STRING_OPTIONS, "nonexistent") is None

    def test_multiple_is_correct_returns_first(self):
        opts = [
            {"text": "First", "is_correct": True},
            {"text": "Second", "is_correct": True},
        ]
        assert _resolve_correct_option_index(opts, "Second") == 0
