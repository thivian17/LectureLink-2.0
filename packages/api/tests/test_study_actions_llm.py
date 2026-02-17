"""Tests for the LLM-powered study actions service."""

from __future__ import annotations

import json
import uuid
from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from lecturelink_api.services.study_actions import LectureGap, StudyAction
from lecturelink_api.services.study_actions_llm import (
    VALID_ACTION_TYPES,
    _build_llm_context,
    _validate_llm_actions,
    get_study_actions_llm,
)

COURSE_A = str(uuid.uuid4())
COURSE_B = str(uuid.uuid4())
USER_ID = str(uuid.uuid4())


def _make_course(cid: str, name: str = "Test Course", code: str | None = "CS101"):
    return {
        "id": cid,
        "name": name,
        "code": code,
        "user_id": USER_ID,
        "semester_start": "2025-01-13",
        "semester_end": "2025-05-10",
        "meeting_days": ["Monday", "Wednesday"],
        "holidays": [],
        "target_grade": 0.9,
    }


def _make_context(
    syllabus=True,
    needs_review=False,
    lecture_count=5,
    upcoming=None,
):
    syl = None
    if syllabus:
        syl = {
            "id": str(uuid.uuid4()),
            "status": "processed",
            "needs_review": needs_review,
            "reviewed_at": None if needs_review else "2025-01-20T00:00:00",
        }
    return {
        "syllabus": syl,
        "lecture_count": lecture_count,
        "upcoming_assessments": upcoming or [],
    }


def _make_performance(weak_concepts=None, overall_accuracy=0.75):
    concepts = []
    weak_ids = []
    if weak_concepts:
        for wc in weak_concepts:
            cid = str(uuid.uuid4())
            concepts.append({
                "concept_id": cid,
                "title": wc["title"],
                "mastery": wc["mastery"],
                "trend": wc.get("trend", "stable"),
                "total_attempts": 5,
            })
            if wc["mastery"] < 0.5:
                weak_ids.append(cid)
    return {
        "overall": {"overall_accuracy": overall_accuracy, "quizzes_taken": 3},
        "concepts": concepts,
        "weak_concepts": weak_ids,
        "strong_concepts": [],
        "quiz_history": [],
    }


def _valid_llm_action(cid: str, course: dict, **overrides):
    """Build a valid LLM action dict."""
    base = f"/dashboard/courses/{cid}"
    action = {
        "action_type": "upload_lectures",
        "priority": 0.85,
        "course_id": cid,
        "course_name": course["name"],
        "course_code": course.get("code"),
        "title": "You're behind on lectures",
        "description": "Upload your recent lecture materials.",
        "cta_label": "Upload Lecture",
        "cta_url": f"{base}/lectures/new",
        "metadata": {},
    }
    action.update(overrides)
    return action


# ---------------------------------------------------------------------------
# _build_llm_context
# ---------------------------------------------------------------------------


class TestBuildLLMContext:
    def test_includes_all_courses(self):
        courses = [_make_course(COURSE_A, "CS 101"), _make_course(COURSE_B, "MATH 200")]
        contexts = {COURSE_A: _make_context(), COURSE_B: _make_context()}

        result = json.loads(_build_llm_context(courses, contexts, {}, {}))

        assert len(result["courses"]) == 2
        ids = {c["course_id"] for c in result["courses"]}
        assert ids == {COURSE_A, COURSE_B}

    def test_includes_cta_urls(self):
        courses = [_make_course(COURSE_A)]
        contexts = {COURSE_A: _make_context()}

        result = json.loads(_build_llm_context(courses, contexts, {}, {}))

        cta = result["courses"][0]["cta_urls"]
        assert "upload_syllabus" in cta
        assert "review_syllabus" in cta
        assert "upload_lectures" in cta
        assert "quiz" in cta
        assert COURSE_A in cta["upload_syllabus"]

    def test_includes_lecture_gap(self):
        courses = [_make_course(COURSE_A)]
        contexts = {COURSE_A: _make_context()}
        gap = LectureGap(
            expected_count=10, actual_count=6, missing_count=4,
            last_expected_date=date(2025, 2, 10),
            next_expected_date=date(2025, 2, 12),
        )

        result = json.loads(_build_llm_context(courses, contexts, {}, {COURSE_A: gap}))

        lg = result["courses"][0]["lecture_gap"]
        assert lg["missing"] == 4
        assert lg["expected"] == 10

    def test_omits_lecture_gap_when_caught_up(self):
        courses = [_make_course(COURSE_A)]
        contexts = {COURSE_A: _make_context()}
        gap = LectureGap(expected_count=5, actual_count=5, missing_count=0)

        result = json.loads(_build_llm_context(courses, contexts, {}, {COURSE_A: gap}))

        assert "lecture_gap" not in result["courses"][0]

    def test_includes_performance_data(self):
        courses = [_make_course(COURSE_A)]
        contexts = {COURSE_A: _make_context()}
        perf = _make_performance(
            weak_concepts=[{"title": "Binary Trees", "mastery": 0.3}],
            overall_accuracy=0.65,
        )

        result = json.loads(
            _build_llm_context(courses, contexts, {COURSE_A: perf}, {})
        )

        p = result["courses"][0]["performance"]
        assert p["overall_accuracy"] == 0.65
        assert len(p["weak_concepts"]) == 1
        assert p["weak_concepts"][0]["title"] == "Binary Trees"

    def test_no_performance_for_new_course(self):
        courses = [_make_course(COURSE_A)]
        contexts = {COURSE_A: _make_context()}

        result = json.loads(_build_llm_context(courses, contexts, {}, {}))

        assert "performance" not in result["courses"][0]


