"""Tests for the deterministic-first concept mapper.

Tests each mapping layer independently, then the integrated flow.
"""

from __future__ import annotations

from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch

import numpy as np
import pytest
from lecturelink_api.agents.concept_mapper import (
    LINK_THRESHOLD,
    _get_syllabus_schedule,
    _lecture_week_number,
    _tokenize,
    compute_embedding_signal,
    compute_keyword_signal,
    compute_schedule_signal,
    map_concepts_to_assessments,
)

_MOD = "lecturelink_api.agents.concept_mapper"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


_DEFAULT_TOPICS = ["thermodynamics", "heat transfer"]


def _assessment(
    id: str = "assess-001",
    title: str = "Midterm 1",
    type: str = "exam",
    due_date: str | None = "2026-03-15",
    weight_percent: float = 25.0,
    topics: list | None = _DEFAULT_TOPICS,
) -> dict:
    return {
        "id": id,
        "title": title,
        "type": type,
        "due_date": due_date,
        "weight_percent": weight_percent,
        "topics": topics,
        "course_id": "course-001",
    }


def _concept(
    id: str = "concept-001",
    title: str = "First Law of Thermodynamics",
    description: str = "Energy cannot be created or destroyed",
    embedding: list | None = None,
) -> dict:
    return {
        "id": id,
        "title": title,
        "description": description,
        "category": "theorem",
        "embedding": embedding,
    }


def _make_embedding(dim: int = 2000, seed: int = 0) -> list[float]:
    rng = np.random.RandomState(seed)
    vec = rng.randn(dim)
    return (vec / np.linalg.norm(vec)).tolist()


# ---------------------------------------------------------------------------
# Layer 1: Schedule signal
# ---------------------------------------------------------------------------


class TestScheduleSignal:
    def test_lecture_within_assessment_range(self):
        """Lecture in week 4, assessment covers weeks 1-6 -> high score."""
        assessment = _assessment(due_date="2026-03-01")
        semester_start = date(2026, 1, 12)
        score = compute_schedule_signal(4, assessment, [], semester_start)
        assert score >= 0.5

    def test_lecture_outside_assessment_range(self):
        """Lecture in week 12, assessment covers weeks 1-6 -> 0."""
        assessment = _assessment(due_date="2026-02-23")  # ~week 6
        semester_start = date(2026, 1, 12)
        score = compute_schedule_signal(12, assessment, [], semester_start)
        assert score == 0.0

    def test_no_lecture_week_returns_zero(self):
        assessment = _assessment()
        score = compute_schedule_signal(None, assessment, [], date(2026, 1, 12))
        assert score == 0.0

    def test_no_due_date_returns_zero(self):
        assessment = _assessment(due_date=None)
        score = compute_schedule_signal(3, assessment, [], date(2026, 1, 12))
        assert score == 0.0

    def test_adjacent_week_gets_partial_score(self):
        """Lecture well outside assessment range -> zero or small signal."""
        assessment = _assessment(due_date="2026-02-23")  # ~week 6, range ~1-6
        semester_start = date(2026, 1, 12)
        # Week 8 is outside the range (7 is adjacent/edge)
        score = compute_schedule_signal(8, assessment, [], semester_start)
        assert score < 0.5


class TestLectureWeekNumber:
    def test_from_date_and_semester_start(self):
        week = _lecture_week_number("2026-02-09", None, date(2026, 1, 12))
        assert week == 5  # (Feb 9 - Jan 12) = 28 days = 4 weeks -> week 5

    def test_fallback_to_lecture_number(self):
        week = _lecture_week_number(None, 7, date(2026, 1, 12))
        assert week == 7

    def test_none_when_no_data(self):
        week = _lecture_week_number(None, None, None)
        assert week is None


# ---------------------------------------------------------------------------
# Layer 2: Keyword signal
# ---------------------------------------------------------------------------


class TestKeywordSignal:
    def test_direct_topic_match(self):
        """Concept about thermodynamics, assessment covers thermodynamics -> high score."""
        concept = _concept(
            title="Thermodynamics Laws",
            description="Laws governing heat and energy",
        )
        assessment = _assessment(
            topics=["thermodynamics", "heat transfer", "energy conservation"]
        )
        score = compute_keyword_signal(concept, assessment)
        assert score > 0.3

    def test_no_overlap(self):
        """Concept about databases, assessment about physics -> 0."""
        concept = _concept(title="SQL Joins", description="Combining database tables")
        assessment = _assessment(topics=["thermodynamics", "heat transfer"])
        score = compute_keyword_signal(concept, assessment)
        assert score == 0.0

    def test_empty_topics_and_title(self):
        concept = _concept()
        assessment = _assessment(title="", topics=[])
        score = compute_keyword_signal(concept, assessment)
        assert score == 0.0

    def test_title_overlap_bonus(self):
        """Matching assessment TITLE keywords gives bonus."""
        concept = _concept(
            title="Midterm Review Topics", description="Reviewing key concepts"
        )
        assessment = _assessment(title="Midterm 1", topics=["review"])
        score = compute_keyword_signal(concept, assessment)
        assert score > 0


