"""Tests for onboarding integration: assessment results, course creation flags, priority weights."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from lecturelink_api.main import app
from lecturelink_api.models.api_models import AssessmentResponse
from lecturelink_api.services.priority import (
    ACTIVE_MODE_WEIGHTS,
    REVIEW_MODE_WEIGHTS,
    get_priority_weights,
)

# ---------------------------------------------------------------------------
# Fake user / helpers
# ---------------------------------------------------------------------------

FAKE_USER_ID = str(uuid.uuid4())
FAKE_OTHER_USER_ID = str(uuid.uuid4())
FAKE_EMAIL = "test@university.edu"
FAKE_TOKEN = "fake-jwt-token"


def _fake_user():
    return {"id": FAKE_USER_ID, "email": FAKE_EMAIL, "token": FAKE_TOKEN}


def _now_str():
    return datetime.now(UTC).isoformat()


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def _override_auth():
    from lecturelink_api.auth import get_current_user

    app.dependency_overrides[get_current_user] = lambda: _fake_user()
    yield
    app.dependency_overrides.pop(get_current_user, None)


@pytest.fixture()
def _override_settings():
    from lecturelink_api.config import Settings, get_settings

    fake_settings = Settings(
        SUPABASE_URL="https://fake.supabase.co",
        SUPABASE_ANON_KEY="fake-anon-key",
    )
    app.dependency_overrides[get_settings] = lambda: fake_settings
    yield fake_settings
    app.dependency_overrides.pop(get_settings, None)


@pytest_asyncio.fixture()
async def client(_override_auth, _override_settings):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


# ---------------------------------------------------------------------------
# Mock helpers
# ---------------------------------------------------------------------------


def _mock_execute(data):
    resp = MagicMock()
    resp.data = data
    return resp


def _mock_chain(final_data):
    chain = MagicMock()
    chain.execute.return_value = _mock_execute(final_data)
    for method in (
        "select", "insert", "update", "delete",
        "eq", "order", "single", "maybe_single",
    ):
        getattr(chain, method).return_value = chain
    return chain


def _sample_course(course_id: str | None = None) -> dict:
    cid = course_id or str(uuid.uuid4())
    return {
        "id": cid,
        "user_id": FAKE_USER_ID,
        "name": "Intro to CS",
        "code": "CS101",
        "semester_start": "2026-01-12",
        "semester_end": "2026-05-01",
        "meeting_days": ["Tue", "Thu"],
        "meeting_time": "10:00",
        "holidays": [],
        "target_grade": 0.8,
        "created_at": _now_str(),
        "updated_at": _now_str(),
        "onboarding_completed_at": None,
    }


def _sample_assessment(
    course_id: str,
    assessment_id: str | None = None,
    student_score: float | None = None,
) -> dict:
    aid = assessment_id or str(uuid.uuid4())
    return {
        "id": aid,
        "course_id": course_id,
        "syllabus_id": str(uuid.uuid4()),
        "title": "Midterm 1",
        "type": "exam",
        "due_date": "2026-03-15",
        "due_date_raw": "Week 8 Thursday",
        "is_date_ambiguous": False,
        "weight_percent": 20.0,
        "student_score": student_score,
        "topics": ["Chapter 1", "Chapter 2"],
        "created_at": _now_str(),
    }


# ---------------------------------------------------------------------------
# Test: save_assessment_result
# ---------------------------------------------------------------------------


class TestSaveAssessmentResult:
    @pytest.mark.asyncio
    async def test_save_assessment_result(self, client):
        course_id = str(uuid.uuid4())
        assessment_id = str(uuid.uuid4())

        assessment_row = _sample_assessment(course_id, assessment_id)
        updated_row = {**assessment_row, "student_score": 85.0}
        course_row = _sample_course(course_id)

        # sb.table() is called 3 times:
        #   1. select assessment (verify exists)
        #   2. select course (verify ownership)
        #   3. update assessment (set student_score)
        with patch("lecturelink_api.routers.assessments.create_client") as mock_create:
            sb = MagicMock()
            mock_create.return_value = sb

            call_count = 0

            def table_side_effect(table_name):
                nonlocal call_count
                call_count += 1
                if table_name == "assessments" and call_count == 1:
                    return _mock_chain([{"id": assessment_id, "course_id": course_id}])
                if table_name == "courses":
                    return _mock_chain([course_row])
                # update call
                return _mock_chain([updated_row])

            sb.table.side_effect = table_side_effect

            resp = await client.put(
                f"/api/assessments/{assessment_id}/result",
                json={"score_percent": 85.0},
            )

        assert resp.status_code == 200
        data = resp.json()
        assert data["student_score"] == 85.0
        assert data["id"] == assessment_id

    @pytest.mark.asyncio
    async def test_save_result_validation_too_low(self, client):
        resp = await client.put(
            f"/api/assessments/{uuid.uuid4()}/result",
            json={"score_percent": -1.0},
        )
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_save_result_validation_too_high(self, client):
        resp = await client.put(
            f"/api/assessments/{uuid.uuid4()}/result",
            json={"score_percent": 101.0},
        )
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_save_result_wrong_user(self, client):
        """Saving a result for an assessment belonging to a different user returns 404."""
        course_id = str(uuid.uuid4())
        assessment_id = str(uuid.uuid4())

        assessment_row = {"id": assessment_id, "course_id": course_id}
        # Course owned by a *different* user → ownership check returns empty
        with patch("lecturelink_api.routers.assessments.create_client") as mock_create:
            sb = MagicMock()
            mock_create.return_value = sb

            call_count = 0

            def table_side_effect(table_name):
                nonlocal call_count
                call_count += 1
                if table_name == "assessments" and call_count == 1:
                    return _mock_chain([assessment_row])
                if table_name == "courses":
                    # No matching rows → ownership fails
                    return _mock_chain([])
                return _mock_chain([])

            sb.table.side_effect = table_side_effect

            resp = await client.put(
                f"/api/assessments/{assessment_id}/result",
                json={"score_percent": 85.0},
            )

        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Test: course creation onboarding flags
# ---------------------------------------------------------------------------


class TestCourseCreationOnboardingFlag:
    @pytest.mark.asyncio
    async def test_create_course_needs_onboarding(self, client):
        course = _sample_course()

        with patch("lecturelink_api.routers.courses.create_client") as mock_create:
            sb = MagicMock()
            mock_create.return_value = sb

            call_count = 0

            def table_side_effect(table_name):
                nonlocal call_count
                call_count += 1
                if call_count == 1:
                    # insert call
                    return _mock_chain([course])
                # select existing courses — only the one just created
                return _mock_chain([{"id": course["id"]}])

            sb.table.side_effect = table_side_effect

            resp = await client.post("/api/courses", json={
                "name": "Intro to CS",
                "code": "CS101",
                "semester_start": "2026-01-12",
                "semester_end": "2026-05-01",
            })

        assert resp.status_code == 201
        data = resp.json()
        assert data["needs_onboarding"] is True
        assert data["is_first_course"] is True
        assert data["onboarding_completed_at"] is None

    @pytest.mark.asyncio
    async def test_create_course_not_first_course(self, client):
        course = _sample_course()
        other_course_id = str(uuid.uuid4())

        with patch("lecturelink_api.routers.courses.create_client") as mock_create:
            sb = MagicMock()
            mock_create.return_value = sb

            call_count = 0

            def table_side_effect(table_name):
                nonlocal call_count
                call_count += 1
                if call_count == 1:
                    # insert call
                    return _mock_chain([course])
                # select existing courses — two courses exist
                return _mock_chain([
                    {"id": course["id"]},
                    {"id": other_course_id},
                ])

            sb.table.side_effect = table_side_effect

            resp = await client.post("/api/courses", json={
                "name": "Intro to CS",
                "semester_start": "2026-01-12",
                "semester_end": "2026-05-01",
            })

        assert resp.status_code == 201
        data = resp.json()
        assert data["needs_onboarding"] is True
        assert data["is_first_course"] is False


# ---------------------------------------------------------------------------
# Test: priority weights
# ---------------------------------------------------------------------------


class TestPriorityWeights:
    def test_active_mode_weights(self):
        weights = get_priority_weights("active")
        assert weights == ACTIVE_MODE_WEIGHTS
        assert weights["deadline_urgency"] == 0.4
        assert weights["grade_impact"] == 0.3
        assert weights["mastery_gap"] == 0.2
        assert weights["fsrs_due"] == 0.1

    def test_review_mode_weights(self):
        weights = get_priority_weights("review")
        assert weights == REVIEW_MODE_WEIGHTS
        assert weights["deadline_urgency"] == 0.0
        assert weights["grade_impact"] == 0.0
        assert weights["mastery_gap"] == 0.6
        assert weights["fsrs_due"] == 0.4

    def test_default_is_active(self):
        assert get_priority_weights() == ACTIVE_MODE_WEIGHTS

    def test_unknown_mode_returns_active(self):
        assert get_priority_weights("something_else") == ACTIVE_MODE_WEIGHTS


# ---------------------------------------------------------------------------
# Test: AssessmentResponse includes student_score
# ---------------------------------------------------------------------------


class TestAssessmentResponseModel:
    def test_includes_student_score(self):
        data = {
            "id": str(uuid.uuid4()),
            "course_id": str(uuid.uuid4()),
            "title": "Final Exam",
            "type": "exam",
            "created_at": _now_str(),
            "student_score": 92.5,
        }
        model = AssessmentResponse(**data)
        assert model.student_score == 92.5

    def test_student_score_defaults_to_none(self):
        data = {
            "id": str(uuid.uuid4()),
            "course_id": str(uuid.uuid4()),
            "title": "Final Exam",
            "type": "exam",
            "created_at": _now_str(),
        }
        model = AssessmentResponse(**data)
        assert model.student_score is None