# ---------------------------------------------------------------------------
# _validate_llm_actions
# ---------------------------------------------------------------------------


class TestValidateLLMActions:
    def test_valid_actions_pass_through(self):
        course = _make_course(COURSE_A)
        action = _valid_llm_action(COURSE_A, course)

        result = _validate_llm_actions({"actions": [action]}, [course])

        assert len(result) == 1
        assert isinstance(result[0], StudyAction)
        assert result[0].action_type == "upload_lectures"
        assert result[0].course_id == COURSE_A

    def test_invalid_action_type_dropped(self):
        course = _make_course(COURSE_A)
        action = _valid_llm_action(COURSE_A, course, action_type="nonexistent_type")

        result = _validate_llm_actions({"actions": [action]}, [course])

        assert len(result) == 0

    def test_invalid_course_id_dropped(self):
        course = _make_course(COURSE_A)
        action = _valid_llm_action(COURSE_A, course, course_id="invalid-id")

        result = _validate_llm_actions({"actions": [action]}, [course])

        assert len(result) == 0

    def test_malformed_cta_url_auto_corrected(self):
        course = _make_course(COURSE_A)
        action = _valid_llm_action(COURSE_A, course, cta_url="/wrong/url")

        result = _validate_llm_actions({"actions": [action]}, [course])

        assert len(result) == 1
        assert result[0].cta_url == f"/dashboard/courses/{COURSE_A}/lectures/new"

    def test_course_name_overwritten(self):
        course = _make_course(COURSE_A, name="Data Structures")
        action = _valid_llm_action(
            COURSE_A, course, course_name="data structures class"
        )

        result = _validate_llm_actions({"actions": [action]}, [course])

        assert len(result) == 1
        assert result[0].course_name == "Data Structures"

    def test_priority_clamped(self):
        course = _make_course(COURSE_A)
        action_high = _valid_llm_action(COURSE_A, course, priority=1.5)
        action_low = _valid_llm_action(COURSE_A, course, priority=-0.3)

        result = _validate_llm_actions(
            {"actions": [action_high, action_low]}, [course]
        )

        assert len(result) == 2
        assert result[0].priority == 1.0
        assert result[1].priority == 0.0

    def test_empty_actions(self):
        result = _validate_llm_actions({"actions": []}, [_make_course(COURSE_A)])
        assert result == []

    def test_non_list_actions(self):
        result = _validate_llm_actions(
            {"actions": "not a list"}, [_make_course(COURSE_A)]
        )
        assert result == []

    def test_all_action_types_accepted(self):
        course = _make_course(COURSE_A)
        actions = [
            _valid_llm_action(COURSE_A, course, action_type=at)
            for at in VALID_ACTION_TYPES
        ]

        result = _validate_llm_actions({"actions": actions}, [course])

        assert len(result) == len(VALID_ACTION_TYPES)


# ---------------------------------------------------------------------------
# get_study_actions_llm (integration with mocked Gemini)
# ---------------------------------------------------------------------------


def _mock_execute(data):
    resp = MagicMock()
    resp.data = data
    resp.count = len(data) if data else 0
    return resp


def _mock_chain(final_data):
    chain = MagicMock()
    chain.execute.return_value = _mock_execute(final_data)
    for method in ("select", "eq", "in_", "order", "limit", "gte", "lte"):
        getattr(chain, method).return_value = chain
    return chain


