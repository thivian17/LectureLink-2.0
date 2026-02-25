"""Tests for tutor prompts, planner, and content services."""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from lecturelink_api.services.tutor_prompts import (
    get_chat_relevance_prompt,
    get_check_question_prompt,
    get_diagnostic_questions_prompt,
    get_grading_prompt,
    get_lesson_plan_prompt,
    get_reteach_prompt,
    get_session_summary_prompt,
    get_teaching_block_prompt,
    get_tutor_system_prompt,
    get_transition_prompt,
    get_practice_prompt,
    get_summary_prompt,
    get_chat_answer_prompt,
    get_diagnostic_analysis_prompt,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

FAKE_USER_ID = str(uuid.uuid4())
FAKE_COURSE_ID = str(uuid.uuid4())
FAKE_ASSESSMENT_ID = str(uuid.uuid4())

SAMPLE_CHUNKS = [
    {
        "content": "Recursion is when a function calls itself.",
        "lecture_title": "Lecture 5: Recursion",
        "start_time": 120.0,
    },
    {
        "content": "The base case prevents infinite recursion.",
        "lecture_title": "Lecture 5: Recursion",
        "start_time": 180.0,
    },
]

SAMPLE_CONCEPTS = [
    {"concept_id": "c1", "title": "Recursion", "mastery": 0.3, "priority_score": 0.8},
    {"concept_id": "c2", "title": "Binary Search", "mastery": 0.6, "priority_score": 0.6},
    {"concept_id": "c3", "title": "Hash Tables", "mastery": 0.85, "priority_score": 0.3},
]

SAMPLE_RUBRIC = {
    "must_mention": ["base case", "recursive call"],
    "partial_credit_for": ["mentions function calling itself"],
    "common_misconceptions": [
        {"misconception": "recursion always needs a loop", "why_wrong": "uses call stack instead"},
    ],
    "model_answer": "A recursive function calls itself with a smaller input and has a base case.",
    "misconception_detection": {
        "if_mentions_loop": "confused about recursion vs iteration",
    },
}


def _mock_execute(data):
    resp = MagicMock()
    resp.data = data
    return resp


def _mock_chain(final_data):
    """Mock a Supabase query chain.

    If final_data is a list, .execute() returns it as-is.
    .maybe_single() and .single() switch the execute data to
    the first element (or None) to match Supabase behavior.
    """
    chain = MagicMock()
    chain.execute.return_value = _mock_execute(final_data)

    # maybe_single / single should return a single dict, not a list
    def _make_single_chain(*_args, **_kwargs):
        single_chain = MagicMock()
        if isinstance(final_data, list):
            single_data = final_data[0] if final_data else None
        else:
            single_data = final_data
        single_chain.execute.return_value = _mock_execute(single_data)
        # Allow further chaining after maybe_single
        for m in ("eq", "in_", "order"):
            getattr(single_chain, m).return_value = single_chain
        return single_chain

    for method in (
        "select", "insert", "update", "delete",
        "eq", "in_", "order",
    ):
        getattr(chain, method).return_value = chain

    chain.single.side_effect = _make_single_chain
    chain.maybe_single.side_effect = _make_single_chain
    return chain


# ---------------------------------------------------------------------------
# Test: Prompt templates — format and structure
# ---------------------------------------------------------------------------


class TestLessonPlanPrompt:
    def test_format(self):
        prompt = get_lesson_plan_prompt(
            concepts=SAMPLE_CONCEPTS,
            assessment_context="Midterm 1 in 5 days, worth 20%",
            mode="guided",
        )
        assert "Recursion" in prompt
        assert "Binary Search" in prompt
        assert "Midterm 1" in prompt
        assert "session_title" in prompt  # JSON output instruction
        assert "estimated_duration_minutes" in prompt
        assert "teaching_approach" in prompt
        assert "Respond ONLY with valid JSON" in prompt

    def test_custom_topic_included(self):
        prompt = get_lesson_plan_prompt(
            concepts=SAMPLE_CONCEPTS,
            assessment_context="Final exam",
            mode="guided",
            custom_topic="Merge Sort",
        )
        assert "Merge Sort" in prompt
        assert "specifically requested" in prompt


class TestCheckQuestionPrompt:
    def test_includes_rubric_instruction(self):
        prompt = get_check_question_prompt(
            concept_title="Recursion",
            question_type="mcq",
            target_understanding="base case identification",
            lecture_chunks=SAMPLE_CHUNKS,
            mastery=0.3,
        )
        assert "rubric" in prompt
        assert "must_mention" in prompt
        assert "partial_credit_for" in prompt
        assert "common_misconceptions" in prompt
        assert "misconception_detection" in prompt
        assert "Respond ONLY with valid JSON" in prompt

    def test_difficulty_adapts_to_mastery(self):
        # Low mastery → basic difficulty
        low = get_check_question_prompt(
            concept_title="X", question_type="mcq",
            target_understanding="test", lecture_chunks=[], mastery=0.2,
        )
        assert "basic" in low

        # Mid mastery → intermediate
        mid = get_check_question_prompt(
            concept_title="X", question_type="mcq",
            target_understanding="test", lecture_chunks=[], mastery=0.5,
        )
        assert "intermediate" in mid

        # High mastery → advanced
        high = get_check_question_prompt(
            concept_title="X", question_type="mcq",
            target_understanding="test", lecture_chunks=[], mastery=0.8,
        )
        assert "advanced" in high


class TestGradingPrompt:
    def test_format(self):
        prompt = get_grading_prompt(
            question_text="What is recursion?",
            student_answer="A function that calls itself",
            rubric=SAMPLE_RUBRIC,
            lecture_context="Recursion is when a function calls itself.",
        )
        assert "is_correct" in prompt
        assert "misconception_type" in prompt
        assert "near_miss" in prompt
        assert "fundamental" in prompt
        assert "Respond ONLY with valid JSON" in prompt
        assert "base case" in prompt  # rubric content


class TestReteachPrompt:
    def test_near_miss_is_brief(self):
        prompt = get_reteach_prompt(
            concept_title="Recursion",
            original_explanation="Recursion is when a function calls itself.",
            misconception="Student thinks recursion needs a loop",
            misconception_type="near_miss",
            lecture_chunks=SAMPLE_CHUNKS,
        )
        assert "50-100 words" in prompt
        assert "brief" in prompt.lower()
        assert "NEVER repeat" in prompt

    def test_fundamental_is_detailed(self):
        prompt = get_reteach_prompt(
            concept_title="Recursion",
            original_explanation="Recursion is when a function calls itself.",
            misconception="Student has no idea what recursion is",
            misconception_type="fundamental",
            lecture_chunks=SAMPLE_CHUNKS,
        )
        assert "150-250 words" in prompt
        assert "alternative approaches" in prompt or "Analogy" in prompt or "analogy" in prompt.lower()
        assert "NEVER repeat" in prompt


class TestChatRelevancePrompt:
    def test_classification(self):
        prompt = get_chat_relevance_prompt(
            student_message="What is the base case for fibonacci?",
            current_concept="Recursion",
            assessment_topics=["Recursion", "Sorting", "Trees"],
        )
        assert "on_topic" in prompt
        assert "related" in prompt
        assert "off_topic" in prompt
        assert "Recursion" in prompt
        assert "fibonacci" in prompt
        assert "Respond ONLY with valid JSON" in prompt


class TestDiagnosticPrompt:
    def test_generates_mixed_question_types(self):
        prompt = get_diagnostic_questions_prompt(
            concepts=SAMPLE_CONCEPTS,
            assessment_context="Midterm in 5 days",
        )
        assert "mcq" in prompt.lower()
        assert "short_answer" in prompt
        assert "true_false" in prompt or "fill_in_blank" in prompt
        assert "5-8" in prompt
        assert "Respond ONLY with valid JSON" in prompt
        # Concepts are included
        assert "Recursion" in prompt
        assert "Binary Search" in prompt


class TestTeachingBlockPrompt:
    def test_includes_chunks_and_approach(self):
        prompt = get_teaching_block_prompt(
            concept_title="Recursion",
            teaching_approach="foundational",
            mastery=0.2,
            lecture_chunks=SAMPLE_CHUNKS,
            step_description="Introduce the concept of recursion",
        )
        assert "foundational" in prompt
        assert "150-250 words" in prompt
        assert "Lecture 5: Recursion" in prompt
        assert "base case" in prompt  # from chunk content


class TestTutorSystemPrompt:
    def test_full_context(self):
        prompt = get_tutor_system_prompt(
            course_name="Intro to CS",
            course_code="CS101",
            assessment_title="Midterm 1",
            days_until=5,
            weight_percent=20.0,
            assessment_topics=["Recursion", "Sorting"],
            student_name="Alice",
            mastery_summary=[
                {"title": "Recursion", "mastery": 0.3},
                {"title": "Sorting", "mastery": 0.7},
            ],
            mode="guided",
        )
        assert "CS101" in prompt
        assert "Alice" in prompt
        assert "Midterm 1" in prompt
        assert "20.0%" in prompt
        assert "Recursion" in prompt
        assert "weak" in prompt  # mastery 0.3 → weak
        assert "developing" in prompt  # mastery 0.7 → developing

    def test_no_student_name(self):
        prompt = get_tutor_system_prompt(
            course_name="CS101", course_code="CS101",
            assessment_title="Final", days_until=14,
            weight_percent=None, assessment_topics=[],
            student_name=None, mastery_summary=[], mode="guided",
        )
        # Should not crash or include "None"
        assert "None" not in prompt or "unknown" in prompt.lower()

    def test_previous_session_included(self):
        prompt = get_tutor_system_prompt(
            course_name="CS", course_code="CS101",
            assessment_title="Quiz", days_until=3,
            weight_percent=10.0, assessment_topics=["Trees"],
            student_name="Bob", mastery_summary=[], mode="guided",
            previous_session_summary="Covered recursion basics, struggled with base cases.",
        )
        assert "base cases" in prompt
        assert "Build on this" in prompt


# ---------------------------------------------------------------------------
# Test: Planner — priority concepts with fallback
# ---------------------------------------------------------------------------


class TestGetPriorityConcepts:
    @pytest.mark.asyncio
    async def test_with_fallback_to_topics(self):
        """When concept tables don't exist, falls back to assessment topics."""
        from lecturelink_api.services.tutor_planner import get_priority_concepts

        sb = MagicMock()

        # Make concept mastery RPC raise (simulating no concept tables)
        sb.rpc.side_effect = Exception("relation does not exist")

        # Fallback: assessment topics
        sb.table.return_value = _mock_chain(
            [{"topics": ["Recursion", "Binary Search", "Sorting"]}]
        )

        result = await get_priority_concepts(
            sb, FAKE_COURSE_ID, FAKE_USER_ID,
            target_assessment_id=FAKE_ASSESSMENT_ID,
        )

        assert len(result) == 3
        assert result[0]["title"] == "Recursion"
        assert result[0]["mastery"] == 0.5  # default unknown
        assert result[0]["concept_id"] is None

    @pytest.mark.asyncio
    async def test_with_concepts(self):
        """When concept tables exist, uses mastery data."""
        from lecturelink_api.services.tutor_planner import get_priority_concepts

        sb = MagicMock()

        mastery_data = [
            {
                "concept_id": "c1",
                "concept_title": "Recursion",
                "accuracy": 0.4,
                "recent_accuracy": 0.3,
                "total_attempts": 5,
                "difficulty_estimate": 0.6,
            },
            {
                "concept_id": "c2",
                "concept_title": "Sorting",
                "accuracy": 0.8,
                "recent_accuracy": 0.9,
                "total_attempts": 10,
                "difficulty_estimate": 0.4,
            },
        ]

        sb.rpc.return_value = _mock_chain(mastery_data)

        result = await get_priority_concepts(
            sb, FAKE_COURSE_ID, FAKE_USER_ID,
        )

        assert len(result) == 2
        # Recursion has lower mastery → higher priority
        assert result[0]["title"] == "Recursion"
        assert result[0]["mastery"] < result[1]["mastery"]
        assert result[0]["teaching_approach"] == "foundational"
        assert result[1]["teaching_approach"] == "synthesis"

    @pytest.mark.asyncio
    async def test_fallback_to_lectures(self):
        """When no assessment topics, falls back to lecture titles."""
        from lecturelink_api.services.tutor_planner import get_priority_concepts

        sb = MagicMock()
        sb.rpc.side_effect = Exception("no concept tables")

        call_count = 0

        def table_side_effect(table_name):
            nonlocal call_count
            call_count += 1
            if table_name == "assessments":
                # No topics
                return _mock_chain([{"topics": None}])
            if table_name == "lectures":
                return _mock_chain([
                    {"title": "Intro to Algorithms"},
                    {"title": "Data Structures"},
                ])
            return _mock_chain([])

        sb.table.side_effect = table_side_effect

        result = await get_priority_concepts(
            sb, FAKE_COURSE_ID, FAKE_USER_ID,
            target_assessment_id=FAKE_ASSESSMENT_ID,
        )

        assert len(result) == 2
        assert result[0]["title"] == "Intro to Algorithms"


# ---------------------------------------------------------------------------
# Test: Planner — assessment and student context
# ---------------------------------------------------------------------------


class TestGetAssessmentContext:
    @pytest.mark.asyncio
    async def test_context(self):
        from lecturelink_api.services.tutor_planner import get_assessment_context

        sb = MagicMock()
        due_date = (datetime.now(UTC) + timedelta(days=5)).isoformat()

        call_count = 0

        def table_side_effect(table_name):
            nonlocal call_count
            call_count += 1
            if table_name == "assessments":
                return _mock_chain([{
                    "title": "Midterm 1",
                    "due_date": due_date,
                    "weight_percent": 20.0,
                    "topics": ["Recursion", "Sorting"],
                }])
            if table_name == "courses":
                return _mock_chain([{"name": "Intro to CS", "code": "CS101"}])
            return _mock_chain([])

        sb.table.side_effect = table_side_effect

        result = await get_assessment_context(
            sb, FAKE_COURSE_ID, FAKE_ASSESSMENT_ID,
        )

        assert result["assessment_title"] == "Midterm 1"
        assert result["days_until"] == 5 or result["days_until"] == 4  # date boundary
        assert result["weight_percent"] == 20.0
        assert result["course_name"] == "Intro to CS"
        assert result["course_code"] == "CS101"


class TestGetStudentContext:
    @pytest.mark.asyncio
    async def test_context(self):
        from lecturelink_api.services.tutor_planner import get_student_context

        sb = MagicMock()

        call_count = 0

        def table_side_effect(table_name):
            nonlocal call_count
            call_count += 1
            if table_name == "profiles":
                return _mock_chain([{"full_name": "Alice Smith"}])
            if table_name == "tutor_sessions":
                # Table might not exist yet
                raise Exception("relation does not exist")
            return _mock_chain([])

        sb.table.side_effect = table_side_effect

        result = await get_student_context(sb, FAKE_USER_ID)

        assert result["student_name"] == "Alice Smith"
        assert result["previous_session_summary"] is None


# ---------------------------------------------------------------------------
# Test: Additional prompt templates
# ---------------------------------------------------------------------------


class TestPracticePrompt:
    def test_low_mastery_worked_example(self):
        prompt = get_practice_prompt(
            concept_title="Recursion",
            mastery=0.2,
            lecture_chunks=SAMPLE_CHUNKS,
        )
        assert "WORKED EXAMPLE" in prompt

    def test_high_mastery_challenge(self):
        prompt = get_practice_prompt(
            concept_title="Recursion",
            mastery=0.9,
            lecture_chunks=SAMPLE_CHUNKS,
        )
        assert "CHALLENGE" in prompt


class TestSummaryPrompt:
    def test_format(self):
        prompt = get_summary_prompt(
            concept_title="Recursion",
            questions_asked=3,
            questions_correct=2,
            key_misconceptions=["confused base case with recursive step"],
        )
        assert "2/3" in prompt
        assert "confused base case" in prompt


class TestTransitionPrompt:
    def test_format(self):
        prompt = get_transition_prompt(
            completed_concept="Recursion",
            next_concept="Dynamic Programming",
            connection="DP builds on recursive substructure",
        )
        assert "Recursion" in prompt
        assert "Dynamic Programming" in prompt
        assert "recursive substructure" in prompt


class TestSessionSummaryPrompt:
    def test_format(self):
        prompt = get_session_summary_prompt({
            "concepts_covered": ["Recursion", "Binary Search"],
            "questions_asked": 6,
            "questions_correct": 4,
        })
        assert "Recursion" in prompt
        assert "Binary Search" in prompt


class TestDiagnosticAnalysisPrompt:
    def test_format(self):
        prompt = get_diagnostic_analysis_prompt([
            {
                "question": "What is recursion?",
                "student_answer": "A loop",
                "is_correct": False,
            },
        ])
        assert "concept_results" in prompt
        assert "recommended_focus" in prompt
        assert "Respond ONLY with valid JSON" in prompt


class TestChatAnswerPrompt:
    def test_format(self):
        prompt = get_chat_answer_prompt(
            student_message="Can you explain base cases again?",
            current_concept="Recursion",
            lecture_chunks=SAMPLE_CHUNKS,
            assessment_context="Midterm in 5 days",
        )
        assert "base cases" in prompt
        assert "Recursion" in prompt
        assert "Lecture 5" in prompt


# ---------------------------------------------------------------------------
# Test: All prompt functions are importable
# ---------------------------------------------------------------------------


class TestAllPromptFunctionsImportable:
    def test_all_exist(self):
        """Verify every prompt function is importable."""
        from lecturelink_api.services.tutor_prompts import (
            get_chat_answer_prompt,
            get_chat_relevance_prompt,
            get_check_question_prompt,
            get_diagnostic_analysis_prompt,
            get_diagnostic_questions_prompt,
            get_grading_prompt,
            get_lesson_plan_prompt,
            get_practice_prompt,
            get_reteach_prompt,
            get_session_summary_prompt,
            get_summary_prompt,
            get_teaching_block_prompt,
            get_transition_prompt,
            get_tutor_system_prompt,
        )
        # All 14 exist and are callable
        funcs = [
            get_tutor_system_prompt, get_lesson_plan_prompt,
            get_teaching_block_prompt, get_check_question_prompt,
            get_grading_prompt, get_reteach_prompt,
            get_practice_prompt, get_summary_prompt,
            get_transition_prompt, get_chat_relevance_prompt,
            get_chat_answer_prompt, get_diagnostic_questions_prompt,
            get_diagnostic_analysis_prompt, get_session_summary_prompt,
        ]
        assert len(funcs) == 14
        assert all(callable(f) for f in funcs)