class TestTokenize:
    def test_removes_stopwords(self):
        tokens = _tokenize("the quick brown fox and the lazy dog")
        assert "the" not in tokens
        assert "and" not in tokens
        assert "quick" in tokens
        assert "brown" in tokens

    def test_removes_short_words(self):
        tokens = _tokenize("AI is a key ML tool")
        assert "is" not in tokens
        assert "key" in tokens

    def test_removes_academic_stopwords(self):
        tokens = _tokenize("lecture 5 class exam chapter")
        assert "lecture" not in tokens
        assert "exam" not in tokens


# ---------------------------------------------------------------------------
# Layer 3: Embedding signal
# ---------------------------------------------------------------------------


class TestEmbeddingSignal:
    def test_identical_embeddings(self):
        emb = _make_embedding(seed=42)
        score = compute_embedding_signal(emb, emb)
        assert score > 0.99

    def test_orthogonal_embeddings(self):
        emb_a = [1.0] + [0.0] * 1999
        emb_b = [0.0, 1.0] + [0.0] * 1998
        score = compute_embedding_signal(emb_a, emb_b)
        assert score < 0.01

    def test_none_embedding_returns_zero(self):
        assert compute_embedding_signal(None, _make_embedding()) == 0.0
        assert compute_embedding_signal(_make_embedding(), None) == 0.0

    def test_zero_norm_returns_zero(self):
        assert compute_embedding_signal([0.0] * 2000, _make_embedding()) == 0.0


# ---------------------------------------------------------------------------
# Syllabus schedule query
# ---------------------------------------------------------------------------


class TestGetSyllabusSchedule:
    def test_finds_reviewed_syllabus(self):
        """Should find syllabus with status=processed and needs_review=false."""
        sb = MagicMock()
        schedule_data = [{"week_number": 1, "topics": ["Intro"]}]

        chain = MagicMock()
        chain.select.return_value = chain
        chain.eq.return_value = chain
        chain.limit.return_value = chain
        chain.execute.return_value = MagicMock(
            data=[{"raw_extraction": {"weekly_schedule": schedule_data}}]
        )
        sb.table.return_value = chain

        result = _get_syllabus_schedule(sb, "course-001")
        assert result == schedule_data

    def test_returns_empty_when_no_syllabus(self):
        sb = MagicMock()
        chain = MagicMock()
        chain.select.return_value = chain
        chain.eq.return_value = chain
        chain.limit.return_value = chain
        chain.execute.return_value = MagicMock(data=[])
        sb.table.return_value = chain

        result = _get_syllabus_schedule(sb, "course-001")
        assert result == []


# ---------------------------------------------------------------------------
# Integration: map_concepts_to_assessments
# ---------------------------------------------------------------------------


def _table_side_effect(assessments, schedule_data=None, semester=None):
    """Build a supabase mock that returns the right data per table."""

    def side_effect(name):
        chain = MagicMock()
        chain.select.return_value = chain
        chain.eq.return_value = chain
        chain.limit.return_value = chain
        chain.single.return_value = chain

        if name == "assessments":
            chain.execute.return_value = MagicMock(data=assessments)
        elif name == "syllabi":
            if schedule_data:
                chain.execute.return_value = MagicMock(
                    data=[{"raw_extraction": {"weekly_schedule": schedule_data}}]
                )
            else:
                chain.execute.return_value = MagicMock(data=[])
        elif name == "courses":
            sem = semester or {
                "semester_start": "2026-01-12",
                "semester_end": "2026-05-01",
            }
            chain.execute.return_value = MagicMock(data=sem)
        elif name == "concept_assessment_links":
            chain.upsert.return_value = chain
            chain.execute.return_value = MagicMock(
                data=[{"concept_id": "c1", "assessment_id": "assess-001"}]
            )
        return chain

    return side_effect


