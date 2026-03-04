"""Concept Mapper — bridges lecture concepts to syllabus assessments.

Uses three signals: schedule match (50%), semantic similarity (30%),
and explicit coverage (20%) to determine which assessments each concept
is relevant to.
"""

from __future__ import annotations

import json
import logging

from google import genai
from google.genai import types

logger = logging.getLogger(__name__)

CONCEPT_MAPPING_PROMPT = """You are an educational content mapper.

Given:
1. Extracted concepts from a lecture (with titles and descriptions)
2. The course syllabus weekly schedule (topics per week)
3. All upcoming assessments (with titles, types, due dates, topics[])
4. The lecture date and number

Determine which assessments each concept is relevant to.

For each concept, output:
{{
    "concept_title": "First Law of Thermodynamics",
    "assessment_mappings": [
        {{
            "assessment_id": "uuid-here",
            "relevance_score": 0.85,
            "reasoning": "This concept falls within Week 5 material and Midterm 2 covers weeks 4-8"
        }}
    ]
}}

Scoring guidelines:
- 0.9-1.0: Assessment EXPLICITLY lists this concept/topic
- 0.7-0.9: Concept falls within the assessment's date/topic range
- 0.5-0.7: Concept is related but not directly covered
- Below 0.5: Don't include the mapping

Only map to assessments that have NOT yet passed (due date is in the future).

CONCEPTS:
{concepts}

SYLLABUS SCHEDULE:
{schedule}

ASSESSMENTS:
{assessments}

LECTURE DATE: {lecture_date}
LECTURE NUMBER: {lecture_number}

Output a JSON array of mappings. Output ONLY the JSON array, no other text."""


async def map_concepts_to_assessments(
    supabase,
    lecture_id: str,
    course_id: str,
    user_id: str,
    concepts: list[dict],
    lecture_date: str | None = None,
    lecture_number: int | None = None,
) -> list[dict]:
    """Map extracted concepts to upcoming assessments.

    Args:
        supabase: Supabase client.
        lecture_id: The lecture UUID.
        course_id: The course UUID.
        user_id: The owner user UUID.
        concepts: List of stored concepts (with 'id' and 'title').
        lecture_date: Date of the lecture (ISO format).
        lecture_number: Lecture number in the course sequence.

    Returns:
        List of concept_assessment_links created.
    """
    # Fetch course assessments
    assessments_result = (
        supabase.table("assessments")
        .select("*")
        .eq("course_id", course_id)
        .execute()
    )
    assessments = assessments_result.data

    if not assessments:
        logger.warning(
            "No assessments found for course %s. Skipping concept mapping.",
            course_id,
        )
        return []

    # Fetch syllabus schedule data (if available)
    schedule = _get_syllabus_schedule(supabase, course_id)

    # Build title -> ID map for concepts (case-insensitive)
    concept_id_map = {
        c["title"].lower(): c["id"] for c in concepts if c.get("id")
    }

    # Use Gemini to determine mappings
    client = genai.Client()

    concepts_for_prompt = [
        {
            "title": c["title"],
            "description": c.get("description", ""),
            "category": c.get("category", ""),
        }
        for c in concepts
    ]
    assessments_for_prompt = [
        {
            "assessment_id": a["id"],
            "title": a.get("title", ""),
            "type": a.get("assessment_type", ""),
            "due_date": a.get("due_date", ""),
            "weight": a.get("weight", 0),
            "topics": a.get("topics", []),
        }
        for a in assessments
    ]

    prompt = CONCEPT_MAPPING_PROMPT.format(
        concepts=json.dumps(concepts_for_prompt, indent=2),
        schedule=(
            json.dumps(schedule, indent=2)
            if schedule
            else "No schedule data available"
        ),
        assessments=json.dumps(assessments_for_prompt, indent=2),
        lecture_date=lecture_date or "Unknown",
        lecture_number=lecture_number or "Unknown",
    )

    try:
        response = await client.aio.models.generate_content(
            model="gemini-2.5-flash",
            contents=[types.Content(role="user", parts=[types.Part(text=prompt)])],
            config=types.GenerateContentConfig(
                temperature=0.1,
                max_output_tokens=16384,
            ),
        )

        result_text = response.text.strip()
        if result_text.startswith("```"):
            result_text = result_text.split("```")[1]
            if result_text.startswith("json"):
                result_text = result_text[4:]

        mappings = json.loads(result_text)

    except Exception as e:
        logger.warning(
            "Concept mapping via Gemini failed: %s. No mappings will be created.", e,
        )
        mappings = []

    # Store mappings in concept_assessment_links
    links = []
    for mapping in mappings:
        concept_title = mapping.get("concept_title", "").lower()
        concept_id = concept_id_map.get(concept_title)
        if not concept_id:
            continue

        for am in mapping.get("assessment_mappings", []):
            assessment_id = am.get("assessment_id")
            relevance = float(am.get("relevance_score", 0.5))

            if relevance < 0.5:
                continue

            links.append({
                "concept_id": concept_id,
                "assessment_id": assessment_id,
                "user_id": user_id,
                "mapping_confidence": relevance,
            })

    if links:
        result = (
            supabase.table("concept_assessment_links")
            .upsert(links, on_conflict="concept_id,assessment_id")
            .execute()
        )
        logger.info(
            "Created %d concept-assessment links for lecture %s",
            len(result.data), lecture_id,
        )
        return result.data

    return []


def _get_syllabus_schedule(supabase, course_id: str) -> list[dict]:
    """Fetch parsed syllabus schedule for the course."""
    try:
        syllabi = (
            supabase.table("syllabi")
            .select("raw_extraction")
            .eq("course_id", course_id)
            .eq("status", "confirmed")
            .limit(1)
            .execute()
        )

        if syllabi.data and syllabi.data[0].get("raw_extraction"):
            data = syllabi.data[0]["raw_extraction"]
            return data.get("schedule", [])
    except Exception as e:
        logger.warning("Failed to fetch syllabus schedule: %s", e)

    return []


