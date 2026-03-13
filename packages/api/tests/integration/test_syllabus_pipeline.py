"""Tests for the syllabus processing pipeline integration.

Tests the flow: upload → process (mocked pipeline) → status → review → accept.
Validates date resolution, ambiguous date flagging, and assessment DB population.
"""

from __future__ import annotations

import uuid
from datetime import date
from unittest.mock import MagicMock, patch

import pytest
from lecturelink_api.agents.syllabus_processor import finalize_extraction, post_process_extraction
from lecturelink_api.models.syllabus_models import (
    SyllabusExtraction,
    extraction_to_db_assessments,
)
from lecturelink_api.tools.date_resolver import SemesterContext, resolve_all_dates

from tests.integration.conftest import (
    make_assessment,
    make_pipeline_output,
    make_syllabus,
    mock_chain,
)

# ---------------------------------------------------------------------------
# Pipeline output → post-processing tests
# ---------------------------------------------------------------------------


class TestPostProcessingIntegration:
    """Test that post_process_extraction produces valid SyllabusExtraction."""

    @pytest.mark.integration
    def test_pipeline_output_parses_to_model(self):
        """Pre-computed pipeline output can be post-processed successfully."""
        raw = make_pipeline_output()
        semester_ctx = {
            "semester_start": "2026-01-12",
            "semester_end": "2026-05-01",
            "meeting_days": ["tuesday", "thursday"],
            "holidays": [],
        }

        extraction = post_process_extraction(raw, semester_ctx)
        extraction = finalize_extraction(extraction, semester_ctx)

        assert isinstance(extraction, SyllabusExtraction)
        assert extraction.extraction_confidence > 0
        assert len(extraction.assessments) > 0
        assert len(extraction.grade_breakdown) > 0

    @pytest.mark.integration
    def test_grade_weights_sum_correctly(self):
        """Grade breakdown weights sum close to 100%."""
        raw = make_pipeline_output()
        extraction = post_process_extraction(raw, {})

        total = sum(
            float(comp.weight_percent.value or 0)
            for comp in extraction.grade_breakdown
        )
        assert 95.0 <= total <= 105.0, f"Grade total {total}% not near 100%"

    @pytest.mark.integration
    def test_assessments_have_required_fields(self):
        """Every assessment has title and type after post-processing."""
        raw = make_pipeline_output()
        extraction = post_process_extraction(raw, {})

        for a in extraction.assessments:
            assert a.title.value is not None, "Assessment missing title"
            assert a.type.value is not None, "Assessment missing type"


# ---------------------------------------------------------------------------
# Date resolution tests
# ---------------------------------------------------------------------------


class TestDateResolutionIntegration:
    """Test date resolution on extraction output."""

    @pytest.mark.integration
    def test_explicit_dates_preserved(self):
        """Dates like 'February 19, 2026' stay resolved."""
        raw = make_pipeline_output()
        extraction = post_process_extraction(raw, {})

        sem = SemesterContext(
            start=date(2026, 1, 12),
            end=date(2026, 5, 1),
            meeting_days=["tuesday", "thursday"],
            holidays=[],
        )
        resolved = resolve_all_dates(extraction.assessments, sem)

        for a in resolved:
            if a.due_date_resolved.value:
                # Verify resolved dates are actual date strings
                date.fromisoformat(str(a.due_date_resolved.value))

    @pytest.mark.integration
    def test_llm_resolved_dates_validated(self):
        """LLM-resolved dates are validated against semester boundaries."""
        from lecturelink_api.tools.date_resolver import resolve_date

        sem = SemesterContext(
            start=date(2026, 1, 12),
            end=date(2026, 5, 1),
            meeting_days=["tuesday", "thursday"],
            holidays=[],
        )

        # Valid LLM date within semester accepted
        result = resolve_date("Week 3 Tuesday", sem, llm_resolved=date(2026, 1, 27))
        assert result.value is not None
        assert result.value == date(2026, 1, 27)

        # LLM date outside semester rejected
        result = resolve_date("Week 8 Thursday", sem, llm_resolved=date(2026, 6, 1))
        assert result.value is None

    @pytest.mark.integration
    def test_ambiguous_dates_flagged(self):
        """Assessments with raw text but no resolved date are marked ambiguous."""
        raw = make_pipeline_output()
        # Set one assessment to have unresolvable date
        raw["assessments"][0]["due_date_raw"] = {
            "value": "TBD",
            "confidence": 0.3,
            "source_text": "TBD",
        }
        raw["assessments"][0]["due_date_resolved"] = {
            "value": None,
            "confidence": 0.0,
            "source_text": None,
        }

        extraction = post_process_extraction(raw, {})
        rows = extraction_to_db_assessments(
            extraction, str(uuid.uuid4()), str(uuid.uuid4())
        )

        tbd_row = next(r for r in rows if r["due_date_raw"] == "TBD")
        assert tbd_row["is_date_ambiguous"] is True
        assert tbd_row["due_date"] is None