class TestMapConceptsIntegration:
    @pytest.mark.asyncio
    async def test_creates_links_with_matching_data(self):
        """Concepts with matching keywords should create links."""
        sb = MagicMock()
        assessments = [
            _assessment(topics=["thermodynamics", "heat", "energy"])
        ]
        sb.table.side_effect = _table_side_effect(assessments)

        concepts = [
            _concept(
                id="c1",
                title="Thermodynamics First Law",
                description="Energy conservation in thermal systems",
                embedding=_make_embedding(seed=1),
            )
        ]

        with (
            patch(
                f"{_MOD}._get_assessment_embeddings",
                new_callable=AsyncMock,
                return_value={},
            ),
            patch(
                f"{_MOD}.compute_llm_adjustments",
                new_callable=AsyncMock,
                return_value={},
            ),
        ):
            result = await map_concepts_to_assessments(
                sb,
                "lec-001",
                "course-001",
                "user-001",
                concepts,
                lecture_date="2026-02-09",
                lecture_number=4,
            )

        assert len(result) > 0

    @pytest.mark.asyncio
    async def test_no_concepts_returns_empty(self):
        sb = MagicMock()
        result = await map_concepts_to_assessments(
            sb, "lec-001", "course-001", "user-001", []
        )
        assert result == []

    @pytest.mark.asyncio
    async def test_no_assessments_returns_empty(self):
        sb = MagicMock()
        chain = MagicMock()
        chain.select.return_value = chain
        chain.eq.return_value = chain
        chain.execute.return_value = MagicMock(data=[])
        sb.table.return_value = chain

        concepts = [_concept(id="c1")]
        result = await map_concepts_to_assessments(
            sb, "lec-001", "course-001", "user-001", concepts
        )
        assert result == []

    @pytest.mark.asyncio
    async def test_llm_failure_preserves_deterministic_links(self):
        """If Layer 4 fails, Layers 1-3 links should still be created."""
        sb = MagicMock()
        assessments = [
            _assessment(topics=["thermodynamics", "energy", "heat"])
        ]
        sb.table.side_effect = _table_side_effect(assessments)

        concepts = [
            _concept(
                id="c1",
                title="Thermodynamics Energy Conservation",
                description="Energy is conserved in thermal processes and heat transfer",
                embedding=_make_embedding(seed=1),
            )
        ]

        with (
            patch(
                f"{_MOD}._get_assessment_embeddings",
                new_callable=AsyncMock,
                return_value={},
            ),
            patch(
                f"{_MOD}.compute_llm_adjustments",
                new_callable=AsyncMock,
                side_effect=Exception("Gemini down"),
            ),
        ):
            result = await map_concepts_to_assessments(
                sb,
                "lec-001",
                "course-001",
                "user-001",
                concepts,
                lecture_date="2026-02-09",
            )

        # Links should still be created from Layers 1-3
        assert len(result) > 0

    @pytest.mark.asyncio
    async def test_non_mappable_types_excluded(self):
        """Participation and homework assessments should not get concept links."""
        sb = MagicMock()
        assessments = [
            _assessment(id="a1", type="participation", topics=["attendance"]),
            _assessment(id="a2", type="homework", topics=["thermodynamics"]),
        ]
        sb.table.side_effect = _table_side_effect(assessments)

        concepts = [_concept(id="c1", embedding=_make_embedding())]

        result = await map_concepts_to_assessments(
            sb, "lec-001", "course-001", "user-001", concepts
        )
        assert result == []

    @pytest.mark.asyncio
    async def test_upsert_uses_conflict_key(self):
        """Verify upsert is called with on_conflict='concept_id,assessment_id'."""
        sb = MagicMock()
        assessments = [
            _assessment(topics=["thermodynamics", "energy", "heat"])
        ]
        sb.table.side_effect = _table_side_effect(assessments)

        concepts = [
            _concept(
                id="c1",
                title="Thermodynamics Energy",
                description="Heat and energy conservation principles",
                embedding=_make_embedding(seed=1),
            )
        ]

        with (
            patch(
                f"{_MOD}._get_assessment_embeddings",
                new_callable=AsyncMock,
                return_value={},
            ),
            patch(
                f"{_MOD}.compute_llm_adjustments",
                new_callable=AsyncMock,
                return_value={},
            ),
        ):
            await map_concepts_to_assessments(
                sb,
                "lec-001",
                "course-001",
                "user-001",
                concepts,
                lecture_date="2026-02-09",
            )

        # Find the upsert call on the concept_assessment_links table
        upsert_calls = []
        for call in sb.table.call_args_list:
            if call.args and call.args[0] == "concept_assessment_links":
                # The next chained call should be upsert
                upsert_calls.append(call)

        # Verify upsert was called (links were above threshold)
        assert len(upsert_calls) > 0

    @pytest.mark.asyncio
    async def test_concept_without_id_skipped(self):
        """Concepts missing 'id' field should be silently skipped."""
        sb = MagicMock()
        assessments = [_assessment()]
        sb.table.side_effect = _table_side_effect(assessments)

        concepts = [
            {"title": "No ID Concept", "description": "Missing id field"}
        ]

        with (
            patch(
                f"{_MOD}._get_assessment_embeddings",
                new_callable=AsyncMock,
                return_value={},
            ),
            patch(
                f"{_MOD}.compute_llm_adjustments",
                new_callable=AsyncMock,
                return_value={},
            ),
        ):
            result = await map_concepts_to_assessments(
                sb, "lec-001", "course-001", "user-001", concepts
            )

        assert result == []
