"""Tests for the Study Tutor grading service, session management, and router."""

from __future__ import annotations

import json
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from lecturelink_api.services.tutor import (
    complete_session,
    create_session,
    get_active_session,
    get_session_entry_data,
    get_session_history,
    get_session_summary,
    log_session_event,
    pause_session,
    resume_session,
    update_session_progress,
)
from lecturelink_api.services.tutor_grading import (
    _normalize_for_comparison,
    classify_misconception,
    grade_answer,
    grade_fill_in_blank,
    grade_mcq,
    grade_ordering,
    grade_short_answer,
    grade_true_false,
)

# ──────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────


def _mock_execute(data):
    resp = MagicMock()
    resp.data = data
    resp.count = 0
    return resp


def _mock_chain(final_data):
    """Return a mock that supports chained Supabase query builder calls."""
    chain = MagicMock()
    chain.execute.return_value = _mock_execute(final_data)
    for method in (
        "select", "insert", "update", "delete", "upsert",
        "eq", "in_", "order", "limit", "single", "maybe_single",
        "not_", "gte", "lte", "desc",
    ):
        getattr(chain, method).return_value = chain
    chain.not_.is_.return_value = chain
    return chain


SESSION_ROW = {
    "id": "sess-1",
    "user_id": "user-1",
    "course_id": "course-1",
    "mode": "full_lesson",
    "status": "active",
    "lesson_plan": {"concepts": [{"title": "Trees"}]},
    "current_concept_index": 0,
    "current_step_index": 0,
    "concepts_planned": 1,
    "concepts_completed": 0,
    "questions_asked": 0,
    "questions_correct": 0,
    "duration_seconds": 0,
    "suggested_duration_minutes": 25,
    "started_at": "2025-06-01T00:00:00+00:00",
    "created_at": "2025-06-01T00:00:00+00:00",
}


# ──────────────────────────────────────────────────────────────────────
# Grading: MCQ
# ──────────────────────────────────────────────────────────────────────


class TestGradeMCQ:
    @pytest.mark.asyncio
    async def test_grade_mcq_correct(self):
        question = {
            "question_type": "mcq",
            "correct_answer": "B",
            "explanation": "B is right because...",
        }
        result = await grade_mcq(question, "B")
        assert result.is_correct is True
        assert result.grading_confidence == 1.0
        assert "B is right because" in result.feedback

    @pytest.mark.asyncio
    async def test_grade_mcq_correct_case_insensitive(self):
        question = {"question_type": "mcq", "correct_answer": "C"}
        result = await grade_mcq(question, "  c  ")
        assert result.is_correct is True

    @pytest.mark.asyncio
    async def test_grade_mcq_incorrect(self):
        question = {
            "question_type": "mcq",
            "correct_answer": "A",
            "explanation": "A is the answer.",
        }
        result = await grade_mcq(question, "D")
        assert result.is_correct is False
        assert "A" in result.feedback


# ──────────────────────────────────────────────────────────────────────
# Grading: True/False
# ──────────────────────────────────────────────────────────────────────


class TestGradeTrueFalse:
    @pytest.mark.asyncio
    @pytest.mark.parametrize("answer", ["true", "True", "TRUE", "T", "t"])
    async def test_true_variants_correct(self, answer):
        question = {"correct_answer": "true"}
        result = await grade_true_false(question, answer)
        assert result.is_correct is True
        assert result.grading_confidence == 1.0

    @pytest.mark.asyncio
    @pytest.mark.parametrize("answer", ["false", "False", "FALSE", "F", "f"])
    async def test_false_variants_correct(self, answer):
        question = {"correct_answer": "false"}
        result = await grade_true_false(question, answer)
        assert result.is_correct is True

    @pytest.mark.asyncio
    async def test_true_false_incorrect(self):
        question = {"correct_answer": "true"}
        result = await grade_true_false(question, "false")
        assert result.is_correct is False

    @pytest.mark.asyncio
    async def test_unrecognizable_answer(self):
        question = {"correct_answer": "true"}
        result = await grade_true_false(question, "maybe")
        assert result.is_correct is False
        assert "True or False" in result.feedback


# ──────────────────────────────────────────────────────────────────────
# Grading: Fill-in-the-blank
# ──────────────────────────────────────────────────────────────────────


