"""Concept Extractor — extracts discrete, testable concepts from lecture content.

Uses Gemini 2.5 Pro with thinking for higher quality extraction.
"""

from __future__ import annotations

import json
import logging

from google import genai
from google.genai import types

logger = logging.getLogger(__name__)

CONCEPT_EXTRACTION_PROMPT = """You are an expert educator analyzing lecture content.

Extract all key concepts from this lecture. A 'concept' is a discrete, testable \
piece of knowledge that a student should understand after attending this lecture.

For each concept, provide:
1. title: Clear, concise name (e.g., 'First Law of Thermodynamics')
2. description: 1-2 sentence explanation a student should know
3. category: One of: 'definition', 'theorem', 'process', 'concept', 'example', 'formula'
4. difficulty_estimate: 0.0 (introductory) to 1.0 (graduate-level)
5. related_concepts: Other concepts from THIS lecture that this builds upon (titles)

Guidelines:
- Extract 15-30 concepts for a typical 50-minute lecture
- Include both core concepts AND supporting details
- Definitions, theorems, processes, formulas, and relationships are all concepts
- Mark difficulty based on Bloom's taxonomy level required:
  - 0.0-0.2: Remember/recall (basic definitions)
  - 0.2-0.4: Understand (explain in own words)
  - 0.4-0.6: Apply (use in new situations)
  - 0.6-0.8: Analyze (break down, compare)
  - 0.8-1.0: Evaluate/Create (synthesize, judge)
- Do NOT extract meta-concepts like 'lecture overview' or 'homework reminder'
- Think step-by-step about what a student needs to learn.

LECTURE CONTENT:
{content}

Output a JSON array of concepts. Output ONLY the JSON array, no other text."""


async def extract_concepts(aligned_segments: list[dict]) -> list[dict]:
    """Extract key concepts from aligned lecture content.

    Uses Gemini 2.5 Pro for higher quality extraction.

    Args:
        aligned_segments: List of aligned segments from Content Aligner
            [{{start, end, text, speaker, slide_number, source}}, ...]

    Returns:
        List of extracted concepts:
            [{{title, description, category, difficulty_estimate, related_concepts}}, ...]

    Raises:
        ConceptExtractionError: If extraction fails.
    """
    client = genai.Client()

    content_text = format_content_for_extraction(aligned_segments)
    prompt = CONCEPT_EXTRACTION_PROMPT.format(content=content_text)

    try:
        response = await client.aio.models.generate_content(
            model="gemini-2.5-pro",
            contents=[types.Content(role="user", parts=[types.Part(text=prompt)])],
            config=types.GenerateContentConfig(
                temperature=0.2,
                max_output_tokens=16384,
            ),
        )

        result_text = response.text.strip()
        if result_text.startswith("```"):
            result_text = result_text.split("```")[1]
            if result_text.startswith("json"):
                result_text = result_text[4:]

        concepts = json.loads(result_text)
        validated = validate_concepts(concepts)

        logger.info("Concept extraction complete: %d concepts", len(validated))
        return validated

    except json.JSONDecodeError as e:
        raise ConceptExtractionError(f"Failed to parse concepts JSON: {e}") from e
    except ConceptExtractionError:
        raise
    except Exception as e:
        logger.error("Concept extraction failed: %s", e)
        raise ConceptExtractionError(f"Concept extraction failed: {e}") from e


def format_content_for_extraction(segments: list[dict]) -> str:
    """Format aligned segments into readable text for the extraction prompt."""
    parts = []
    for seg in segments:
        timestamp = ""
        if seg.get("start") is not None:
            minutes = int(seg["start"] // 60)
            seconds = int(seg["start"] % 60)
            timestamp = f"[{minutes:02d}:{seconds:02d}] "

        slide_ref = ""
        if seg.get("slide_number"):
            slide_ref = f"[Slide {seg['slide_number']}] "

        speaker = seg.get("speaker", "")
        speaker_prefix = (
            f"({speaker}) " if speaker and speaker != "professor" else ""
        )

        parts.append(f"{timestamp}{slide_ref}{speaker_prefix}{seg['text']}")

    return "\n".join(parts)


VALID_CATEGORIES = {
    "definition", "theorem", "process", "concept", "example", "formula",
}


def validate_concepts(concepts: list[dict]) -> list[dict]:
    """Validate and clean extracted concepts."""
    validated = []
    seen_titles: set[str] = set()

    for c in concepts:
        title = c.get("title", "").strip()
        if not title:
            continue

        title_lower = title.lower()
        if title_lower in seen_titles:
            continue
        seen_titles.add(title_lower)

        category = c.get("category", "concept").lower()
        if category not in VALID_CATEGORIES:
            category = "concept"

        difficulty = float(c.get("difficulty_estimate", 0.5))
        difficulty = max(0.0, min(1.0, difficulty))

        validated.append({
            "title": title,
            "description": c.get("description", ""),
            "category": category,
            "difficulty_estimate": difficulty,
            "related_concepts": c.get("related_concepts", []),
        })

    return validated


class ConceptExtractionError(Exception):
    """Raised when concept extraction fails."""
