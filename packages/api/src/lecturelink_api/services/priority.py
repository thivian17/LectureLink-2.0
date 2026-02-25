"""Priority scoring weight vectors based on course mode.

The Supabase RPC function ``get_study_priorities`` (see migration 006b)
handles scoring in SQL.  This module provides the same weight constants
in Python for use by application-level scoring or tests.
"""

from __future__ import annotations

ACTIVE_MODE_WEIGHTS: dict[str, float] = {
    "deadline_urgency": 0.4,
    "grade_impact": 0.3,
    "mastery_gap": 0.2,
    "fsrs_due": 0.1,
}

REVIEW_MODE_WEIGHTS: dict[str, float] = {
    "deadline_urgency": 0.0,
    "grade_impact": 0.0,
    "mastery_gap": 0.6,
    "fsrs_due": 0.4,
}


def get_priority_weights(mode: str = "active") -> dict[str, float]:
    """Return priority scoring weights based on course mode."""
    if mode == "review":
        return REVIEW_MODE_WEIGHTS
    return ACTIVE_MODE_WEIGHTS