class TestGradeFillInBlank:
    @pytest.mark.asyncio
    async def test_exact_match(self):
        question = {
            "correct_answer": "binary search",
            "acceptable_answers": ["binary search"],
        }
        result = await grade_fill_in_blank(question, "binary search")
        assert result.is_correct is True

    @pytest.mark.asyncio
    async def test_case_insensitive_match(self):
        question = {
            "correct_answer": "Binary Search",
            "acceptable_answers": ["binary search"],
        }
        result = await grade_fill_in_blank(question, "BINARY SEARCH")
        assert result.is_correct is True

    @pytest.mark.asyncio
    async def test_fuzzy_nlogn_match(self):
        """Various representations of n log n should all match."""
        question = {
            "correct_answer": "n log n",
            "acceptable_answers": ["n log n", "nlogn", "n*log(n)"],
        }
        result = await grade_fill_in_blank(question, "nlogn")
        assert result.is_correct is True

    @pytest.mark.asyncio
    async def test_fuzzy_big_o_match(self):
        """O(n log n) should match n log n."""
        question = {
            "correct_answer": "n log n",
            "acceptable_answers": ["n log n", "O(n log n)"],
        }
        result = await grade_fill_in_blank(question, "O(n log n)")
        assert result.is_correct is True

    @pytest.mark.asyncio
    async def test_incorrect_answer(self):
        question = {
            "correct_answer": "binary search",
            "acceptable_answers": ["binary search"],
        }
        result = await grade_fill_in_blank(question, "linear search")
        assert result.is_correct is False


class TestNormalizeForComparison:
    def test_strips_whitespace(self):
        assert _normalize_for_comparison("  hello  ") == "hello"

    def test_removes_big_o_wrapper(self):
        assert _normalize_for_comparison("O(n log n)") == "nlogn"

    def test_removes_spaces_and_stars(self):
        assert _normalize_for_comparison("n * log(n)") == "nlogn"


# ──────────────────────────────────────────────────────────────────────
# Grading: Ordering
# ──────────────────────────────────────────────────────────────────────


class TestGradeOrdering:
    @pytest.mark.asyncio
    async def test_correct_ordering(self):
        question = {"correct_answer": ["A", "B", "C"]}
        result = await grade_ordering(question, "A, B, C")
        assert result.is_correct is True

    @pytest.mark.asyncio
    async def test_wrong_ordering(self):
        question = {"correct_answer": ["A", "B", "C"]}
        result = await grade_ordering(question, "C, B, A")
        assert result.is_correct is False

    @pytest.mark.asyncio
    async def test_json_list_input(self):
        question = {"correct_answer": ["X", "Y", "Z"]}
        result = await grade_ordering(question, '["X", "Y", "Z"]')
        assert result.is_correct is True


# ──────────────────────────────────────────────────────────────────────
# Grading: Misconception classifier
# ──────────────────────────────────────────────────────────────────────


class TestClassifyMisconception:
    def test_uses_existing_classification(self):
        result = {"misconception_type": "near_miss"}
        assert classify_misconception(result) == "near_miss"

    def test_fundamental_from_heuristic(self):
        result = {
            "rubric_evaluation": {
                "criteria_met": ["A"],
                "criteria_missed": ["B", "C", "D"],
            }
        }
        assert classify_misconception(result) == "fundamental"

    def test_near_miss_from_heuristic(self):
        result = {
            "rubric_evaluation": {
                "criteria_met": ["A", "B", "C"],
                "criteria_missed": ["D"],
            }
        }
        assert classify_misconception(result) == "near_miss"

    def test_returns_none_when_no_data(self):
        assert classify_misconception({}) is None


# ──────────────────────────────────────────────────────────────────────
# Grading: Dispatcher
# ──────────────────────────────────────────────────────────────────────


class TestGradeAnswerDispatch:
    @pytest.mark.asyncio
    async def test_routes_mcq(self):
        question = {"question_type": "mcq", "correct_answer": "A"}
        result = await grade_answer(question, "A")
        assert result.is_correct is True
        assert result.grading_confidence == 1.0

    @pytest.mark.asyncio
    async def test_routes_true_false(self):
        question = {"question_type": "true_false", "correct_answer": "true"}
        result = await grade_answer(question, "T")
        assert result.is_correct is True

    @pytest.mark.asyncio
    async def test_routes_fill_in_blank(self):
        question = {
            "question_type": "fill_in_blank",
            "correct_answer": "stack",
            "acceptable_answers": ["stack"],
        }
        result = await grade_answer(question, "stack")
        assert result.is_correct is True

    @pytest.mark.asyncio
    async def test_routes_ordering(self):
        question = {
            "question_type": "ordering",
            "correct_answer": ["1", "2"],
        }
        result = await grade_answer(question, "1, 2")
        assert result.is_correct is True