def _mock_supabase(courses=None, syllabi=None, lectures=None, assessments=None):
    """Build a mock Supabase client with configurable table responses."""
    sb = MagicMock()

    table_map = {
        "courses": courses if courses is not None else [],
        "syllabi": syllabi if syllabi is not None else [],
        "lectures": lectures if lectures is not None else [],
        "assessments": assessments if assessments is not None else [],
    }

    def table_router(name):
        return _mock_chain(table_map.get(name, []))

    sb.table.side_effect = table_router
    return sb


def _mock_gemini_response(actions_list: list[dict]):
    """Build a mock Gemini response with .text attribute."""
    response = MagicMock()
    response.text = json.dumps({"actions": actions_list})
    return response


class TestGetStudyActionsLLM:
    @pytest.mark.asyncio
    async def test_no_courses_skips_llm_call(self):
        sb = _mock_supabase(courses=[])

        with patch(
            "lecturelink_api.services.study_actions_llm._get_client"
        ) as mock_client:
            result = await get_study_actions_llm(sb, USER_ID)

        assert result == []
        mock_client.assert_not_called()

    @pytest.mark.asyncio
    async def test_calls_gemini_with_correct_config(self):
        course = _make_course(COURSE_A, name="DS", code="CS201")
        sb = _mock_supabase(courses=[course])

        mock_gen = AsyncMock(return_value=_mock_gemini_response([]))

        with patch(
            "lecturelink_api.services.study_actions_llm._get_client"
        ) as mock_client:
            mock_client.return_value.aio.models.generate_content = mock_gen
            await get_study_actions_llm(sb, USER_ID)

        mock_gen.assert_awaited_once()
        call_kwargs = mock_gen.call_args
        assert call_kwargs.kwargs["model"] == "gemini-2.5-flash"
        config = call_kwargs.kwargs["config"]
        assert config["temperature"] == 0.4
        assert config["response_mime_type"] == "application/json"

    @pytest.mark.asyncio
    async def test_returns_sorted_actions(self):
        course = _make_course(COURSE_A, name="DS", code="CS201")
        sb = _mock_supabase(courses=[course])

        actions = [
            _valid_llm_action(COURSE_A, course, priority=0.3, title="Low"),
            _valid_llm_action(COURSE_A, course, priority=0.9, title="High"),
            _valid_llm_action(COURSE_A, course, priority=0.6, title="Mid"),
        ]
        mock_gen = AsyncMock(return_value=_mock_gemini_response(actions))

        with patch(
            "lecturelink_api.services.study_actions_llm._get_client"
        ) as mock_client:
            mock_client.return_value.aio.models.generate_content = mock_gen
            result = await get_study_actions_llm(sb, USER_ID)

        assert len(result) == 3
        assert result[0].priority == 0.9
        assert result[1].priority == 0.6
        assert result[2].priority == 0.3

    @pytest.mark.asyncio
    async def test_respects_limit(self):
        course = _make_course(COURSE_A, name="DS", code="CS201")
        sb = _mock_supabase(courses=[course])

        actions = [
            _valid_llm_action(COURSE_A, course, priority=0.9 - i * 0.1, title=f"A{i}")
            for i in range(5)
        ]
        mock_gen = AsyncMock(return_value=_mock_gemini_response(actions))

        with patch(
            "lecturelink_api.services.study_actions_llm._get_client"
        ) as mock_client:
            mock_client.return_value.aio.models.generate_content = mock_gen
            result = await get_study_actions_llm(sb, USER_ID, limit=2)

        assert len(result) == 2

    @pytest.mark.asyncio
    async def test_llm_failure_returns_empty(self):
        course = _make_course(COURSE_A, name="DS", code="CS201")
        sb = _mock_supabase(courses=[course])

        mock_gen = AsyncMock(side_effect=RuntimeError("API error"))

        with patch(
            "lecturelink_api.services.study_actions_llm._get_client"
        ) as mock_client:
            mock_client.return_value.aio.models.generate_content = mock_gen
            result = await get_study_actions_llm(sb, USER_ID)

        assert result == []

    @pytest.mark.asyncio
    async def test_malformed_json_returns_empty(self):
        course = _make_course(COURSE_A, name="DS", code="CS201")
        sb = _mock_supabase(courses=[course])

        bad_response = MagicMock()
        bad_response.text = "not valid json {{"
        mock_gen = AsyncMock(return_value=bad_response)

        with patch(
            "lecturelink_api.services.study_actions_llm._get_client"
        ) as mock_client:
            mock_client.return_value.aio.models.generate_content = mock_gen
            result = await get_study_actions_llm(sb, USER_ID)

        assert result == []
