"""Integration test fixtures.

Provides:
- Fake auth that bypasses Supabase JWT validation
- Supabase mock factory for chainable query builders
- AsyncClient for making API requests via ASGI transport
- Pre-computed pipeline outputs (so tests run without Gemini)
- Phase 2 factories: lectures, chunks, concepts, quizzes, quiz questions
"""

from __future__ import annotations

import os
import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from lecturelink_api.main import app

# ---------------------------------------------------------------------------
# Env-var gating — skip all integration tests unless opted in
# ---------------------------------------------------------------------------

_SKIP_MSG = "Set LECTURELINK_RUN_INTEGRATION=1 to run integration tests"


def pytest_collection_modifyitems(config, items):  # noqa: ARG001
    if os.getenv("LECTURELINK_RUN_INTEGRATION"):
        return
    skip = pytest.mark.skip(reason=_SKIP_MSG)
    for item in items:
        if "integration" in str(item.fspath):
            item.add_marker(skip)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

FAKE_USER_ID = str(uuid.uuid4())
FAKE_EMAIL = "integration@test.edu"
FAKE_TOKEN = "integration-test-token"


# ---------------------------------------------------------------------------
# Auth / settings overrides
# ---------------------------------------------------------------------------


def _fake_user():
    return {"id": FAKE_USER_ID, "email": FAKE_EMAIL, "token": FAKE_TOKEN}


def _now_str():
    return datetime.now(UTC).isoformat()


@pytest.fixture()
def override_auth():
    from lecturelink_api.auth import get_current_user

    app.dependency_overrides[get_current_user] = lambda: _fake_user()
    yield
    app.dependency_overrides.pop(get_current_user, None)


@pytest.fixture()
def override_settings():
    from lecturelink_api.config import Settings, get_settings

    fake = Settings(
        SUPABASE_URL="https://fake.supabase.co",
        SUPABASE_ANON_KEY="fake-anon-key",
    )
    app.dependency_overrides[get_settings] = lambda: fake
    yield fake
    app.dependency_overrides.pop(get_settings, None)


@pytest.fixture()
def override_task_queue():
    from lecturelink_api.services.task_queue import get_task_queue
    mock_tq = MagicMock()
    mock_tq.enqueue_lecture_processing = AsyncMock()
    mock_tq.enqueue_quiz_generation = AsyncMock()
    mock_tq.enqueue_syllabus_processing = AsyncMock()
    mock_tq.enqueue_user_refresh = AsyncMock()
    app.dependency_overrides[get_task_queue] = lambda: mock_tq
    yield mock_tq
    app.dependency_overrides.pop(get_task_queue, None)