# ──────────────────────────────────────────────────────────────────────
# Grading: Short answer (AI-graded, mocked)
# ──────────────────────────────────────────────────────────────────────


class TestGradeShortAnswer:
    @pytest.mark.asyncio
    async def test_calls_gemini_and_returns_result(self):
        """Mock the Gemini client and verify short-answer grading."""
        gemini_response = json.dumps({
            "is_correct": True,
            "partially_correct": False,
            "criteria_met": ["mentions recursion"],
            "criteria_missed": [],
            "misconceptions_detected": [],
            "misconception_type": None,
            "feedback": "Good explanation of recursion.",
            "confidence": 0.9,
        })

        mock_response = MagicMock()
        mock_response.text = gemini_response
        mock_client = MagicMock()
        mock_client.aio.models.generate_content = AsyncMock(
            return_value=mock_response,
        )

        question = {
            "question_text": "Explain recursion",
            "rubric": {
                "must_mention": ["base case", "recursive call"],
                "model_answer": "Recursion is a function calling itself.",
            },
        }

        with patch(
            "lecturelink_api.services.tutor_grading._get_client",
            return_value=mock_client,
        ):
            result = await grade_short_answer(question, "A function that calls itself")

        assert result.is_correct is True
        assert result.grading_confidence == 0.9
        assert "recursion" in result.feedback.lower()

    @pytest.mark.asyncio
    async def test_fallback_on_gemini_error(self):
        """If Gemini fails, return a safe fallback."""
        mock_client = MagicMock()
        mock_client.aio.models.generate_content = AsyncMock(
            side_effect=Exception("API error"),
        )

        question = {
            "question_text": "Explain sorting",
            "rubric": {"model_answer": "Sorting arranges elements."},
        }

        with patch(
            "lecturelink_api.services.tutor_grading._get_client",
            return_value=mock_client,
        ):
            result = await grade_short_answer(question, "bubble sort")

        assert result.is_correct is False
        assert result.grading_confidence == 0.0
        assert result.model_answer is not None


# ──────────────────────────────────────────────────────────────────────
# Session management: create / get active
# ──────────────────────────────────────────────────────────────────────


class TestSessionManagement:
    @pytest.mark.asyncio
    async def test_create_session(self):
        sb = MagicMock()
        sb.table.return_value = _mock_chain([SESSION_ROW])

        result = await create_session(
            sb, "course-1", "user-1", "full_lesson",
            lesson_plan={"concepts": [{"title": "Trees"}]},
        )
        assert result.id == "sess-1"
        assert result.mode == "full_lesson"
        assert result.concepts_planned == 1

    @pytest.mark.asyncio
    async def test_get_active_session_exists(self):
        sb = MagicMock()
        sb.table.return_value = _mock_chain([SESSION_ROW])

        result = await get_active_session(sb, "course-1", "user-1")
        assert result is not None
        assert result.status == "active"

    @pytest.mark.asyncio
    async def test_get_active_session_none(self):
        sb = MagicMock()
        sb.table.return_value = _mock_chain([])

        result = await get_active_session(sb, "course-1", "user-1")
        assert result is None


# ──────────────────────────────────────────────────────────────────────
# Session management: pause / resume
# ──────────────────────────────────────────────────────────────────────


class TestPauseResume:
    @pytest.mark.asyncio
    async def test_pause_session(self):
        sb = MagicMock()
        chain = _mock_chain([])
        sb.table.return_value = chain

        await pause_session(sb, "sess-1", "user-1")
        # Verify update was called
        chain.update.assert_called_once()
        update_payload = chain.update.call_args[0][0]
        assert update_payload["status"] == "paused"
        assert "paused_at" in update_payload

    @pytest.mark.asyncio
    async def test_resume_session(self):
        resumed = {**SESSION_ROW, "status": "active", "paused_at": None}
        sb = MagicMock()
        sb.table.return_value = _mock_chain([resumed])

        result = await resume_session(sb, "sess-1", "user-1")
        assert result.status == "active"


# ──────────────────────────────────────────────────────────────────────
# Session management: complete + summary
# ──────────────────────────────────────────────────────────────────────


