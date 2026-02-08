"""Integration test fixtures.

Provides:
- Fake auth that bypasses Supabase JWT validation
- Supabase mock factory for chainable query builders
- AsyncClient for making API requests via ASGI transport
- Pre-computed pipeline outputs (so tests run without Gemini)
- Test syllabus fixtures with ground truths
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from lecturelink_api.main import app

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
    return datetime.now(timezone.utc).isoformat()


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


@pytest_asyncio.fixture()
async def client(override_auth, override_settings):
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


def mock_chain(final_data):
    """Build a chainable mock that returns final_data on .execute()."""
    chain = MagicMock()
    chain.execute.return_value = mock_execute(final_data)
    for method in (
        "select", "insert", "update", "delete",
        "eq", "order", "single", "maybe_single",
        "limit", "not_",
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
