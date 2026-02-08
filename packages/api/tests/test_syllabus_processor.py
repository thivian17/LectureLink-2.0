"""Tests for the multi-agent syllabus extraction pipeline."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from lecturelink_api.agents.syllabus_processor import (
    GradingOutput,
    ScheduleOutput,
    extraction_pipeline,
    grading_extractor,
    info_extractor,
    ingestion_agent,
    parallel_extraction,
    schedule_extractor,
    validation_loop,
    validator,
)
from lecturelink_api.models.syllabus_models import SyllabusExtraction

FIXTURES_DIR = Path(__file__).parent / "fixtures"


# ---------------------------------------------------------------------------
# Sample extraction output (simulates what the validated pipeline produces)
# ---------------------------------------------------------------------------

_SAMPLE_EXTRACTION = {
    "course_name": {
        "value": "Introduction to Computer Science",
        "confidence": 0.95,
        "source_text": "CS 101 - Introduction to Computer Science",
    },
    "course_code": {
        "value": "CS 101",
        "confidence": 0.95,
        "source_text": "CS 101",
    },
    "instructor_name": {
        "value": "Dr. Jane Smith",
        "confidence": 0.9,
        "source_text": "Instructor: Dr. Jane Smith",
    },
    "instructor_email": {
        "value": "jsmith@university.edu",
        "confidence": 0.9,
        "source_text": "Email: jsmith@university.edu",
    },
    "office_hours": {
        "value": "Mon/Wed 2-3pm, Room 301",
        "confidence": 0.85,
        "source_text": "Office Hours: Mon/Wed 2-3pm, Room 301",
    },
    "grade_breakdown": [
        {
            "name": {"value": "Midterm Exams", "confidence": 0.95, "source_text": "Midterms: 30%"},
            "weight_percent": {"value": 30.0, "confidence": 0.95, "source_text": "30%"},
            "drop_policy": None,
        },
        {
            "name": {"value": "Final Exam", "confidence": 0.95, "source_text": "Final: 35%"},
            "weight_percent": {"value": 35.0, "confidence": 0.95, "source_text": "35%"},
            "drop_policy": None,
        },
        {
            "name": {"value": "Homework", "confidence": 0.9, "source_text": "Homework: 25%"},
            "weight_percent": {"value": 25.0, "confidence": 0.9, "source_text": "25%"},
            "drop_policy": {
                "value": "lowest score dropped",
                "confidence": 0.8,
                "source_text": "lowest score dropped",
            },
        },
        {
            "name": {"value": "Participation", "confidence": 0.85, "source_text": "Participation: 10%"},
            "weight_percent": {"value": 10.0, "confidence": 0.85, "source_text": "10%"},
            "drop_policy": None,
        },
    ],
    "assessments": [
        {
            "title": {"value": "Midterm 1", "confidence": 0.95, "source_text": "Midterm 1"},
            "type": {"value": "exam", "confidence": 0.95, "source_text": "Midterm Exam"},
            "due_date_raw": {"value": "October 10", "confidence": 0.9, "source_text": "October 10"},
            "due_date_resolved": {"value": "2025-10-10", "confidence": 0.85, "source_text": None},
            "weight_percent": {"value": 15.0, "confidence": 0.9, "source_text": "15%"},
            "topics": ["Chapters 1-5"],
        },
        {
            "title": {"value": "Final Exam", "confidence": 0.95, "source_text": "Final Exam"},
            "type": {"value": "exam", "confidence": 0.95, "source_text": "Final Exam"},
            "due_date_raw": {"value": "December 15", "confidence": 0.9, "source_text": "December 15"},
            "due_date_resolved": {"value": "2025-12-15", "confidence": 0.9, "source_text": None},
            "weight_percent": {"value": 35.0, "confidence": 0.95, "source_text": "35%"},
            "topics": ["Chapters 1-12"],
        },
        {
            "title": {"value": "Homework 1", "confidence": 0.9, "source_text": "Homework 1"},
            "type": {"value": "homework", "confidence": 0.9, "source_text": "Homework"},
            "due_date_raw": {"value": "Sep 10", "confidence": 0.85, "source_text": "Sep 10"},
            "due_date_resolved": {"value": "2025-09-10", "confidence": 0.8, "source_text": None},
            "weight_percent": {"value": 5.0, "confidence": 0.85, "source_text": "5%"},
            "topics": ["Chapter 1"],
        },
    ],
    "weekly_schedule": [
        {
            "week_number": 1,
            "date_range": {
                "value": "Aug 25 – Aug 29",
                "confidence": 0.9,
                "source_text": "Week 1 - Aug 25-29",
            },
            "topics": ["Course overview", "Intro to Python"],
            "readings": ["Chapter 1"],
            "due_items": [],
        },
        {
            "week_number": 2,
            "date_range": {
                "value": "Sep 1 – Sep 5",
                "confidence": 0.9,
                "source_text": "Week 2 - Sep 1-5",
            },
            "topics": ["Variables and Data Types"],
            "readings": [],
            "due_items": [],
        },
        {
            "week_number": 3,
            "date_range": {
                "value": "Sep 8 – Sep 12",
                "confidence": 0.9,
                "source_text": "Week 3 - Sep 8-12",
            },
            "topics": ["Control Flow"],
            "readings": [],
            "due_items": ["Homework 1"],
        },
    ],
    "policies": {
        "late_policy": "10% penalty per day, maximum 3 days late",
        "academic_integrity": "Zero tolerance for plagiarism",
    },
    "extraction_confidence": 0.9,
    "missing_sections": [],
}


# ---------------------------------------------------------------------------
# Pipeline structure tests
# ---------------------------------------------------------------------------


class TestPipelineStructure:
    """Verify the agent graph is wired correctly."""

    def test_pipeline_name(self):
        assert extraction_pipeline.name == "ExtractionPipeline"

    def test_pipeline_has_two_stages(self):
        assert len(extraction_pipeline.sub_agents) == 2

    def test_ingestion_agent_exists(self):
        assert ingestion_agent.name == "IngestionAgent"
        assert ingestion_agent.output_key == "raw_text"

    def test_stage_1_is_parallel_extraction(self):
        agent = extraction_pipeline.sub_agents[0]
        assert agent.name == "ParallelExtraction"
        names = {a.name for a in agent.sub_agents}
        assert names == {"ScheduleExtractor", "GradingExtractor", "InfoExtractor"}

    def test_stage_2_is_validation_loop(self):
        agent = extraction_pipeline.sub_agents[1]
        assert agent.name == "ValidationLoop"
        assert agent is validation_loop
        assert validator.output_key == "validated_syllabus"

    def test_all_extractors_use_gemini_flash(self):
        for agent in [schedule_extractor, grading_extractor, info_extractor]:
            assert agent.model == "gemini-2.5-flash"

    def test_ingestion_has_document_tool(self):
        assert len(ingestion_agent.tools) == 1

    def test_parallel_agent_has_three_sub_agents(self):
        assert len(parallel_extraction.sub_agents) == 3

    def test_extraction_output_keys(self):
        assert schedule_extractor.output_key == "schedule_data"
        assert grading_extractor.output_key == "grading_data"
        assert info_extractor.output_key == "info_data"


# ---------------------------------------------------------------------------
# Intermediate schema tests
# ---------------------------------------------------------------------------


class TestIntermediateSchemas:
    """Verify the intermediate output schemas produce valid JSON schemas."""

    def test_schedule_output_schema(self):
        schema = ScheduleOutput.model_json_schema()
        assert schema["type"] == "object"
        assert "weekly_schedule" in schema["properties"]

    def test_grading_output_schema(self):
        schema = GradingOutput.model_json_schema()
        assert schema["type"] == "object"
        assert "grade_breakdown" in schema["properties"]
        assert "assessments" in schema["properties"]

    def test_schemas_are_json_serializable(self):
        for model_cls in (ScheduleOutput, GradingOutput):
            schema = model_cls.model_json_schema()
            roundtripped = json.loads(json.dumps(schema))
            assert roundtripped == schema


# ---------------------------------------------------------------------------
# Pipeline output validation tests
# ---------------------------------------------------------------------------


class TestPipelineOutput:
    """Validate that pipeline-shaped output parses into correct models."""

    @pytest.fixture()
    def extraction(self):
        return SyllabusExtraction(**_SAMPLE_EXTRACTION)

    def test_output_parses_as_valid_syllabus_extraction(self, extraction):
        assert isinstance(extraction, SyllabusExtraction)
        assert extraction.course_name.value == "Introduction to Computer Science"
        assert extraction.course_code.value == "CS 101"

    def test_grade_breakdown_has_at_least_one_component(self, extraction):
        assert len(extraction.grade_breakdown) >= 1
        assert extraction.grade_breakdown[0].name.value == "Midterm Exams"

    def test_assessments_non_empty(self, extraction):
        assert len(extraction.assessments) > 0
        assert extraction.assessments[0].title.value == "Midterm 1"

    def test_weekly_schedule_present(self, extraction):
        assert len(extraction.weekly_schedule) >= 1
        assert extraction.weekly_schedule[0].week_number == 1

    def test_policies_extracted(self, extraction):
        assert "late_policy" in extraction.policies
        assert "academic_integrity" in extraction.policies

    def test_extraction_roundtrips_through_json(self, extraction):
        json_str = extraction.model_dump_json()
        restored = SyllabusExtraction.model_validate_json(json_str)
        assert restored == extraction


# ---------------------------------------------------------------------------
# Fixture file tests
# ---------------------------------------------------------------------------


class TestFixtures:
    """Verify that test fixture files exist and are valid."""

    def test_sample_pdf_fixture_exists(self):
        pdf_path = FIXTURES_DIR / "sample_syllabus.pdf"
        assert pdf_path.exists(), f"Sample PDF fixture not found at {pdf_path}"

    def test_sample_pdf_is_valid(self):
        pdf_path = FIXTURES_DIR / "sample_syllabus.pdf"
        content = pdf_path.read_bytes()
        assert content[:5] == b"%PDF-", "Fixture is not a valid PDF file"
        assert len(content) > 100, "PDF fixture seems too small"


# ---------------------------------------------------------------------------
# Runner instantiation test
# ---------------------------------------------------------------------------


class TestRunnerIntegration:
    """Verify the pipeline can be loaded into an ADK Runner."""

    @pytest.mark.asyncio
    async def test_runner_accepts_pipeline(self):
        from google.adk.runners import Runner
        from google.adk.sessions import InMemorySessionService

        runner = Runner(
            agent=extraction_pipeline,
            app_name="test_syllabus",
            session_service=InMemorySessionService(),
        )
        assert runner.agent.name == "ExtractionPipeline"