class TestCompleteSession:
    @pytest.mark.asyncio
    async def test_complete_session_generates_summary(self):
        completed_row = {
            **SESSION_ROW,
            "status": "completed",
            "questions_asked": 3,
            "questions_correct": 2,
        }

        events = [
            {
                "concept_title": "Trees",
                "is_correct": True,
                "event_type": "question_answer",
            },
            {
                "concept_title": "Trees",
                "is_correct": True,
                "event_type": "question_answer",
            },
            {
                "concept_title": "Trees",
                "is_correct": False,
                "event_type": "question_answer",
            },
        ]

        sb = MagicMock()
        call_count = 0

        def table_dispatch(name):
            nonlocal call_count
            call_count += 1
            if name == "tutor_sessions":
                return _mock_chain([completed_row])
            if name == "tutor_session_events":
                return _mock_chain(events)
            if name == "mastery_scores":
                raise Exception("Phase 3 table not found")
            return _mock_chain([])

        sb.table.side_effect = table_dispatch

        summary = await complete_session(sb, "sess-1", "user-1")
        assert summary.session_id == "sess-1"
        assert summary.total_questions == 3
        assert summary.total_correct == 2
        assert summary.accuracy_percent == pytest.approx(66.7, abs=0.1)
        assert len(summary.concepts_covered) == 1
        assert summary.concepts_covered[0]["concept_title"] == "Trees"


# ──────────────────────────────────────────────────────────────────────
# Session management: log event / history
# ──────────────────────────────────────────────────────────────────────


class TestLogEventAndHistory:
    @pytest.mark.asyncio
    async def test_log_session_event(self):
        event_id = str(uuid.uuid4())
        sb = MagicMock()
        sb.table.return_value = _mock_chain([{"id": event_id}])

        result = await log_session_event(
            sb, "sess-1", "user-1", "course-1", "session_started",
        )
        assert result == event_id

    @pytest.mark.asyncio
    async def test_get_session_history(self):
        sb = MagicMock()
        sb.table.return_value = _mock_chain([
            SESSION_ROW,
            {**SESSION_ROW, "id": "sess-2", "status": "completed"},
        ])

        result = await get_session_history(sb, "course-1", "user-1")
        assert len(result) == 2

    @pytest.mark.asyncio
    async def test_no_duplicate_active_sessions(self):
        """get_active_session returns the most recent (first row)."""
        sb = MagicMock()
        sb.table.return_value = _mock_chain([SESSION_ROW])

        result = await get_active_session(sb, "course-1", "user-1")
        assert result is not None
        assert result.id == "sess-1"


# ──────────────────────────────────────────────────────────────────────
# Session management: update progress
# ──────────────────────────────────────────────────────────────────────


class TestUpdateProgress:
    @pytest.mark.asyncio
    async def test_update_session_progress(self):
        sb = MagicMock()
        current_chain = _mock_chain({
            "questions_asked": 5,
            "questions_correct": 3,
            "duration_seconds": 120,
            "concepts_completed": 1,
        })
        update_chain = _mock_chain([])

        calls = []

        def table_dispatch(name):
            if not calls:
                calls.append(1)
                return current_chain
            return update_chain

        sb.table.side_effect = table_dispatch

        await update_session_progress(
            sb, "sess-1", "user-1",
            questions_asked_delta=1,
            questions_correct_delta=1,
            duration_delta=30,
        )

        update_chain.update.assert_called_once()
        payload = update_chain.update.call_args[0][0]
        assert payload["questions_asked"] == 6
        assert payload["questions_correct"] == 4
        assert payload["duration_seconds"] == 150


# ──────────────────────────────────────────────────────────────────────
# Session management: entry data
# ──────────────────────────────────────────────────────────────────────


class TestGetSessionEntryData:
    @pytest.mark.asyncio
    async def test_entry_endpoint_returns_assessments(self):
        assessments = [
            {
                "id": "a1",
                "title": "Midterm",
                "due_date": "2099-12-01T00:00:00+00:00",
                "weight_percent": 30.0,
            },
        ]

        sb = MagicMock()

        def table_dispatch(name):
            if name == "assessments":
                return _mock_chain(assessments)
            if name == "tutor_sessions":
                return _mock_chain([])
            if name == "mastery_scores":
                raise Exception("not deployed")
            return _mock_chain([])

        sb.table.side_effect = table_dispatch

        result = await get_session_entry_data(sb, "course-1", "user-1")
        assert len(result.upcoming_assessments) == 1
        assert result.upcoming_assessments[0].title == "Midterm"
        assert result.active_session is None
        assert result.suggested_duration_minutes == 25


# ──────────────────────────────────────────────────────────────────────
# Session management: get_session_summary
# ──────────────────────────────────────────────────────────────────────