@pytest_asyncio.fixture()
async def client(override_auth, override_settings, override_task_queue):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest_asyncio.fixture()
async def unauthenticated_client(override_settings):
    """Client WITHOUT auth override — requests will hit real auth checks."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


# ---------------------------------------------------------------------------
# Supabase mock helpers (same pattern as test_api.py)
# ---------------------------------------------------------------------------


def mock_execute(data):
    """Return a mock that looks like supabase.execute() result."""
    resp = MagicMock()
    resp.data = data
    return resp


def mock_chain(final_data, *, count=None):
    """Build a chainable mock that returns final_data on .execute()."""
    chain = MagicMock()
    result = mock_execute(final_data)
    result.count = count if count is not None else (
        len(final_data) if isinstance(final_data, list) else 0
    )
    chain.execute.return_value = result
    for method in (
        "select", "insert", "update", "delete",
        "eq", "order", "single", "maybe_single",
        "limit", "not_", "gte", "in_",
    ):
        getattr(chain, method).return_value = chain
    return chain


def mock_chain_async(final_data, *, count=None):
    """Build a chainable mock where .execute() is an AsyncMock.

    Required for code paths that ``await supabase.table(...).execute()``
    such as the rate-limit middleware.
    """
    chain = MagicMock()
    result = mock_execute(final_data)
    result.count = count if count is not None else (
        len(final_data) if isinstance(final_data, list) else 0
    )
    chain.execute = AsyncMock(return_value=result)
    for method in (
        "select", "insert", "update", "delete",
        "eq", "order", "single", "maybe_single",
        "limit", "not_", "gte", "in_",
    ):
        getattr(chain, method).return_value = chain
    return chain


# ---------------------------------------------------------------------------
# Sample data factories
# ---------------------------------------------------------------------------


def make_course(course_id: str | None = None, **overrides) -> dict:
    cid = course_id or str(uuid.uuid4())
    base = {
        "id": cid,
        "user_id": FAKE_USER_ID,
        "name": "PHYS 201: Thermodynamics",
        "code": "PHYS201",
        "semester_start": "2026-01-12",
        "semester_end": "2026-05-01",
        "meeting_days": ["Tuesday", "Thursday"],
        "meeting_time": "10:00",
        "holidays": [],
        "target_grade": 0.8,
        "created_at": _now_str(),
        "updated_at": _now_str(),
    }
    base.update(overrides)
    return base


def make_syllabus(
    syllabus_id: str | None = None,
    course_id: str | None = None,
    **overrides,
) -> dict:
    sid = syllabus_id or str(uuid.uuid4())
    cid = course_id or str(uuid.uuid4())
    base = {
        "id": sid,
        "course_id": cid,
        "user_id": FAKE_USER_ID,
        "file_url": "https://example.com/syllabus.pdf",
        "file_name": "syllabus.pdf",
        "raw_extraction": None,
        "grade_breakdown": [],
        "extraction_confidence": None,
        "needs_review": True,
        "status": "pending",
        "reviewed_at": None,
        "created_at": _now_str(),
    }
    base.update(overrides)
    return base


def make_assessment(
    course_id: str,
    assessment_id: str | None = None,
    **overrides,
) -> dict:
    aid = assessment_id or str(uuid.uuid4())
    base = {
        "id": aid,
        "course_id": course_id,
        "syllabus_id": str(uuid.uuid4()),
        "title": "Midterm Exam 1",
        "type": "exam",
        "due_date": "2026-02-19",
        "due_date_raw": "February 19, 2026",
        "is_date_ambiguous": False,
        "weight_percent": 15.0,
        "topics": ["Chapters 1-5"],
        "created_at": _now_str(),
    }
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# Pre-computed pipeline output (mock of what Gemini would return)
# ---------------------------------------------------------------------------


def make_pipeline_output() -> dict:
    """A pre-built extraction result matching STEM syllabus ground truth.

    This allows testing post-processing, date resolution, DB persistence,
    and the review flow without calling Gemini.
    """
    def _field(value, confidence=0.9, source=None):
        return {"value": value, "confidence": confidence, "source_text": source}

    return {
        "course_name": _field("University Physics I", 0.95),
        "course_code": _field("PHYS 201", 0.95),
        "instructor_name": _field("Dr. Richard Feynman", 0.9),
        "instructor_email": _field("rfeynman@caltech.edu", 0.85),
        "office_hours": _field("Tuesday/Thursday 2:00-3:30 PM, Room 214", 0.8),
        "grade_breakdown": [
            {
                "name": _field("Midterm Exam 1"),
                "weight_percent": _field(15.0),
                "drop_policy": None,
            },
            {
                "name": _field("Midterm Exam 2"),
                "weight_percent": _field(15.0),
                "drop_policy": None,
            },
            {
                "name": _field("Final Exam"),
                "weight_percent": _field(30.0),
                "drop_policy": None,
            },
            {
                "name": _field("Laboratory Reports"),
                "weight_percent": _field(20.0),
                "drop_policy": None,
            },
            {
                "name": _field("Homework Assignments"),
                "weight_percent": _field(15.0),
                "drop_policy": _field("lowest dropped"),
            },
            {
                "name": _field("Participation"),
                "weight_percent": _field(5.0),
                "drop_policy": None,
            },
        ],
        "assessments": [
            {
                "title": _field("Midterm Exam 1"),
                "type": _field("exam"),
                "due_date_raw": _field("February 19, 2026"),
                "due_date_resolved": _field("2026-02-19"),
                "weight_percent": _field(15.0),
                "topics": ["Chapters 1-5"],
            },
            {
                "title": _field("Midterm Exam 2"),
                "type": _field("exam"),
                "due_date_raw": _field("April 2, 2026"),
                "due_date_resolved": _field("2026-04-02"),
                "weight_percent": _field(15.0),
                "topics": ["Chapters 6-10"],
            },
            {
                "title": _field("Final Exam"),
                "type": _field("exam"),
                "due_date_raw": _field("May 7, 2026"),
                "due_date_resolved": _field("2026-05-07"),
                "weight_percent": _field(30.0),
                "topics": ["Cumulative"],
            },
            {
                "title": _field("Lab Report 1"),
                "type": _field("lab"),
                "due_date_raw": _field("February 5, 2026"),
                "due_date_resolved": _field("2026-02-05"),
                "weight_percent": _field(5.0),
                "topics": ["Calorimetry"],
            },
        ],
        "weekly_schedule": [],
        "policies": {
            "late_policy": "10% penalty per day, maximum 3 days late.",
            "academic_integrity": "Violations result in course failure.",
        },
        "extraction_confidence": 0.88,
        "missing_sections": [],
    }


# ---------------------------------------------------------------------------
# Phase 2 data factories
# ---------------------------------------------------------------------------


def make_lecture(
    course_id: str,
    lecture_id: str | None = None,
    **overrides,
) -> dict:
    lid = lecture_id or str(uuid.uuid4())
    base = {
        "id": lid,
        "course_id": course_id,
        "user_id": FAKE_USER_ID,
        "title": "Lecture 1: Intro to Thermodynamics",
        "lecture_number": 1,
        "lecture_date": "2026-01-14",
        "processing_status": "completed",
        "processing_stage": "completed",
        "processing_progress": 1.0,
        "processing_error": None,
        "summary": "Introduction to thermodynamic systems and energy transfer.",
        "duration_seconds": 3000,
        "transcript": '[{"start":0.0,"end":30.0,"text":"Welcome to thermodynamics.","speaker":"professor"}]',
        "retry_count": 0,
        "created_at": _now_str(),
        "updated_at": _now_str(),
    }
    base.update(overrides)
    return base


def make_chunk(
    lecture_id: str,
    chunk_index: int = 0,
    chunk_id: str | None = None,
    **overrides,
) -> dict:
    cid = chunk_id or str(uuid.uuid4())
    base = {
        "id": cid,
        "lecture_id": lecture_id,
        "user_id": FAKE_USER_ID,
        "chunk_index": chunk_index,
        "content": f"Chunk {chunk_index}: heat transfer via conduction, convection, radiation.",
        "start_time": chunk_index * 150.0,
        "end_time": (chunk_index + 1) * 150.0,
        "slide_number": (chunk_index // 4) + 1,
        "embedding": [0.1] * 768,
        "metadata": {"source": "aligned"},
        "created_at": _now_str(),
    }
    base.update(overrides)
    return base


def make_concept(
    course_id: str,
    lecture_id: str,
    concept_id: str | None = None,
    **overrides,
) -> dict:
    coid = concept_id or str(uuid.uuid4())
    base = {
        "id": coid,
        "course_id": course_id,
        "lecture_id": lecture_id,
        "user_id": FAKE_USER_ID,
        "title": "Thermodynamic System",
        "description": "A region of space defined by boundaries.",
        "category": "definition",
        "difficulty_estimate": 0.3,
        "source_chunk_ids": [],
        "embedding": [0.1] * 768,
        "created_at": _now_str(),
    }
    base.update(overrides)
    return base


def make_quiz(
    course_id: str,
    quiz_id: str | None = None,
    **overrides,
) -> dict:
    qid = quiz_id or str(uuid.uuid4())
    base = {
        "id": qid,
        "course_id": course_id,
        "user_id": FAKE_USER_ID,
        "title": "Practice Quiz - PHYS 201",
        "status": "ready",
        "question_count": 5,
        "difficulty": "medium",
        "best_score": None,
        "attempt_count": 0,
        "target_assessment_id": None,
        "created_at": _now_str(),
    }
    base.update(overrides)
    return base


def make_quiz_question(
    quiz_id: str,
    question_index: int = 0,
    question_id: str | None = None,
    **overrides,
) -> dict:
    qid = question_id or str(uuid.uuid4())
    base = {
        "id": qid,
        "quiz_id": quiz_id,
        "question_index": question_index,
        "question_type": "mcq",
        "question_text": "Which describes a thermodynamic system?",
        "options": [
            {"label": "A", "text": "A region defined by boundaries", "is_correct": True},
            {"label": "B", "text": "Any object that produces heat", "is_correct": False},
            {"label": "C", "text": "A machine that converts energy", "is_correct": False},
            {"label": "D", "text": "A chemical reaction", "is_correct": False},
        ],
        "correct_answer": "A",
        "explanation": "A thermodynamic system is a region defined by boundaries.",
        "source_chunk_ids": [],
        "concept_id": None,
        "difficulty": 0.3,
        "created_at": _now_str(),
    }
    base.update(overrides)
    return base


def make_search_result(
    lecture_id: str,
    chunk_id: str | None = None,
    **overrides,
) -> dict:
    """Factory for a hybrid_search service result."""
    cid = chunk_id or str(uuid.uuid4())
    base = {
        "chunk_id": cid,
        "lecture_id": lecture_id,
        "lecture_title": "Lecture 1: Intro to Thermodynamics",
        "content": "Heat transfer occurs through conduction, convection, and radiation.",
        "start_time": 110.0,
        "end_time": 135.5,
        "slide_number": 4,
        "score": 0.85,
    }
    base.update(overrides)
    return base
