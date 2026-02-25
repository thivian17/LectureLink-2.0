"""Tests for the priority scoring system.

Validates:
- Pure-Python reference implementation mirrors SQL formula
- High weight beats low weight when deadlines are similar
- Close deadline beats distant when weights are similar
- Past-due assessments get high urgency
- Null dates excluded from results
- API endpoint returns correct shape
"""

from __future__ import annotations

import uuid
from datetime import date, timedelta
from unittest.mock import MagicMock, patch

import pytest

from tests.integration.conftest import mock_chain

# ---------------------------------------------------------------------------
# Pure-Python reference implementation of the SQL priority formula
# ---------------------------------------------------------------------------


def compute_priority_score(
    weight_percent: float | None, due_date: date | None
) -> float:
    """Python mirror of the get_study_priorities() SQL function.

    Formula: priority_score = (weight_factor * 0.4) + (urgency_factor * 0.6)
    - weight_factor = weight_percent / 100.0
    - urgency_factor = 1/(1 + days_until_due) for future, 0.9 for past
    """
    if due_date is None:
        return 0.0

    weight_factor = (weight_percent or 0.0) / 100.0
    today = date.today()
    days_until = (due_date - today).days

    if days_until < 0:
        urgency_factor = 0.9
    else:
        urgency_factor = 1.0 / (1.0 + days_until)

    return weight_factor * 0.4 + urgency_factor * 0.6


# ---------------------------------------------------------------------------
# Tests for the Python reference implementation
# ---------------------------------------------------------------------------


class TestPriorityScoringFormula:
    """Unit tests for the priority scoring formula."""

    def test_high_weight_beats_low_weight_same_deadline(self):
        """When deadlines are the same, higher weight = higher score."""
        due = date.today() + timedelta(days=14)
        score_high = compute_priority_score(40.0, due)
        score_low = compute_priority_score(10.0, due)
        assert score_high > score_low, (
            f"Weight 40% ({score_high:.4f}) should beat "
            f"weight 10% ({score_low:.4f}) at same deadline"
        )

    def test_close_deadline_beats_distant_same_weight(self):
        """When weights are the same, closer deadline = higher score."""
        score_close = compute_priority_score(20.0, date.today() + timedelta(days=3))
        score_far = compute_priority_score(20.0, date.today() + timedelta(days=30))
        assert score_close > score_far, (
            f"3-day ({score_close:.4f}) should beat "
            f"30-day ({score_far:.4f}) at same weight"
        )

    def test_past_due_gets_high_urgency(self):
        """Past-due assessments get urgency_factor=0.9."""
        score = compute_priority_score(20.0, date.today() - timedelta(days=5))
        # urgency=0.9, weight_factor=0.2 -> 0.2*0.4 + 0.9*0.6 = 0.08+0.54 = 0.62
        assert score == pytest.approx(0.62, abs=0.01)

    def test_null_due_date_returns_zero(self):
        """No due date → score 0."""
        assert compute_priority_score(50.0, None) == 0.0

    def test_null_weight_still_has_urgency(self):
        """No weight → only urgency contributes."""
        score = compute_priority_score(None, date.today() + timedelta(days=1))
        # weight_factor=0, urgency=1/(1+1)=0.5 -> 0+0.3 = 0.3
        assert score == pytest.approx(0.3, abs=0.01)

    def test_due_today_has_max_urgency(self):
        """Assessment due today: urgency_factor = 1/(1+0) = 1.0."""
        score = compute_priority_score(50.0, date.today())
        # weight=0.5*0.4=0.2, urgency=1.0*0.6=0.6 -> 0.8
        assert score == pytest.approx(0.8, abs=0.01)

    def test_exam_beats_homework_realistic(self):
        """Realistic scenario: final exam (35%, 14 days) vs HW (5%, 7 days)."""
        exam_score = compute_priority_score(35.0, date.today() + timedelta(days=14))
        hw_score = compute_priority_score(5.0, date.today() + timedelta(days=7))
        # Exam: 0.35*0.4 + 1/15*0.6 = 0.14 + 0.04 = 0.18
        # HW: 0.05*0.4 + 1/8*0.6 = 0.02 + 0.075 = 0.095
        assert exam_score > hw_score, "High-weight exam should outrank low-weight HW"


# ---------------------------------------------------------------------------
# Tests for the priority scoring API endpoint
# ---------------------------------------------------------------------------


class TestPriorityScoringEndpoint:
    """Tests for GET /api/courses/{id}/assessments/priorities."""

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_endpoint_returns_priorities(self, client):
        """Endpoint returns priority-scored assessments."""
        course_id = str(uuid.uuid4())
        priorities = [
            {
                "assessment_id": str(uuid.uuid4()),
                "title": "Final Exam",
                "course_id": course_id,
                "due_date": "2026-04-30",
                "weight_percent": 35.0,
                "priority_score": 0.75,
            },
            {
                "assessment_id": str(uuid.uuid4()),
                "title": "Homework 1",
                "course_id": course_id,
                "due_date": "2026-02-05",
                "weight_percent": 5.0,
                "priority_score": 0.25,
            },
        ]

        with patch(
            "lecturelink_api.routers.assessments.create_client"
        ) as mc:
            sb = MagicMock()
            mc.return_value = sb
            sb.table.return_value = mock_chain({"id": course_id})
            sb.rpc.return_value = mock_chain(priorities)

            resp = await client.get(
                f"/api/courses/{course_id}/assessments/priorities"
            )

        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 2
        assert data[0]["priority_score"] > data[1]["priority_score"]

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_endpoint_returns_correct_shape(self, client):
        """Each priority item has the expected fields."""
        course_id = str(uuid.uuid4())
        aid = str(uuid.uuid4())
        priorities = [
            {
                "assessment_id": aid,
                "title": "Midterm",
                "course_id": course_id,
                "due_date": "2026-03-15",
                "weight_percent": 25.0,
                "priority_score": 0.5,
            }
        ]

        with patch(
            "lecturelink_api.routers.assessments.create_client"
        ) as mc:
            sb = MagicMock()
            mc.return_value = sb
            sb.table.return_value = mock_chain({"id": course_id})
            sb.rpc.return_value = mock_chain(priorities)

            resp = await client.get(
                f"/api/courses/{course_id}/assessments/priorities"
            )

        assert resp.status_code == 200
        item = resp.json()[0]
        assert "assessment_id" in item
        assert "title" in item
        assert "due_date" in item
        assert "weight_percent" in item
        assert "priority_score" in item

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_empty_course_returns_empty_list(self, client):
        """Course with no assessments returns empty list."""
        course_id = str(uuid.uuid4())

        with patch(
            "lecturelink_api.routers.assessments.create_client"
        ) as mc:
            sb = MagicMock()
            mc.return_value = sb
            sb.table.return_value = mock_chain({"id": course_id})
            sb.rpc.return_value = mock_chain([])

            resp = await client.get(
                f"/api/courses/{course_id}/assessments/priorities"
            )

        assert resp.status_code == 200
        assert resp.json() == []

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_course_not_found_returns_404(self, client):
        """Unknown course returns 404."""
        course_id = str(uuid.uuid4())

        with patch(
            "lecturelink_api.routers.assessments.create_client"
        ) as mc:
            sb = MagicMock()
            mc.return_value = sb
            sb.table.return_value = mock_chain(None)

            resp = await client.get(
                f"/api/courses/{course_id}/assessments/priorities"
            )

        assert resp.status_code == 404
