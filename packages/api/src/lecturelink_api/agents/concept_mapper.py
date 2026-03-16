"""Concept Mapper — deterministic-first mapping of lecture concepts to assessments.

Architecture:
  Layer 1: Schedule-based (40%) — lecture week within assessment coverage window
  Layer 2: Keyword overlap (30%) — word overlap between concepts and assessment topics
  Layer 3: Embedding similarity (20%) — cosine similarity of concept vs assessment text
  Layer 4: LLM refinement (10%) — optional Gemini adjustment (additive, never required)

If Layer 4 fails, Layers 1-3 links are preserved unchanged.
"""

from __future__ import annotations

import json
import logging
import re
from datetime import date

import numpy as np
from google.genai import types

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Weights and thresholds
# ---------------------------------------------------------------------------

SCHEDULE_WEIGHT = 0.40
KEYWORD_WEIGHT = 0.30
EMBEDDING_WEIGHT = 0.20
LLM_WEIGHT = 0.10

LINK_THRESHOLD = 0.3  # Minimum final score to persist a link
KEYWORD_MIN_OVERLAP = 1  # At least 1 shared keyword to register a keyword signal


# ---------------------------------------------------------------------------
# Layer 1: Schedule-based mapping
# ---------------------------------------------------------------------------


def _get_syllabus_schedule(supabase, course_id: str) -> list[dict]:
    """Fetch parsed syllabus schedule for the course.

    FIXED: Queries for status="processed" (the actual status after extraction),
    not "confirmed" (which never exists in the DB).
    Falls back to any syllabus if none with needs_review=false.
    """
    # Try reviewed (accepted) syllabus first
    try:
        result = (
            supabase.table("syllabi")
            .select("raw_extraction")
            .eq("course_id", course_id)
            .eq("status", "processed")
            .eq("needs_review", False)
            .limit(1)
            .execute()
        )
        if result.data and result.data[0].get("raw_extraction"):
            extraction = result.data[0]["raw_extraction"]
            return extraction.get("weekly_schedule", [])
    except Exception:
        logger.debug("Failed to fetch reviewed syllabus schedule", exc_info=True)

    # Fallback: any processed syllabus (even if not yet reviewed)
    try:
        result = (
            supabase.table("syllabi")
            .select("raw_extraction")
            .eq("course_id", course_id)
            .eq("status", "processed")
            .limit(1)
            .execute()
        )
        if result.data and result.data[0].get("raw_extraction"):
            extraction = result.data[0]["raw_extraction"]
            return extraction.get("weekly_schedule", [])
    except Exception:
        logger.debug("Failed to fetch any syllabus schedule", exc_info=True)

    return []


def _get_semester_dates(supabase, course_id: str) -> tuple[date | None, date | None]:
    """Fetch semester start/end dates for the course."""
    try:
        result = (
            supabase.table("courses")
            .select("semester_start, semester_end")
            .eq("id", course_id)
            .single()
            .execute()
        )
        if result.data:
            start = result.data.get("semester_start")
            end = result.data.get("semester_end")
            start_date = date.fromisoformat(str(start)) if start else None
            end_date = date.fromisoformat(str(end)) if end else None
            return start_date, end_date
    except Exception:
        logger.debug("Failed to fetch semester dates", exc_info=True)
    return None, None