# ---------------------------------------------------------------------------
# DB assessment conversion tests
# ---------------------------------------------------------------------------


class TestAssessmentConversion:
    """Test extraction → DB row conversion."""

    @pytest.mark.integration
    def test_conversion_produces_correct_row_count(self):
        """extraction_to_db_assessments produces one row per assessment."""
        raw = make_pipeline_output()
        extraction = post_process_extraction(raw, {})
        course_id = str(uuid.uuid4())
        syllabus_id = str(uuid.uuid4())

        rows = extraction_to_db_assessments(extraction, course_id, syllabus_id)

        assert len(rows) == len(extraction.assessments)

    @pytest.mark.integration
    def test_rows_have_correct_foreign_keys(self):
        """Each row references the correct course and syllabus."""
        raw = make_pipeline_output()
        extraction = post_process_extraction(raw, {})
        course_id = str(uuid.uuid4())
        syllabus_id = str(uuid.uuid4())

        rows = extraction_to_db_assessments(extraction, course_id, syllabus_id)

        for row in rows:
            assert row["course_id"] == course_id
            assert row["syllabus_id"] == syllabus_id
            assert row["id"]  # UUID generated

    @pytest.mark.integration
    def test_weight_percent_converted_to_float(self):
        """String weight values get converted to float."""
        raw = make_pipeline_output()
        extraction = post_process_extraction(raw, {})
        rows = extraction_to_db_assessments(
            extraction, str(uuid.uuid4()), str(uuid.uuid4())
        )

        for row in rows:
            if row["weight_percent"] is not None:
                assert isinstance(row["weight_percent"], float)


# ---------------------------------------------------------------------------
# Upload + review endpoint flow
# ---------------------------------------------------------------------------


class TestUploadAndReviewFlow:
    """Test the upload → status → review endpoint sequence."""

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_upload_creates_processing_record(self, client):
        """POST /api/syllabi/upload returns 201 with syllabus_id."""
        course_id = str(uuid.uuid4())
        syllabus_id = str(uuid.uuid4())

        with patch("lecturelink_api.routers.syllabi.create_client") as mc:
            sb = MagicMock()
            mc.return_value = sb

            course_chain = mock_chain([{"id": course_id}])
            insert_chain = mock_chain(
                [{"id": syllabus_id, "status": "processing"}]
            )
            sb.table.side_effect = lambda name: (
                course_chain if name == "courses" else insert_chain
            )
            sb.storage.from_.return_value.upload.return_value = None

            resp = await client.post(
                "/api/syllabi/upload",
                data={"course_id": course_id},
                files={
                    "file": (
                        "phys201.pdf",
                        b"%PDF-1.4 fake",
                        "application/pdf",
                    )
                },
            )

        assert resp.status_code == 201
        data = resp.json()
        assert data["syllabus_id"] == syllabus_id
        assert data["status"] == "processing"

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_review_marks_syllabus_complete(self, client):
        """PUT /api/syllabi/{id}/review sets needs_review=False."""
        sid = str(uuid.uuid4())
        reviewed = make_syllabus(
            syllabus_id=sid,
            needs_review=False,
            reviewed_at="2026-02-08T12:00:00Z",
            raw_extraction={"course_name": {"value": "PHYS 201", "confidence": 1.0}},
            extraction_confidence=0.9,
        )

        with patch("lecturelink_api.routers.syllabi.create_client") as mc:
            sb = MagicMock()
            mc.return_value = sb
            sb.table.return_value = mock_chain([reviewed])

            resp = await client.put(
                f"/api/syllabi/{sid}/review",
                json={
                    "raw_extraction": {
                        "course_name": {"value": "PHYS 201", "confidence": 1.0}
                    }
                },
            )

        assert resp.status_code == 200
        assert resp.json()["needs_review"] is False

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_assessment_manual_correction_clears_ambiguous(self, client):
        """PATCH assessment with corrected date clears is_date_ambiguous."""
        course_id = str(uuid.uuid4())
        assessment_id = str(uuid.uuid4())
        updated = make_assessment(
            course_id,
            assessment_id,
            due_date="2026-03-15",
            is_date_ambiguous=False,
        )

        with patch(
            "lecturelink_api.routers.assessments.create_client"
        ) as mc:
            sb = MagicMock()
            mc.return_value = sb

            existing_chain = mock_chain(
                [{"id": assessment_id, "course_id": course_id}]
            )
            course_chain = mock_chain([{"id": course_id}])
            update_chain = mock_chain([updated])

            call_count = {"n": 0}
            chains = [existing_chain, course_chain, update_chain]

            def table_side_effect(name):
                idx = min(call_count["n"], len(chains) - 1)
                call_count["n"] += 1
                return chains[idx]

            sb.table.side_effect = table_side_effect

            resp = await client.patch(
                f"/api/assessments/{assessment_id}",
                json={
                    "due_date": "2026-03-15",
                    "is_date_ambiguous": False,
                },
            )

        assert resp.status_code == 200
        assert resp.json()["is_date_ambiguous"] is False
