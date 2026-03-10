"""Lesson planner — decides WHAT to teach and in what order.

Orchestrates concept prioritization, context gathering, and plan generation
for the Study Tutor.
"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import UTC, datetime

from lecturelink_api.models.tutor_models import (
    AssessmentReadinessResponse,
    ConceptReadiness,
)

from . import tutor_prompts
from .genai_client import get_genai_client as _get_client
from .mastery import compute_mastery
from .search import search_lectures

logger = logging.getLogger(__name__)

TUTOR_MODEL = "gemini-2.5-flash"


def _parse_json_response(text: str) -> dict | list:
    """Parse JSON from LLM response, stripping markdown fences if present."""
    cleaned = text.strip()
    if cleaned.startswith("```"):
        # Remove ```json ... ``` fences
        lines = cleaned.split("\n")
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        cleaned = "\n".join(lines)
    return json.loads(cleaned)


# ---------------------------------------------------------------------------
# 1. Priority concepts
# ---------------------------------------------------------------------------


async def get_priority_concepts(
    supabase,
    course_id: str,
    user_id: str,
    target_assessment_id: str | None = None,
    limit: int = 5,
) -> list[dict]:
    """Get priority concepts for a tutoring session.

    Tries concept tables first, falls back to syllabus topics if unavailable.

    Returns:
        [{concept_id, title, mastery, priority_score, teaching_approach}]
    """
    # Try concept tables first
    try:
        concepts = await _get_concepts_from_tables(
            supabase,
            course_id,
            user_id,
            target_assessment_id,
            limit,
        )
        if concepts:
            return concepts
    except Exception:
        logger.warning(
            "Tutor falling back to syllabus topics "
            "— concept extraction not available for course %s",
            course_id,
        )

    # Fallback: use assessment topics or lecture titles
    return await _get_fallback_concepts(
        supabase,
        course_id,
        target_assessment_id,
        limit,
    )


async def _get_concepts_from_tables(
    supabase,
    course_id: str,
    user_id: str,
    target_assessment_id: str | None,
    limit: int,
) -> list[dict]:
    """Fetch concepts from concept tables with mastery data."""
    # Get concept mastery for this course
    mastery_result = supabase.rpc(
        "get_concept_mastery",
        {"p_course_id": course_id, "p_user_id": user_id},
    ).execute()

    if not mastery_result.data:
        return []

    mastery_map: dict[str, dict] = {}
    for m in mastery_result.data:
        accuracy = m.get("accuracy", 0.0)
        recent = m.get("recent_accuracy", 0.0)
        attempts = m.get("total_attempts", 0)
        mastery = compute_mastery(accuracy, recent, attempts)
        mastery_map[m["concept_id"]] = {
            "concept_id": m["concept_id"],
            "title": m["concept_title"],
            "mastery": mastery,
            "total_attempts": attempts,
            "difficulty": m.get("difficulty_estimate", 0.5),
        }

    # If targeting a specific assessment, prioritize linked concepts
    if target_assessment_id:
        try:
            links = (
                supabase.table("concept_assessment_links")
                .select("concept_id, relevance_score")
                .eq("assessment_id", target_assessment_id)
                .order("relevance_score", desc=True)
                .execute()
            )
            if links.data:
                result = []
                for link in links.data:
                    cid = link["concept_id"]
                    entry = mastery_map.get(cid)
                    if entry:
                        priority = _compute_priority(
                            entry["mastery"],
                            entry["difficulty"],
                            link.get("relevance_score", 0.5),
                        )
                        result.append(
                            {
                                **entry,
                                "priority_score": priority,
                                "teaching_approach": _teaching_approach(entry["mastery"]),
                            }
                        )
                result.sort(key=lambda x: x["priority_score"], reverse=True)
                return result[:limit]
        except Exception:
            logger.debug("concept_assessment_links query failed", exc_info=True)

    # No assessment target — prioritize by mastery gap
    result = []
    for entry in mastery_map.values():
        priority = _compute_priority(entry["mastery"], entry["difficulty"])
        result.append(
            {
                **entry,
                "priority_score": priority,
                "teaching_approach": _teaching_approach(entry["mastery"]),
            }
        )
    result.sort(key=lambda x: x["priority_score"], reverse=True)
    return result[:limit]


async def _get_fallback_concepts(
    supabase,
    course_id: str,
    target_assessment_id: str | None,
    limit: int,
) -> list[dict]:
    """Fallback: use assessment topics or lecture titles as pseudo-concepts."""
    # Try assessment topics first
    if target_assessment_id:
        try:
            assessment = (
                supabase.table("assessments")
                .select("topics")
                .eq("id", target_assessment_id)
                .maybe_single()
                .execute()
            )
            if assessment.data and assessment.data.get("topics"):
                topics = assessment.data["topics"]
                return [
                    {
                        "concept_id": None,
                        "title": topic,
                        "mastery": 0.5,
                        "priority_score": 1.0 - (i * 0.1),
                        "teaching_approach": "application",
                    }
                    for i, topic in enumerate(topics[:limit])
                ]
        except Exception:
            logger.debug("Failed to fetch assessment topics", exc_info=True)

    # Try lecture titles
    try:
        lectures = (
            supabase.table("lectures")
            .select("title")
            .eq("course_id", course_id)
            .eq("processing_status", "completed")
            .order("lecture_number")
            .execute()
        )
        if lectures.data:
            return [
                {
                    "concept_id": None,
                    "title": lec["title"],
                    "mastery": 0.5,
                    "priority_score": 0.5,
                    "teaching_approach": "application",
                }
                for lec in lectures.data[:limit]
            ]
    except Exception:
        logger.debug("Failed to fetch lecture titles", exc_info=True)

    return []


def _compute_priority(
    mastery: float,
    difficulty: float,
    relevance: float = 0.5,
) -> float:
    """Compute priority score for a concept.

    Higher priority = lower mastery, higher difficulty, higher relevance.
    """
    mastery_gap = 1.0 - mastery
    return round(mastery_gap * 0.4 + difficulty * 0.2 + relevance * 0.4, 4)


def _teaching_approach(mastery: float) -> str:
    """Choose teaching approach based on mastery level."""
    if mastery < 0.4:
        return "foundational"
    if mastery <= 0.7:
        return "application"
    return "synthesis"


def _consolidate_by_topics(
    fine_concepts: list[dict],
    topics: list[str],
    covered_titles: set[str],
) -> list["ConceptReadiness"]:
    """Consolidate fine-grained concepts into broader assessment topics.

    Uses word-overlap scoring to bucket each concept under the best-matching
    topic.  Concepts that don't match any topic are grouped under a catch-all.
    Each topic becomes one ConceptReadiness entry with averaged mastery.
    """
    from lecturelink_api.models.tutor_models import ConceptReadiness

    # Build normalised word sets for each topic
    def _words(text: str) -> set[str]:
        return {w.lower().strip(".,;:()") for w in text.split() if len(w) > 2}

    topic_words = [(t, _words(t)) for t in topics]

    # Bucket each concept under the best-matching topic
    buckets: dict[str, list[dict]] = {t: [] for t in topics}
    unmatched: list[dict] = []

    for entry in fine_concepts:
        concept_words = _words(entry["title"]) | _words(
            entry.get("description", ""),
        )
        best_topic: str | None = None
        best_score = 0
        for topic_name, tw in topic_words:
            if not tw:
                continue
            overlap = len(concept_words & tw)
            # Normalise by topic word count so short topics can still match
            score = overlap / len(tw)
            if score > best_score:
                best_score = score
                best_topic = topic_name
        if best_topic and best_score > 0:
            buckets[best_topic].append(entry)
        else:
            unmatched.append(entry)

    # Distribute unmatched concepts evenly among topics that have the fewest
    # members, so nothing is silently dropped.
    if unmatched:
        for entry in unmatched:
            smallest = min(buckets, key=lambda t: len(buckets[t]))
            buckets[smallest].append(entry)

    results: list[ConceptReadiness] = []
    for topic_name, entries in buckets.items():
        if not entries:
            # Topic with no matching concepts — show at 0% mastery
            results.append(ConceptReadiness(
                concept_id=None,
                title=topic_name,
                mastery=0.0,
                total_attempts=0,
                covered=False,
                teaching_approach="foundational",
            ))
            continue
        avg_mastery = sum(e["mastery"] for e in entries) / len(entries)
        total_attempts = sum(e.get("total_attempts", 0) for e in entries)
        any_covered = any(e["title"] in covered_titles for e in entries)
        results.append(ConceptReadiness(
            concept_id=None,
            title=topic_name,
            mastery=round(avg_mastery, 4),
            total_attempts=total_attempts,
            covered=any_covered,
            teaching_approach=_teaching_approach(avg_mastery),
        ))

    return results


# ---------------------------------------------------------------------------
# 2. Assessment context
# ---------------------------------------------------------------------------


async def get_assessment_context(
    supabase,
    course_id: str,
    target_assessment_id: str,
) -> dict:
    """Fetch assessment and course info for session context.

    Returns:
        {assessment_title, days_until, weight_percent, topics,
         course_name, course_code}
    """
    # Fetch assessment
    assessment = (
        supabase.table("assessments")
        .select("title, due_date, weight_percent, topics")
        .eq("id", target_assessment_id)
        .maybe_single()
        .execute()
    )

    a_data = assessment.data or {}
    title = a_data.get("title", "Upcoming Assessment")
    topics = a_data.get("topics") or []
    weight = a_data.get("weight_percent")

    # Calculate days until due
    due_date_str = a_data.get("due_date")
    if due_date_str:
        try:
            due_dt = datetime.fromisoformat(str(due_date_str))
            if due_dt.tzinfo is None:
                due_dt = due_dt.replace(tzinfo=UTC)
            days_until = max(0, (due_dt - datetime.now(UTC)).days)
        except (ValueError, TypeError):
            days_until = 14
    else:
        days_until = 14

    # Fetch course
    course = (
        supabase.table("courses").select("name, code").eq("id", course_id).maybe_single().execute()
    )
    c_data = course.data or {}

    return {
        "assessment_title": title,
        "days_until": days_until,
        "weight_percent": weight,
        "topics": topics,
        "course_name": c_data.get("name", ""),
        "course_code": c_data.get("code", ""),
    }


# ---------------------------------------------------------------------------
# 3. Student context
# ---------------------------------------------------------------------------


async def get_student_context(
    supabase,
    user_id: str,
) -> dict:
    """Fetch student profile and previous session context.

    Returns:
        {student_name, previous_session_summary}
    """
    # Fetch student name from profiles
    student_name = None
    try:
        profile = (
            supabase.table("profiles")
            .select("full_name")
            .eq("id", user_id)
            .maybe_single()
            .execute()
        )
        if profile.data:
            student_name = profile.data.get("full_name")
    except Exception:
        logger.debug("Failed to fetch student profile", exc_info=True)

    # Fetch previous tutor session summary (if session table exists)
    previous_summary = None
    try:
        sessions = (
            supabase.table("tutor_sessions")
            .select("summary")
            .eq("user_id", user_id)
            .order("created_at", desc=True)
            .execute()
        )
        if sessions.data and sessions.data[0].get("summary"):
            previous_summary = sessions.data[0]["summary"]
    except Exception:
        logger.debug("tutor_sessions table not available", exc_info=True)

    return {
        "student_name": student_name,
        "previous_session_summary": previous_summary,
    }


# ---------------------------------------------------------------------------
# 4. Lecture context
# ---------------------------------------------------------------------------


async def get_lecture_context(
    supabase,
    course_id: str,
    concept_title: str,
) -> list[dict]:
    """Retrieve lecture chunks relevant to a concept via RAG search.

    Returns:
        [{content, lecture_title, start_time}] — top 5-8 chunks
    """
    try:
        chunks = await search_lectures(
            supabase=supabase,
            course_id=course_id,
            query=concept_title,
            limit=6,
        )
        return [
            {
                "content": c["content"],
                "lecture_title": c["lecture_title"],
                "start_time": c.get("start_time"),
            }
            for c in chunks
        ]
    except Exception:
        logger.warning(
            "Lecture search failed for concept %r in course %s",
            concept_title,
            course_id,
            exc_info=True,
        )
        return []


# ---------------------------------------------------------------------------
# 5. Lesson plan generation
# ---------------------------------------------------------------------------


async def generate_lesson_plan(
    supabase,
    course_id: str,
    user_id: str,
    mode: str,
    target_assessment_id: str | None = None,
    custom_topic: str | None = None,
    concept_ids: list[str] | None = None,
) -> dict:
    """Orchestrate lesson plan creation.

    Steps:
      1. Get priority concepts (or use custom_topic)
      2. Get assessment context
      3. Get student context
      4. Generate plan via Gemini
      5. Pre-generate first concept content

    Returns:
        Lesson plan dict matching the JSON schema from get_lesson_plan_prompt.
    """
    # If diagnostic mode, use specialized flow
    if mode == "diagnostic":
        return await generate_diagnostic(
            supabase,
            course_id,
            user_id,
            target_assessment_id,
        )

    # 1. Priority concepts
    if custom_topic:
        concepts = [
            {
                "concept_id": None,
                "title": custom_topic,
                "mastery": 0.5,
                "priority_score": 1.0,
                "teaching_approach": "application",
            },
        ]
    else:
        concepts = await get_priority_concepts(
            supabase,
            course_id,
            user_id,
            target_assessment_id,
            limit=len(concept_ids) if concept_ids else 5,
        )
        if concept_ids:
            id_set = set(concept_ids)
            # Match by concept_id first, fall back to title match
            concepts = [
                c for c in concepts
                if c["concept_id"] in id_set or c["title"] in id_set
            ]
        if not concepts:
            # Last resort: use assessment topics as pseudo-concepts
            if target_assessment_id:
                try:
                    a_result = (
                        supabase.table("assessments")
                        .select("topics")
                        .eq("id", target_assessment_id)
                        .maybe_single()
                        .execute()
                    )
                    topics = (a_result.data or {}).get("topics") or []
                    if topics:
                        concepts = [
                            {
                                "concept_id": None,
                                "title": t,
                                "mastery": 0.0,
                                "priority_score": 1.0 - (i * 0.1),
                                "teaching_approach": "foundational",
                            }
                            for i, t in enumerate(topics[:5])
                        ]
                except Exception:
                    logger.debug("Assessment topics fallback failed", exc_info=True)

            if not concepts:
                return {
                    "session_title": "Study Session",
                    "estimated_duration_minutes": 30,
                    "concepts": [],
                    "wrap_up": {
                        "type": "summary",
                        "description": "No concepts available for this session.",
                    },
                    "error": "No concepts found to plan a session around.",
                }

    # 2. Assessment context
    if target_assessment_id:
        assessment_ctx = await get_assessment_context(
            supabase,
            course_id,
            target_assessment_id,
        )
        weight = assessment_ctx["weight_percent"]
        weight_note = f", worth {weight}%" if weight else ""
        topics = assessment_ctx["topics"]
        topics_note = ", ".join(topics) if topics else "general"
        assessment_context_str = (
            f"Assessment: {assessment_ctx['assessment_title']} "
            f"({assessment_ctx['days_until']} days away{weight_note}). "
            f"Topics: {topics_note}."
        )
    else:
        assessment_ctx = {}
        assessment_context_str = "No specific assessment target."

    # 3. Student context
    student_ctx = await get_student_context(supabase, user_id)

    # 4. Build prompt and call Gemini
    prompt = tutor_prompts.get_lesson_plan_prompt(
        concepts=concepts,
        assessment_context=assessment_context_str,
        mode=mode,
        custom_topic=custom_topic,
    )

    try:
        response = await _get_client().aio.models.generate_content(
            model=TUTOR_MODEL,
            contents=prompt,
            config={
                "temperature": 0.4,
                "response_mime_type": "application/json",
            },
        )
        logger.info(
            "Gemini lesson plan call: %d input tokens, %d output tokens",
            response.usage_metadata.prompt_token_count,
            response.usage_metadata.candidates_token_count,
        )
        plan = _parse_json_response(response.text)
    except json.JSONDecodeError:
        logger.error("Failed to parse lesson plan JSON from Gemini")
        # Return a minimal valid plan
        plan = {
            "session_title": f"Study Session: {concepts[0]['title']}",
            "estimated_duration_minutes": 30,
            "concepts": [
                {
                    "concept_id": c.get("concept_id"),
                    "title": c["title"],
                    "mastery": c["mastery"],
                    "total_attempts": c.get("total_attempts", 0),
                    "priority_score": c["priority_score"],
                    "teaching_approach": c["teaching_approach"],
                    "estimated_minutes": 8,
                    "outline": [
                        {"type": "explain", "description": f"Explain {c['title']}"},
                        {
                            "type": "check",
                            "description": f"Check understanding of {c['title']}",
                            "question_type": "short_answer",
                            "targets": c["title"],
                        },
                    ],
                }
                for c in concepts[:3]
            ],
            "wrap_up": {"type": "summary", "description": "Session wrap-up"},
        }
    except Exception:
        logger.error("Gemini lesson plan generation failed", exc_info=True)
        raise

    # 4b. Merge total_attempts from input concepts (Gemini doesn't return it)
    attempts_map = {c.get("concept_id"): c.get("total_attempts", 0) for c in concepts}
    for pc in plan.get("concepts", []):
        cid = pc.get("concept_id")
        if "total_attempts" not in pc and cid in attempts_map:
            pc["total_attempts"] = attempts_map[cid]
        elif "total_attempts" not in pc:
            pc["total_attempts"] = 0

    # 5. Pre-generate first concept's content
    if plan.get("concepts"):
        first_concept = plan["concepts"][0]
        try:
            first_content = await generate_concept_content(
                supabase,
                course_id,
                first_concept,
                assessment_context_str,
            )
            plan["concepts"][0]["generated_content"] = first_content
        except Exception:
            logger.warning("Failed to pre-generate first concept content", exc_info=True)

    # Attach context for downstream use
    plan["_assessment_context"] = assessment_ctx
    plan["_student_context"] = student_ctx

    return plan


# ---------------------------------------------------------------------------
# 6. Concept content generation
# ---------------------------------------------------------------------------


async def generate_concept_content(
    supabase,
    course_id: str,
    concept: dict,
    assessment_context: str,
) -> dict:
    """Generate content for a single concept in the lesson plan.

    For each step in the outline, generates appropriate content via Gemini.

    Returns:
        {concept_title, blocks: [{block_type, content, question?, rubric?}]}
    """
    title = concept["title"]
    mastery = concept.get("mastery", 0.5)
    approach = concept.get("teaching_approach", "application")
    outline = concept.get("outline", [])

    # Get lecture chunks for this concept
    chunks = await get_lecture_context(supabase, course_id, title)

    blocks: list[dict] = []
    for step in outline:
        step_type = step.get("type", "explain")
        description = step.get("description", "")

        if step_type in ("activate", "explain"):
            block = await _generate_teaching_block(
                title,
                approach,
                mastery,
                chunks,
                description,
            )
            blocks.append({"block_type": step_type, "content": block})

        elif step_type == "check":
            q_type = step.get("question_type", "short_answer")
            targets = step.get("targets", title)
            block = await _generate_check_question(
                title,
                q_type,
                targets,
                chunks,
                mastery,
            )
            blocks.append(block)

        elif step_type == "practice":
            block = await _generate_practice(title, mastery, chunks)
            blocks.append({"block_type": "practice", "content": block})

        elif step_type == "summary":
            # Summary is generated later with actual performance data
            blocks.append(
                {
                    "block_type": "summary",
                    "content": None,
                    "pending": True,
                }
            )

        elif step_type == "transition":
            # Transition is generated with the next concept title
            blocks.append(
                {
                    "block_type": "transition",
                    "content": None,
                    "description": description,
                    "pending": True,
                }
            )

        else:
            blocks.append({"block_type": step_type, "content": description})

    return {"concept_title": title, "blocks": blocks}


async def _generate_teaching_block(
    concept_title: str,
    approach: str,
    mastery: float,
    chunks: list[dict],
    description: str,
) -> str:
    """Generate a teaching explanation block via Gemini."""
    prompt = tutor_prompts.get_teaching_block_prompt(
        concept_title=concept_title,
        teaching_approach=approach,
        mastery=mastery,
        lecture_chunks=chunks,
        step_description=description,
    )

    try:
        response = await _get_client().aio.models.generate_content(
            model=TUTOR_MODEL,
            contents=prompt,
            config={"temperature": 0.4},
        )
        logger.info(
            "Gemini teaching block: %d input, %d output tokens",
            response.usage_metadata.prompt_token_count,
            response.usage_metadata.candidates_token_count,
        )
        return response.text
    except Exception:
        logger.error("Teaching block generation failed", exc_info=True)
        return f"Let's discuss **{concept_title}**. {description}"


async def _generate_check_question(
    concept_title: str,
    question_type: str,
    targets: str,
    chunks: list[dict],
    mastery: float,
) -> dict:
    """Generate a comprehension question with rubric via Gemini."""
    prompt = tutor_prompts.get_check_question_prompt(
        concept_title=concept_title,
        question_type=question_type,
        target_understanding=targets,
        lecture_chunks=chunks,
        mastery=mastery,
    )

    try:
        response = await _get_client().aio.models.generate_content(
            model=TUTOR_MODEL,
            contents=prompt,
            config={
                "temperature": 0.3,
                "response_mime_type": "application/json",
            },
        )
        logger.info(
            "Gemini check question: %d input, %d output tokens",
            response.usage_metadata.prompt_token_count,
            response.usage_metadata.candidates_token_count,
        )
        data = _parse_json_response(response.text)
        data["question_id"] = str(uuid.uuid4())
        data["concept_title"] = concept_title
        return {
            "block_type": "check",
            "content": data.get("question_text", ""),
            "question": data,
            "rubric": data.get("rubric", {}),
        }
    except Exception:
        logger.error("Check question generation failed", exc_info=True)
        return {
            "block_type": "check",
            "content": f"Can you explain the key idea behind {concept_title}?",
            "question": {
                "question_id": str(uuid.uuid4()),
                "concept_title": concept_title,
                "question_text": f"Can you explain the key idea behind {concept_title}?",
                "question_type": "short_answer",
                "correct_answer": concept_title,
            },
            "rubric": {"must_mention": [concept_title], "model_answer": concept_title},
        }


async def _generate_practice(
    concept_title: str,
    mastery: float,
    chunks: list[dict],
) -> str:
    """Generate a practice problem via Gemini."""
    prompt = tutor_prompts.get_practice_prompt(
        concept_title=concept_title,
        mastery=mastery,
        lecture_chunks=chunks,
    )

    try:
        response = await _get_client().aio.models.generate_content(
            model=TUTOR_MODEL,
            contents=prompt,
            config={"temperature": 0.4},
        )
        logger.info(
            "Gemini practice: %d input, %d output tokens",
            response.usage_metadata.prompt_token_count,
            response.usage_metadata.candidates_token_count,
        )
        return response.text
    except Exception:
        logger.error("Practice generation failed", exc_info=True)
        return f"Try applying the concept of **{concept_title}** to a simple example."


# ---------------------------------------------------------------------------
# 7. Diagnostic generation
# ---------------------------------------------------------------------------


async def generate_diagnostic(
    supabase,
    course_id: str,
    user_id: str,
    target_assessment_id: str,
) -> dict:
    """Generate a diagnostic assessment for a student.

    Returns:
        {questions: [{question_id, question_text, question_type,
                      concept_title, ...rubric data}]}
    """
    concepts = await get_priority_concepts(
        supabase,
        course_id,
        user_id,
        target_assessment_id,
        limit=6,
    )
    assessment_ctx = await get_assessment_context(
        supabase,
        course_id,
        target_assessment_id,
    )

    diag_topics = assessment_ctx["topics"]
    diag_topics_str = ", ".join(diag_topics) if diag_topics else "general"
    assessment_context_str = (
        f"Assessment: {assessment_ctx['assessment_title']} "
        f"({assessment_ctx['days_until']} days away). "
        f"Topics: {diag_topics_str}."
    )

    prompt = tutor_prompts.get_diagnostic_questions_prompt(
        concepts=concepts,
        assessment_context=assessment_context_str,
    )

    try:
        response = await _get_client().aio.models.generate_content(
            model=TUTOR_MODEL,
            contents=prompt,
            config={
                "temperature": 0.3,
                "response_mime_type": "application/json",
            },
        )
        logger.info(
            "Gemini diagnostic: %d input, %d output tokens",
            response.usage_metadata.prompt_token_count,
            response.usage_metadata.candidates_token_count,
        )
        questions = _parse_json_response(response.text)

        # Add unique IDs to each question
        for q in questions:
            q["question_id"] = str(uuid.uuid4())

        return {"questions": questions}

    except json.JSONDecodeError:
        logger.error("Failed to parse diagnostic JSON")
        return {"questions": [], "error": "Failed to generate diagnostic questions"}
    except Exception:
        logger.error("Diagnostic generation failed", exc_info=True)
        raise


# ---------------------------------------------------------------------------
# 8. Diagnostic analysis
# ---------------------------------------------------------------------------


async def analyze_diagnostic(
    questions_and_results: list[dict],
) -> dict:
    """Analyze diagnostic results and identify gaps.

    Args:
        questions_and_results: [{question, student_answer, is_correct, ...}]

    Returns:
        {concept_results, identified_gaps, recommended_focus, overall_readiness,
         summary}
    """
    prompt = tutor_prompts.get_diagnostic_analysis_prompt(questions_and_results)

    try:
        response = await _get_client().aio.models.generate_content(
            model=TUTOR_MODEL,
            contents=prompt,
            config={
                "temperature": 0.1,
                "response_mime_type": "application/json",
            },
        )
        logger.info(
            "Gemini diagnostic analysis: %d input, %d output tokens",
            response.usage_metadata.prompt_token_count,
            response.usage_metadata.candidates_token_count,
        )
        return _parse_json_response(response.text)
    except json.JSONDecodeError:
        logger.error("Failed to parse diagnostic analysis JSON")
        # Return basic analysis from the raw results
        correct = sum(1 for r in questions_and_results if r.get("is_correct"))
        total = len(questions_and_results)
        return {
            "concept_results": [],
            "identified_gaps": [],
            "recommended_focus": [],
            "overall_readiness": "medium",
            "summary": f"Student answered {correct}/{total} questions correctly.",
        }
    except Exception:
        logger.error("Diagnostic analysis failed", exc_info=True)
        raise


# ---------------------------------------------------------------------------
# 9. Assessment readiness
# ---------------------------------------------------------------------------


async def get_assessment_readiness(
    supabase,
    course_id: str,
    user_id: str,
    assessment_id: str,
) -> AssessmentReadinessResponse:
    """Compute readiness for a specific assessment.

    Combines concept-assessment links, mastery data, and session coverage
    to produce a readiness report.
    """
    # 1. Fetch assessment metadata
    assessment_ctx = await get_assessment_context(
        supabase, course_id, assessment_id,
    )

    # 2. Get linked concepts
    try:
        links = (
            supabase.table("concept_assessment_links")
            .select("concept_id")
            .eq("assessment_id", assessment_id)
            .execute()
        )
        linked_concept_ids = [
            link["concept_id"] for link in (links.data or [])
        ]
    except Exception:
        logger.debug(
            "concept_assessment_links query failed", exc_info=True,
        )
        linked_concept_ids = []

    # 3. Get mastery data (per fine-grained concept)
    mastery_map: dict[str, dict] = {}
    try:
        mastery_result = supabase.rpc(
            "get_concept_mastery",
            {"p_course_id": course_id, "p_user_id": user_id},
        ).execute()
        for m in mastery_result.data or []:
            accuracy = m.get("accuracy", 0.0)
            recent = m.get("recent_accuracy", 0.0)
            attempts = m.get("total_attempts", 0)
            mastery = compute_mastery(accuracy, recent, attempts)
            mastery_map[m["concept_id"]] = {
                "concept_id": m["concept_id"],
                "title": m["concept_title"],
                "mastery": mastery,
                "total_attempts": attempts,
                "lecture_id": m.get("lecture_id"),
            }
    except Exception:
        logger.debug("get_concept_mastery RPC failed", exc_info=True)

    # 4. Get covered concepts from session events
    covered_titles: set[str] = set()
    try:
        events = (
            supabase.table("tutor_session_events")
            .select("concept_title")
            .eq("user_id", user_id)
            .eq("event_type", "question_answer")
            .execute()
        )
        for ev in events.data or []:
            ct = ev.get("concept_title")
            if ct:
                covered_titles.add(ct)
    except Exception:
        logger.debug("tutor_session_events query failed", exc_info=True)

    # 5. Collect matching fine-grained concepts
    fine_concepts: list[dict] = []
    if linked_concept_ids and mastery_map:
        linked_set = set(linked_concept_ids)
        for cid, entry in mastery_map.items():
            if cid in linked_set:
                fine_concepts.append(entry)
    elif mastery_map:
        # No linked concepts — use all mastery data for course
        fine_concepts = list(mastery_map.values())

    # 6. Consolidate fine-grained concepts into broader topics.
    #    Use assessment topics from syllabus as category buckets when
    #    available; otherwise group by lecture.
    concepts: list[ConceptReadiness] = []
    assessment_topics: list[str] = assessment_ctx.get("topics") or []

    if fine_concepts and assessment_topics:
        # Bucket fine-grained concepts under assessment topics via word overlap
        concepts = _consolidate_by_topics(
            fine_concepts, assessment_topics, covered_titles,
        )
    elif fine_concepts:
        # No assessment topics — group by lecture
        lecture_ids = list({
            e["lecture_id"] for e in fine_concepts if e.get("lecture_id")
        })
        lecture_title_map: dict[str, str] = {}
        if lecture_ids:
            try:
                lect_result = (
                    supabase.table("lectures")
                    .select("id, title")
                    .in_("id", lecture_ids)
                    .execute()
                )
                for lect in lect_result.data or []:
                    lecture_title_map[lect["id"]] = lect["title"]
            except Exception:
                logger.debug("lectures title lookup failed", exc_info=True)

        from collections import defaultdict
        by_lecture: dict[str, list[dict]] = defaultdict(list)
        ungrouped: list[dict] = []
        for entry in fine_concepts:
            lid = entry.get("lecture_id")
            if lid:
                by_lecture[lid].append(entry)
            else:
                ungrouped.append(entry)

        for lid, entries in by_lecture.items():
            avg_mastery = sum(e["mastery"] for e in entries) / len(entries)
            total_attempts = sum(e.get("total_attempts", 0) for e in entries)
            any_covered = any(e["title"] in covered_titles for e in entries)
            title = lecture_title_map.get(lid, entries[0]["title"])
            concepts.append(ConceptReadiness(
                concept_id=lid,
                title=title,
                mastery=round(avg_mastery, 4),
                total_attempts=total_attempts,
                covered=any_covered,
                teaching_approach=_teaching_approach(avg_mastery),
            ))
        for entry in ungrouped:
            concepts.append(ConceptReadiness(
                concept_id=entry["concept_id"],
                title=entry["title"],
                mastery=entry["mastery"],
                total_attempts=entry.get("total_attempts", 0),
                covered=entry["title"] in covered_titles,
                teaching_approach=_teaching_approach(entry["mastery"]),
            ))

    # If still empty, use assessment topics as fallback
    if not concepts:
        for topic in assessment_topics:
            concepts.append(ConceptReadiness(
                concept_id=None,
                title=topic,
                mastery=0.0,
                total_attempts=0,
                covered=topic in covered_titles,
                teaching_approach="foundational",
            ))

    total = len(concepts)
    ready_count = sum(1 for c in concepts if c.mastery >= 0.7)
    overall = (
        sum(c.mastery for c in concepts) / total if total > 0 else 0.0
    )

    return AssessmentReadinessResponse(
        assessment_id=assessment_id,
        assessment_title=assessment_ctx.get("assessment_title", "Assessment"),
        due_date=assessment_ctx.get("due_date_str"),
        days_remaining=assessment_ctx.get("days_until"),
        concepts=concepts,
        overall_readiness=round(overall, 3),
        ready_count=ready_count,
        total_count=total,
    )