def _lecture_week_number(
    lecture_date_str: str | None,
    lecture_number: int | None,
    semester_start: date | None,
) -> int | None:
    """Determine which teaching week this lecture falls in.

    Prefers computation from lecture_date + semester_start.
    Falls back to lecture_number if date isn't available.
    """
    if lecture_date_str and semester_start:
        try:
            lec_date = date.fromisoformat(str(lecture_date_str))
            delta = (lec_date - semester_start).days
            if delta >= 0:
                return (delta // 7) + 1
        except (ValueError, TypeError):
            pass

    # Fallback: use lecture_number as a rough proxy for week
    if lecture_number and lecture_number > 0:
        return lecture_number

    return None


def _assessment_week_range(
    assessment: dict,
    schedule: list[dict],
    semester_start: date | None,
) -> tuple[int, int] | None:
    """Determine which weeks an assessment covers.

    Simple heuristic: assessment covers roughly the 5 weeks before its due date
    (or from week 1 if it's early in the semester).
    """
    due_date_str = assessment.get("due_date")
    if not due_date_str or not semester_start:
        return None

    try:
        due_date = date.fromisoformat(str(due_date_str))
        delta = (due_date - semester_start).days
        if delta < 0:
            return None
        assessment_week = (delta // 7) + 1

        start_week = max(1, assessment_week - 5)
        return (start_week, assessment_week)
    except (ValueError, TypeError):
        return None


def compute_schedule_signal(
    lecture_week: int | None,
    assessment: dict,
    schedule: list[dict],
    semester_start: date | None,
) -> float:
    """Compute Layer 1 signal: does this lecture fall within the assessment's coverage window?

    Returns:
        0.0 — lecture week is outside assessment range (or data unavailable)
        0.5 — lecture week is at the edge of the range
        1.0 — lecture week is clearly within range
    """
    if lecture_week is None:
        return 0.0

    week_range = _assessment_week_range(assessment, schedule, semester_start)
    if week_range is None:
        return 0.0

    start_week, end_week = week_range

    if start_week <= lecture_week <= end_week:
        # Within range — higher confidence if well within
        range_size = end_week - start_week + 1
        distance_from_center = abs(lecture_week - (start_week + end_week) / 2)
        center_score = 1.0 - (distance_from_center / max(range_size, 1))
        return max(0.5, center_score)  # at least 0.5 if in range

    # Check if close to the range (within 1 week)
    if lecture_week == start_week - 1 or lecture_week == end_week + 1:
        return 0.25

    return 0.0


# ---------------------------------------------------------------------------
# Layer 2: Keyword/topic overlap
# ---------------------------------------------------------------------------

_STOPWORDS = {
    "the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for",
    "of", "with", "by", "from", "is", "are", "was", "were", "be", "been",
    "have", "has", "had", "do", "does", "did", "will", "would", "could",
    "should", "may", "might", "can", "shall", "not", "no", "all", "each",
    "every", "both", "few", "more", "most", "other", "some", "such", "than",
    "too", "very", "just", "about", "also", "into", "over", "after", "before",
    "between", "through", "during", "above", "below", "up", "down", "out",
    "off", "then", "once", "here", "there", "when", "where", "why", "how",
    "what", "which", "who", "whom", "this", "that", "these", "those",
    "class", "lecture", "week", "chapter", "section", "part", "module",
    "assignment", "exam", "quiz", "test", "midterm", "final", "project",
}


def _tokenize(text: str) -> set[str]:
    """Tokenize text into a set of normalized keywords.

    Removes common stopwords and short words, lowercases everything.
    """
    words = re.findall(r"[a-z0-9]+", text.lower())
    return {w for w in words if len(w) > 2 and w not in _STOPWORDS}


def compute_keyword_signal(concept: dict, assessment: dict) -> float:
    """Compute Layer 2 signal: word overlap between concept and assessment topics.

    Returns:
        0.0 — no meaningful overlap
        0.0-1.0 — normalized overlap score
    """
    concept_text = f"{concept.get('title', '')} {concept.get('description', '')}"
    concept_keywords = _tokenize(concept_text)

    if not concept_keywords:
        return 0.0

    assessment_title = assessment.get("title", "")
    assessment_topics = assessment.get("topics", []) or []
    if isinstance(assessment_topics, str):
        assessment_topics = [assessment_topics]

    assessment_text = f"{assessment_title} {' '.join(str(t) for t in assessment_topics)}"
    assessment_keywords = _tokenize(assessment_text)

    if not assessment_keywords:
        return 0.0

    overlap = concept_keywords & assessment_keywords

    if len(overlap) < KEYWORD_MIN_OVERLAP:
        return 0.0

    # Weighted toward covering assessment keywords
    score = len(overlap) / max(len(assessment_keywords), 1)

    # Bonus for matching assessment TITLE keywords specifically
    title_keywords = _tokenize(assessment_title)
    title_overlap = concept_keywords & title_keywords
    if title_overlap:
        score = min(1.0, score + 0.15 * len(title_overlap))

    return min(1.0, score)


# ---------------------------------------------------------------------------
# Layer 3: Semantic embedding similarity
# ---------------------------------------------------------------------------


async def _get_assessment_embeddings(
    supabase,
    assessments: list[dict],
    course_id: str,
) -> dict[str, list[float]]:
    """Get or compute embeddings for assessment text.

    Embeds: assessment.title + " " + " ".join(assessment.topics)
    """
    from ..services.embedding import embed_texts

    texts = []
    ids = []
    for a in assessments:
        topics = a.get("topics", []) or []
        if isinstance(topics, str):
            topics = [topics]
        text = f"{a.get('title', '')} {' '.join(str(t) for t in topics)}"
        texts.append(text)
        ids.append(a["id"])

    if not texts:
        return {}

    try:
        embeddings = await embed_texts(texts, task_type="RETRIEVAL_DOCUMENT")
        return dict(zip(ids, embeddings))
    except Exception:
        logger.warning("Failed to embed assessment texts", exc_info=True)
        return {}


def compute_embedding_signal(
    concept_embedding: list[float] | None,
    assessment_embedding: list[float] | None,
) -> float:
    """Compute Layer 3 signal: cosine similarity between concept and assessment embeddings.

    Returns:
        0.0 — either embedding is missing
        0.0-1.0 — cosine similarity (clamped to non-negative)
    """
    if concept_embedding is None or assessment_embedding is None:
        return 0.0

    concept_vec = np.array(concept_embedding)
    assessment_vec = np.array(assessment_embedding)

    concept_norm = np.linalg.norm(concept_vec)
    assessment_norm = np.linalg.norm(assessment_vec)

    if concept_norm < 1e-10 or assessment_norm < 1e-10:
        return 0.0

    similarity = float(
        np.dot(concept_vec, assessment_vec) / (concept_norm * assessment_norm)
    )
    return max(0.0, similarity)


# ---------------------------------------------------------------------------
# Layer 4: LLM refinement (optional)
# ---------------------------------------------------------------------------

_LLM_REFINEMENT_PROMPT = """\
You are reviewing concept-to-assessment mappings for a university course.

I have pre-computed relevance scores for each (concept, assessment) pair using \
schedule analysis, keyword matching, and semantic similarity. Your job is to \
ADJUST these scores based on your understanding of how well each concept aligns \
with each assessment.

For each mapping, you can:
- INCREASE the score (if the concept is more relevant than the signals suggest)
- DECREASE the score (if it's a false positive — similar keywords but unrelated)
- KEEP the score (if it looks correct)

Respond with a JSON array. For each entry, include:
- concept_title: exact title from the input
- assessment_id: exact UUID from the input
- adjustment: a float from -0.3 to +0.3 (how much to adjust the pre-computed score)
- reason: one sentence explaining the adjustment

Only include entries where you want to make an adjustment (non-zero). \
If all mappings look correct, return an empty array [].

PRE-COMPUTED MAPPINGS:
{mappings}

COURSE CONTEXT:
Lecture: {lecture_info}
Schedule: {schedule}

Output ONLY the JSON array, no other text."""


async def compute_llm_adjustments(
    candidate_links: list[dict],
    concepts: list[dict],
    assessments: list[dict],
    schedule: list[dict],
    lecture_date: str | None,
    lecture_number: int | None,
) -> dict[tuple[str, str], float]:
    """Layer 4: Ask Gemini to review and adjust pre-computed mappings.

    Returns:
        Dict of (concept_title_lower, assessment_id) -> adjustment float.
        Empty dict if LLM fails (Layers 1-3 preserved unchanged).
    """
    if not candidate_links:
        return {}

    mappings_for_prompt = []
    for link in candidate_links:
        mappings_for_prompt.append({
            "concept_title": link["concept_title"],
            "assessment_title": link["assessment_title"],
            "assessment_id": link["assessment_id"],
            "pre_computed_score": round(link["raw_score"], 3),
            "signals": {
                "schedule": round(link["schedule_signal"], 2),
                "keyword": round(link["keyword_signal"], 2),
                "embedding": round(link["embedding_signal"], 2),
            },
        })

    lecture_info = (
        f"Date: {lecture_date or 'Unknown'}, Number: {lecture_number or 'Unknown'}"
    )

    prompt = _LLM_REFINEMENT_PROMPT.format(
        mappings=json.dumps(mappings_for_prompt, indent=2),
        schedule=json.dumps(schedule[:8], indent=2) if schedule else "No schedule",
        lecture_info=lecture_info,
    )

    try:
        from ..services.genai_client import get_genai_client

        client = get_genai_client()

        response = await client.aio.models.generate_content(
            model="gemini-2.5-flash",
            contents=[types.Content(role="user", parts=[types.Part(text=prompt)])],
            config=types.GenerateContentConfig(
                temperature=0.1,
                max_output_tokens=4096,
            ),
        )

        result_text = response.text.strip()
        if result_text.startswith("```"):
            result_text = result_text.split("```")[1]
            if result_text.startswith("json"):
                result_text = result_text[4:]

        adjustments = json.loads(result_text)

        result: dict[tuple[str, str], float] = {}
        for adj in adjustments:
            title = adj.get("concept_title", "").lower()
            assess_id = adj.get("assessment_id", "")
            adjustment = float(adj.get("adjustment", 0.0))
            # Clamp to [-0.3, +0.3]
            adjustment = max(-0.3, min(0.3, adjustment))
            if title and assess_id and adjustment != 0.0:
                result[(title, assess_id)] = adjustment

        logger.info(
            "LLM refinement: %d adjustments from %d candidates",
            len(result),
            len(candidate_links),
        )
        return result

    except Exception:
        logger.warning(
            "LLM refinement failed — using Layers 1-3 scores unchanged",
            exc_info=True,
        )
        return {}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

# Assessment types that benefit from concept links.
# homework/participation/other don't need them.
_MAPPABLE_TYPES = {"exam", "midterm", "quiz", "test", "final", "project"}


async def map_concepts_to_assessments(
    supabase,
    lecture_id: str,
    course_id: str,
    user_id: str,
    concepts: list[dict],
    lecture_date: str | None = None,
    lecture_number: int | None = None,
) -> list[dict]:
    """Map lecture concepts to assessments using 4-layer scoring.

    Layer 1: Schedule-based (40%) — lecture week within assessment coverage
    Layer 2: Keyword overlap (30%) — word match between concept and assessment topics
    Layer 3: Embedding similarity (20%) — cosine similarity of embeddings
    Layer 4: LLM refinement (10%) — optional Gemini adjustment

    Returns list of persisted concept_assessment_links.
    """
    if not concepts:
        return []

    # --- Fetch all needed data ---

    # Assessments — ALL for the course (not just future)
    assessments_result = (
        supabase.table("assessments")
        .select("id, title, type, due_date, weight_percent, topics, course_id")
        .eq("course_id", course_id)
        .execute()
    )
    assessments = assessments_result.data or []

    if not assessments:
        logger.warning(
            "No assessments for course %s — skipping concept mapping", course_id
        )
        return []

    # Filter to exam-type assessments for mapping
    assessments = [
        a
        for a in assessments
        if (a.get("type") or "").strip().lower() in _MAPPABLE_TYPES
    ]

    if not assessments:
        logger.info(
            "No mappable assessments (exam/quiz/project) for course %s", course_id
        )
        return []

    # Syllabus schedule
    schedule = _get_syllabus_schedule(supabase, course_id)

    # Semester dates
    semester_start, _ = _get_semester_dates(supabase, course_id)

    # Lecture week
    lecture_week = _lecture_week_number(lecture_date, lecture_number, semester_start)

    # Assessment embeddings (Layer 3)
    assessment_embeddings = await _get_assessment_embeddings(
        supabase, assessments, course_id
    )

    # Valid assessment IDs (for validation)
    valid_assessment_ids = {a["id"] for a in assessments}

    # --- Compute signals for every (concept, assessment) pair ---

    candidate_links: list[dict] = []

    for concept in concepts:
        concept_id = concept.get("id")
        if not concept_id:
            continue

        concept_embedding = concept.get("embedding")

        for assessment in assessments:
            assessment_id = assessment["id"]

            # Layer 1
            schedule_signal = compute_schedule_signal(
                lecture_week, assessment, schedule, semester_start
            )

            # Layer 2
            keyword_signal = compute_keyword_signal(concept, assessment)

            # Layer 3
            assessment_emb = assessment_embeddings.get(assessment_id)
            embedding_signal = compute_embedding_signal(
                concept_embedding, assessment_emb
            )

            # Raw score (without LLM)
            raw_score = (
                SCHEDULE_WEIGHT * schedule_signal
                + KEYWORD_WEIGHT * keyword_signal
                + EMBEDDING_WEIGHT * embedding_signal
            )

            # Keep candidates slightly below threshold to allow LLM boost
            if raw_score < LINK_THRESHOLD * 0.7:
                continue

            candidate_links.append({
                "concept_id": concept_id,
                "concept_title": concept.get("title", ""),
                "assessment_id": assessment_id,
                "assessment_title": assessment.get("title", ""),
                "schedule_signal": schedule_signal,
                "keyword_signal": keyword_signal,
                "embedding_signal": embedding_signal,
                "raw_score": raw_score,
            })

    if not candidate_links:
        logger.info("No candidate links above threshold for lecture %s", lecture_id)
        return []

    # --- Layer 4: LLM refinement (optional) ---

    try:
        llm_adjustments = await compute_llm_adjustments(
            candidate_links,
            concepts,
            assessments,
            schedule,
            lecture_date,
            lecture_number,
        )
    except Exception:
        logger.warning(
            "LLM refinement raised — using Layers 1-3 scores unchanged",
            exc_info=True,
        )
        llm_adjustments = {}

    # --- Compute final scores and filter ---

    links_to_persist: list[dict] = []

    for link in candidate_links:
        adj_key = (link["concept_title"].lower(), link["assessment_id"])
        llm_adj = llm_adjustments.get(adj_key, 0.0)

        final_score = link["raw_score"] + LLM_WEIGHT * llm_adj
        final_score = max(0.0, min(1.0, final_score))

        if final_score < LINK_THRESHOLD:
            continue

        # Validate assessment ID exists
        if link["assessment_id"] not in valid_assessment_ids:
            logger.warning(
                "Invalid assessment_id %s — skipping", link["assessment_id"]
            )
            continue

        links_to_persist.append({
            "concept_id": link["concept_id"],
            "assessment_id": link["assessment_id"],
            "user_id": user_id,
            "relevance_score": round(final_score, 4),
            "mapping_confidence": round(final_score, 4),
        })

    # --- Persist to DB ---

    if not links_to_persist:
        logger.info(
            "No links above threshold after scoring for lecture %s", lecture_id
        )
        return []

    try:
        result = (
            supabase.table("concept_assessment_links")
            .upsert(links_to_persist, on_conflict="concept_id,assessment_id")
            .execute()
        )
        logger.info(
            "Concept mapper: created %d links for lecture %s "
            "(%d candidates, %d LLM adjustments)",
            len(result.data),
            lecture_id,
            len(candidate_links),
            len(llm_adjustments),
        )
        return result.data
    except Exception:
        logger.error("Failed to persist concept-assessment links", exc_info=True)
        return []