class TestGetSessionSummary:
    @pytest.mark.asyncio
    async def test_summary_for_active_session(self):
        active_row = {
            **SESSION_ROW,
            "questions_asked": 2,
            "questions_correct": 1,
        }
        events = [
            {
                "concept_title": "Graphs",
                "is_correct": True,
                "event_type": "question_answer",
            },
            {
                "concept_title": "Graphs",
                "is_correct": False,
                "event_type": "question_answer",
            },
        ]

        sb = MagicMock()

        def table_dispatch(name):
            if name == "tutor_sessions":
                return _mock_chain(active_row)
            if name == "tutor_session_events":
                return _mock_chain(events)
            if name == "mastery_scores":
                raise Exception("not deployed")
            return _mock_chain([])

        sb.table.side_effect = table_dispatch

        summary = await get_session_summary(sb, "sess-1", "user-1")
        assert summary.total_questions == 2
        assert summary.total_correct == 1
        assert summary.accuracy_percent == 50.0


# ──────────────────────────────────────────────────────────────────────
# Router tests
# ──────────────────────────────────────────────────────────────────────


class TestTutorRouter:
    """Integration tests for tutor API endpoints."""

    def _make_sb(self, extra_tables=None):
        """Build a mock Supabase client with standard tables."""
        sb = MagicMock()

        course = {
            "id": "course-1",
            "user_id": "user-1",
            "name": "CS201",
            "code": "CS201",
        }

        tables = {
            "courses": [course],
            "tutor_sessions": [],
            "tutor_session_events": [{"id": "ev-default"}],
            "assessments": [],
            "mastery_scores": [],
            "grading_feedback": [],
            **(extra_tables or {}),
        }

        def table_dispatch(name):
            data = tables.get(name, [])
            if name == "mastery_scores" and not data:
                raise Exception("Phase 3 not deployed")
            return _mock_chain(data)

        sb.table.side_effect = table_dispatch
        return sb, course

    @pytest.mark.asyncio
    async def test_start_session(self):
        from lecturelink_api.routers.tutor import start_session

        sb, _ = self._make_sb(extra_tables={
            "tutor_sessions": [SESSION_ROW],
        })

        with patch(
            "lecturelink_api.routers.tutor.get_authenticated_supabase", return_value=sb,
        ):
            result = await start_session(
                course_id="course-1",
                body=MagicMock(
                    mode="full_lesson",
                    custom_topic=None,
                    target_assessment_id=None,
                ),
                user={"id": "user-1", "token": "tok", "email": "a@b.com"},
                settings=MagicMock(),
            )

        # Should return existing active session instead of creating new
        assert result.id == "sess-1"

    @pytest.mark.asyncio
    async def test_pause_and_resume(self):
        from lecturelink_api.routers.tutor import (
            pause_session_endpoint,
            resume_session_endpoint,
        )

        sb, _ = self._make_sb(extra_tables={
            "tutor_sessions": [SESSION_ROW],
        })
        user = {"id": "user-1", "token": "tok", "email": "a@b.com"}

        with patch(
            "lecturelink_api.routers.tutor.get_authenticated_supabase", return_value=sb,
        ):
            pause_result = await pause_session_endpoint(
                session_id="sess-1", user=user, settings=MagicMock(),
            )
            assert pause_result["status"] == "paused"

        # For resume, return an active session
        sb2, _ = self._make_sb(extra_tables={
            "tutor_sessions": [{**SESSION_ROW, "status": "active"}],
        })
        with patch(
            "lecturelink_api.routers.tutor.get_authenticated_supabase", return_value=sb2,
        ):
            resume_result = await resume_session_endpoint(
                session_id="sess-1", user=user, settings=MagicMock(),
            )
            assert resume_result.status == "active"

    @pytest.mark.asyncio
    async def test_complete_and_summary(self):
        from lecturelink_api.routers.tutor import complete_session_endpoint

        completed = {
            **SESSION_ROW,
            "status": "completed",
            "questions_asked": 2,
            "questions_correct": 1,
        }
        events = [
            {
                "id": "ev-1",
                "concept_title": "Trees",
                "is_correct": True,
                "event_type": "question_answer",
            },
            {
                "id": "ev-2",
                "concept_title": "Trees",
                "is_correct": False,
                "event_type": "question_answer",
            },
        ]

        sb = MagicMock()

        def table_dispatch(name):
            if name == "tutor_sessions":
                return _mock_chain([completed])
            if name == "tutor_session_events":
                return _mock_chain(events)
            if name == "mastery_scores":
                raise Exception("not deployed")
            return _mock_chain([])

        sb.table.side_effect = table_dispatch

        with patch(
            "lecturelink_api.routers.tutor.get_authenticated_supabase", return_value=sb,
        ):
            result = await complete_session_endpoint(
                session_id="sess-1",
                user={"id": "user-1", "token": "tok", "email": "a@b.com"},
                settings=MagicMock(),
            )

        assert result.total_questions == 2
        assert result.accuracy_percent == 50.0

    @pytest.mark.asyncio
    async def test_grading_feedback_submission(self):
        from lecturelink_api.routers.tutor import submit_grading_feedback

        sb, _ = self._make_sb(extra_tables={
            "tutor_sessions": [SESSION_ROW],
        })

        with patch(
            "lecturelink_api.routers.tutor.get_authenticated_supabase", return_value=sb,
        ):
            result = await submit_grading_feedback(
                session_id="sess-1",
                body=MagicMock(
                    event_id="ev-1",
                    feedback_type="accurate",
                    feedback_text="Looks good",
                ),
                user={"id": "user-1", "token": "tok", "email": "a@b.com"},
                settings=MagicMock(),
            )

        assert result["status"] == "submitted"

    @pytest.mark.asyncio
    async def test_session_history(self):
        from lecturelink_api.routers.tutor import history_endpoint

        sb, _ = self._make_sb(extra_tables={
            "tutor_sessions": [
                SESSION_ROW,
                {**SESSION_ROW, "id": "sess-2", "status": "completed"},
            ],
        })

        with patch(
            "lecturelink_api.routers.tutor.get_authenticated_supabase", return_value=sb,
        ):
            result = await history_endpoint(
                course_id="course-1",
                user={"id": "user-1", "token": "tok", "email": "a@b.com"},
                settings=MagicMock(),
            )

        assert len(result) == 2

    @pytest.mark.asyncio
    async def test_answer_question_correct(self):
        from lecturelink_api.routers.tutor import answer_question

        session_with_plan = {
            **SESSION_ROW,
            "lesson_plan": {
                "concepts": [{
                    "title": "Trees",
                    "questions": [{
                        "question_id": "q-1",
                        "question_type": "mcq",
                        "question_text": "What is a tree?",
                        "correct_answer": "A",
                        "explanation": "A tree is...",
                    }],
                }],
            },
        }

        sb = MagicMock()
        event_id = str(uuid.uuid4())

        def table_dispatch(name):
            if name == "tutor_sessions":
                return _mock_chain([session_with_plan])
            if name == "tutor_session_events":
                return _mock_chain([{"id": event_id}])
            return _mock_chain([])

        sb.table.side_effect = table_dispatch

        with patch(
            "lecturelink_api.routers.tutor.get_authenticated_supabase", return_value=sb,
        ):
            result = await answer_question(
                session_id="sess-1",
                body=MagicMock(
                    question_id="q-1",
                    student_answer="A",
                    time_spent_seconds=10,
                ),
                user={"id": "user-1", "token": "tok", "email": "a@b.com"},
                settings=MagicMock(),
            )

        assert result.is_correct is True

    @pytest.mark.asyncio
    async def test_answer_question_incorrect(self):
        from lecturelink_api.routers.tutor import answer_question

        session_with_plan = {
            **SESSION_ROW,
            "lesson_plan": {
                "concepts": [{
                    "title": "Trees",
                    "questions": [{
                        "question_id": "q-1",
                        "question_type": "mcq",
                        "question_text": "What is a tree?",
                        "correct_answer": "A",
                    }],
                }],
            },
        }

        sb = MagicMock()
        event_id = str(uuid.uuid4())

        def table_dispatch(name):
            if name == "tutor_sessions":
                return _mock_chain([session_with_plan])
            if name == "tutor_session_events":
                return _mock_chain([{"id": event_id}])
            return _mock_chain([])

        sb.table.side_effect = table_dispatch

        with patch(
            "lecturelink_api.routers.tutor.get_authenticated_supabase", return_value=sb,
        ):
            result = await answer_question(
                session_id="sess-1",
                body=MagicMock(
                    question_id="q-1",
                    student_answer="C",
                    time_spent_seconds=5,
                ),
                user={"id": "user-1", "token": "tok", "email": "a@b.com"},
                settings=MagicMock(),
            )

        assert result.is_correct is False
