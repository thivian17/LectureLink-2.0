"""Tests for the concept mapper agent.

Tests concept-to-assessment mapping via Gemini.
"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from lecturelink_api.agents.concept_mapper import (
    _get_syllabus_schedule,
    map_concepts_to_assessments,
)

_MOD = "lecturelink_api.agents.concept_mapper"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _concepts_with_ids() -> list[dict]:
    return [
        {
            "id": "concept-001",
            "title": "First Law of Thermodynamics",
            "description": "Energy is conserved",
            "category": "theorem",
        },
        {
            "id": "concept-002",
            "title": "Heat Transfer",
            "description": "Movement of thermal energy",
            "category": "process",
        },
    ]


def _assessments() -> list[dict]:
    return [
        {
            "id": "assess-001",
            "title": "Midterm 1",
            "assessment_type": "exam",
            "due_date": "2026-03-15",
            "weight": 20,
            "topics": ["thermodynamics", "heat transfer", "first law"],
            "course_id": "course-001",
        },
        {
            "id": "assess-002",
            "title": "Final Exam",
            "assessment_type": "exam",
            "due_date": "2026-04-20",
            "weight": 35,
            "topics": ["all topics"],
            "course_id": "course-001",
        },
    ]


def _gemini_mapping_response() -> str:
    return json.dumps([
        {
            "concept_title": "First Law of Thermodynamics",
            "assessment_mappings": [
                {
                    "assessment_id": "assess-001",
                    "relevance_score": 0.92,
                    "reasoning": "Directly listed in midterm topics",
                },
                {
                    "assessment_id": "assess-002",
                    "relevance_score": 0.7,
                    "reasoning": "Final covers all topics",
                },
            ],
        },
        {
            "concept_title": "Heat Transfer",
            "assessment_mappings": [
                {
                    "assessment_id": "assess-001",
                    "relevance_score": 0.85,
                    "reasoning": "Listed in midterm topics",
                },
            ],
        },
    ])


def _build_mock_supabase(assessments=None, schedule_data=None) -> MagicMock:
    sb = MagicMock()

    # Assessments query: .table("assessments").select("*").eq("course_id", ...).execute()
    sb.table.return_value.select.return_value.eq.return_value.execute.return_value = MagicMock(
        data=assessments if assessments is not None else _assessments()
    )

    # Syllabi query: .table("syllabi").select().eq().eq().limit().execute()
    sb.table.return_value.select.return_value.eq.return_value.eq.return_value.limit.return_value.execute.return_value = MagicMock(
        data=schedule_data if schedule_data is not None else []
    )

    # Upsert: .table("concept_assessment_links").upsert().execute()
    sb.table.return_value.upsert.return_value.execute.return_value = MagicMock(data=[
        {"concept_id": "concept-001", "assessment_id": "assess-001"},
        {"concept_id": "concept-001", "assessment_id": "assess-002"},
        {"concept_id": "concept-002", "assessment_id": "assess-001"},
    ])

    return sb


# ---------------------------------------------------------------------------
# Test: map_concepts_to_assessments — success
# ---------------------------------------------------------------------------


class TestMapConceptsSuccess:
    @pytest.mark.asyncio
    async def test_creates_links_with_valid_data(self):
        sb = _build_mock_supabase()
        mock_response = MagicMock()
        mock_response.text = _gemini_mapping_response()

        mock_client = MagicMock()
        mock_client.aio.models.generate_content = AsyncMock(return_value=mock_response)

        with patch(f"{_MOD}.genai.Client", return_value=mock_client):
            result = await map_concepts_to_assessments(
                supabase=sb,
                lecture_id="lec-001",
                course_id="course-001",
                user_id="user-001",
                concepts=_concepts_with_ids(),
                lecture_date="2026-01-15",
                lecture_number=3,
            )

        assert len(result) == 3
        # Upsert was called
        sb.table.return_value.upsert.assert_called_once()

    @pytest.mark.asyncio
    async def test_handles_markdown_fenced_response(self):
        sb = _build_mock_supabase()
        fenced = "```json\n" + _gemini_mapping_response() + "\n```"
        mock_response = MagicMock()
        mock_response.text = fenced

        mock_client = MagicMock()
        mock_client.aio.models.generate_content = AsyncMock(return_value=mock_response)

        with patch(f"{_MOD}.genai.Client", return_value=mock_client):
            result = await map_concepts_to_assessments(
                supabase=sb,
                lecture_id="lec-001",
                course_id="course-001",
                user_id="user-001",
                concepts=_concepts_with_ids(),
            )

        assert len(result) == 3


# ---------------------------------------------------------------------------
# Test: No assessments
# ---------------------------------------------------------------------------


class TestNoAssessments:
    @pytest.mark.asyncio
    async def test_returns_empty_with_no_assessments(self):
        sb = _build_mock_supabase(assessments=[])

        result = await map_concepts_to_assessments(
            supabase=sb,
            lecture_id="lec-001",
            course_id="course-001",
            user_id="user-001",
            concepts=_concepts_with_ids(),
        )

        assert result == []


# ---------------------------------------------------------------------------
# Test: Gemini failure → empty mappings (no fabrication)
# ---------------------------------------------------------------------------


class TestGeminiFailure:
    @pytest.mark.asyncio
    async def test_returns_empty_on_gemini_failure(self):
        sb = _build_mock_supabase()

        mock_client = MagicMock()
        mock_client.aio.models.generate_content = AsyncMock(
            side_effect=Exception("Gemini rate limited")
        )

        with patch(f"{_MOD}.genai.Client", return_value=mock_client):
            result = await map_concepts_to_assessments(
                supabase=sb,
                lecture_id="lec-001",
                course_id="course-001",
                user_id="user-001",
                concepts=_concepts_with_ids(),
            )

        # No fabricated mappings — returns empty
        assert result == []


# ---------------------------------------------------------------------------
# Test: _get_syllabus_schedule
# ---------------------------------------------------------------------------


class TestGetSyllabusSchedule:
    def test_returns_schedule_from_confirmed_syllabus(self):
        sb = MagicMock()
        schedule = [{"week": 1, "topics": ["Intro"]}, {"week": 2, "topics": ["Chapter 1"]}]
        sb.table.return_value.select.return_value.eq.return_value.eq.return_value.limit.return_value.execute.return_value = MagicMock(
            data=[{"raw_extraction": {"schedule": schedule}}]
        )

        result = _get_syllabus_schedule(sb, "course-001")
        assert result == schedule

    def test_returns_empty_with_no_syllabus(self):
        sb = MagicMock()
        sb.table.return_value.select.return_value.eq.return_value.eq.return_value.limit.return_value.execute.return_value = MagicMock(
            data=[]
        )

        result = _get_syllabus_schedule(sb, "course-001")
        assert result == []

    def test_returns_empty_on_db_error(self):
        sb = MagicMock()
        sb.table.return_value.select.return_value.eq.return_value.eq.return_value.limit.return_value.execute.side_effect = Exception(
            "DB connection failed"
        )

        result = _get_syllabus_schedule(sb, "course-001")
        assert result == []


# ---------------------------------------------------------------------------
# Test: Relevance filtering
# ---------------------------------------------------------------------------


class TestRelevanceFiltering:
    @pytest.mark.asyncio
    async def test_scores_below_threshold_filtered(self):
        sb = _build_mock_supabase()
        # Return a mapping with low scores
        low_score_response = json.dumps([{
            "concept_title": "First Law of Thermodynamics",
            "assessment_mappings": [
                {"assessment_id": "assess-001", "relevance_score": 0.3, "reasoning": "low"},
                {"assessment_id": "assess-002", "relevance_score": 0.49, "reasoning": "low"},
            ],
        }])

        mock_response = MagicMock()
        mock_response.text = low_score_response
        mock_client = MagicMock()
        mock_client.aio.models.generate_content = AsyncMock(return_value=mock_response)

        # Override upsert to not be called
        sb.table.return_value.upsert.return_value.execute.return_value = MagicMock(
            data=[]
        )

        with patch(f"{_MOD}.genai.Client", return_value=mock_client):
            result = await map_concepts_to_assessments(
                supabase=sb,
                lecture_id="lec-001",
                course_id="course-001",
                user_id="user-001",
                concepts=_concepts_with_ids(),
            )

        # No links should be created (all below 0.5)
        assert result == []


# ---------------------------------------------------------------------------
# Test: Case-insensitive concept matching
# ---------------------------------------------------------------------------


class TestCaseInsensitiveMatching:
    @pytest.mark.asyncio
    async def test_titles_matched_case_insensitively(self):
        sb = _build_mock_supabase()
        # Gemini returns lowercase title but concept has mixed case
        response = json.dumps([{
            "concept_title": "first law of thermodynamics",
            "assessment_mappings": [
                {"assessment_id": "assess-001", "relevance_score": 0.9, "reasoning": "match"},
            ],
        }])

        mock_response = MagicMock()
        mock_response.text = response
        mock_client = MagicMock()
        mock_client.aio.models.generate_content = AsyncMock(return_value=mock_response)

        with patch(f"{_MOD}.genai.Client", return_value=mock_client):
            result = await map_concepts_to_assessments(
                supabase=sb,
                lecture_id="lec-001",
                course_id="course-001",
                user_id="user-001",
                concepts=_concepts_with_ids(),
            )

        # Should still match despite case difference
        assert len(result) > 0


# ---------------------------------------------------------------------------
# Test: Upsert for reprocessing
# ---------------------------------------------------------------------------


class TestUpsertReprocessing:
    @pytest.mark.asyncio
    async def test_upsert_used_for_conflict_handling(self):
        sb = _build_mock_supabase()
        mock_response = MagicMock()
        mock_response.text = _gemini_mapping_response()
        mock_client = MagicMock()
        mock_client.aio.models.generate_content = AsyncMock(return_value=mock_response)

        with patch(f"{_MOD}.genai.Client", return_value=mock_client):
            await map_concepts_to_assessments(
                supabase=sb,
                lecture_id="lec-001",
                course_id="course-001",
                user_id="user-001",
                concepts=_concepts_with_ids(),
            )

        # Verify upsert was called with on_conflict parameter
        upsert_call = sb.table.return_value.upsert.call_args
        assert upsert_call is not None
        assert upsert_call[1].get("on_conflict") == "concept_id,assessment_id"
