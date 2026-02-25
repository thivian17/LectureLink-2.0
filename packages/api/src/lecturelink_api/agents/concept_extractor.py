"""Concept Extractor — extracts discrete, testable concepts from lecture content.

Uses Gemini 2.5 Pro with thinking for higher quality extraction.
"""

from __future__ import annotations

import json
import logging
import re
import unicodedata

from google.genai import types

from ..services.genai_client import get_genai_client as _get_client

logger = logging.getLogger(__name__)

CONCEPT_EXTRACTION_PROMPT = """You are an expert educator analyzing lecture content.

Extract the KEY concepts from this lecture using a two-level hierarchy:
- **Parent concepts** are the major topics/ideas (8-15 per lecture).
- **Subconcepts** are the granular, testable pieces of knowledge within each parent.

For each PARENT concept, provide:
1. title: Clear, concise name (e.g., "Simplex Method")
2. description: 2-3 sentence overview of the concept
3. category: One of: 'definition', 'theorem', 'process', 'concept', 'example', 'formula'
4. difficulty_estimate: 0.0 (introductory) to 1.0 (graduate-level), averaged across subconcepts
5. related_concepts: Other parent concepts from THIS lecture that it builds upon (titles)
6. subconcepts: Array of granular sub-topics within this concept

For each SUBCONCEPT, provide:
1. title: Specific name (e.g., "Pivot Column Selection")
2. description: 1-2 sentence explanation a student should know
3. difficulty_estimate: 0.0 to 1.0

STRICT RULES:
- Output between 8 and 15 PARENT concepts. No more than 15 parents.
- Each parent should have 1-5 subconcepts. Simple definitions may have 1; \
complex processes may have up to 5.
- All granular details go into subconcepts, NOT as separate parent entries.
  GOOD: Parent "Simplex Method" with subconcepts ["Pivot Column Selection", \
"Pivot Row Selection", "Optimality Condition", "Tableau Setup"]
  BAD: Four separate parent entries for each of those.
- Each title must be UNIQUE across ALL parents AND subconcepts.
- Use singular/plural consistently.
- If a topic is discussed in multiple slides or segments, it is still ONE concept.
- Mark difficulty based on Bloom's taxonomy level required:
  - 0.0-0.2: Remember/recall (basic definitions)
  - 0.2-0.4: Understand (explain in own words)
  - 0.4-0.6: Apply (use in new situations)
  - 0.6-0.8: Analyze (break down, compare)
  - 0.8-1.0: Evaluate/Create (synthesize, judge)
- Do NOT extract meta-concepts like 'lecture overview' or 'homework reminder'

EXAMPLE OUTPUT:
[
  {{
    "title": "Simplex Method",
    "description": "An iterative algorithm for solving linear programs by moving \
along edges of the feasible region until the optimal vertex is reached.",
    "category": "process",
    "difficulty_estimate": 0.6,
    "related_concepts": ["Linear Program Formulation"],
    "subconcepts": [
      {{"title": "Simplex Tableau", "description": "A tabular representation ...", "difficulty_estimate": 0.4}},
      {{"title": "Pivot Selection Rules", "description": "The entering variable ...", "difficulty_estimate": 0.6}},
      {{"title": "Optimality Condition", "description": "The solution is optimal when ...", "difficulty_estimate": 0.5}}
    ]
  }}
]

LECTURE CONTENT:
{content}

Output a JSON array of parent concepts with nested subconcepts. Output ONLY the \
JSON array, no other text."""


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
    client = _get_client()

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


def _normalize_title(title: str) -> str:
    """Normalize a concept title for deduplication.

    Strips punctuation, normalizes unicode quotes, lowercases, removes
    trailing 's' (simple plural), and collapses whitespace so that
    "Binary Variable", "Binary Variables", and "'Binary Variables'"
    all map to the same key.
    """
    # Normalize unicode (smart quotes → ASCII, accents → base chars)
    text = unicodedata.normalize("NFKD", title)
    # Lowercase
    text = text.lower()
    # Replace any quote characters with nothing
    text = re.sub(r"['\"\u2018\u2019\u201c\u201d`]", "", text)
    # Strip parenthetical qualifiers like "(Entering Variable)"
    text = re.sub(r"\s*\([^)]*\)\s*", " ", text)
    # Strip non-alphanumeric (keep spaces)
    text = re.sub(r"[^a-z0-9 ]", " ", text)
    # Collapse whitespace
    text = re.sub(r"\s+", " ", text).strip()
    # Remove trailing 's' for simple plural normalization
    if text.endswith("s") and not text.endswith("ss"):
        text = text[:-1]
    return text


def _validate_subconcepts(
    raw: list,
    seen_keys: set[str],
) -> list[dict]:
    """Validate and deduplicate subconcepts within a parent."""
    validated = []
    for sc in raw:
        if not isinstance(sc, dict):
            continue
        title = sc.get("title", "").strip()
        if not title:
            continue
        norm_key = _normalize_title(title)
        if not norm_key or norm_key in seen_keys:
            logger.debug("Dedup subconcept: dropping %r", title)
            continue
        seen_keys.add(norm_key)

        difficulty = float(sc.get("difficulty_estimate", 0.5))
        difficulty = max(0.0, min(1.0, difficulty))

        validated.append({
            "title": title,
            "description": sc.get("description", ""),
            "difficulty_estimate": difficulty,
        })
    return validated


def validate_concepts(concepts: list[dict]) -> list[dict]:
    """Validate, clean, and deduplicate extracted concepts and subconcepts."""
    validated = []
    # Single set across ALL parents + subconcepts for global uniqueness
    seen_keys: set[str] = set()

    for c in concepts:
        title = c.get("title", "").strip()
        if not title:
            continue

        norm_key = _normalize_title(title)
        if not norm_key:
            continue
        if norm_key in seen_keys:
            logger.debug("Dedup: dropping %r (normalized: %r)", title, norm_key)
            continue
        seen_keys.add(norm_key)

        category = c.get("category", "concept").lower()
        if category not in VALID_CATEGORIES:
            category = "concept"

        difficulty = float(c.get("difficulty_estimate", 0.5))
        difficulty = max(0.0, min(1.0, difficulty))

        subconcepts = _validate_subconcepts(
            c.get("subconcepts") or [], seen_keys,
        )

        validated.append({
            "title": title,
            "description": c.get("description", ""),
            "category": category,
            "difficulty_estimate": difficulty,
            "related_concepts": c.get("related_concepts", []),
            "subconcepts": subconcepts,
        })

    return validated


class ConceptExtractionError(Exception):
    """Raised when concept extraction fails."""
