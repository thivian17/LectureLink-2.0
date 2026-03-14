"""Match uploaded filenames to lecture numbers using heuristics + LLM."""

from __future__ import annotations

import json
import logging
import re

from google.genai import types

from .genai_client import get_genai_client

logger = logging.getLogger(__name__)

# Patterns ordered from most specific to least specific
_PATTERNS: list[tuple[re.Pattern, float]] = [
    (re.compile(r"class\s*(\d+)", re.IGNORECASE), 0.95),
    (re.compile(r"lec(?:ture)?\s*[-_.]?\s*(\d+)", re.IGNORECASE), 0.95),
    (re.compile(r"session\s*(\d+)", re.IGNORECASE), 0.9),
    (re.compile(r"week\s*(\d+)", re.IGNORECASE), 0.7),
    (re.compile(r"\bL(\d+)\b"), 0.8),
    # Bare number at end of stem (lowest confidence)
    (re.compile(r"[-_\s](\d+)\s*(?:\(\d+\))?\s*\.\w+$"), 0.5),
]


def heuristic_match(
    filename: str, valid_numbers: set[int],
) -> tuple[int | None, float]:
    """Try regex patterns to extract a lecture number from a filename.

    Returns (lecture_number, confidence) or (None, 0.0).
    """
    for pattern, confidence in _PATTERNS:
        m = pattern.search(filename)
        if m:
            num = int(m.group(1))
            if num in valid_numbers:
                return num, confidence
    return None, 0.0


async def match_files_to_lectures(
    filenames: list[str],
    checklist: list[dict],
) -> list[dict]:
    """Match filenames to lecture numbers using Gemini Flash with heuristic fallback.

    Args:
        filenames: List of uploaded filenames.
        checklist: Lecture checklist dicts with lecture_number, topic_hint, expected_date.

    Returns:
        List of dicts with filename, lecture_number, confidence.
    """
    valid_numbers = {item["lecture_number"] for item in checklist}

    # Build heuristic results first as fallback
    heuristic_results = {}
    for fname in filenames:
        num, conf = heuristic_match(fname, valid_numbers)
        heuristic_results[fname] = {"filename": fname, "lecture_number": num, "confidence": conf}

    # Try LLM matching
    try:
        llm_results = await _llm_match(filenames, checklist)
        # Merge: prefer LLM result if it has higher confidence
        for result in llm_results:
            fname = result["filename"]
            if fname in heuristic_results:
                # Validate LLM-suggested number exists in checklist
                if result.get("lecture_number") and result["lecture_number"] in valid_numbers:
                    if result.get("confidence", 0) > heuristic_results[fname]["confidence"]:
                        heuristic_results[fname] = result
    except Exception:
        logger.warning("LLM file matching failed, using heuristic fallback", exc_info=True)

    return list(heuristic_results.values())


async def _llm_match(
    filenames: list[str],
    checklist: list[dict],
) -> list[dict]:
    """Call Gemini Flash to match filenames to lecture numbers."""
    schedule_lines = []
    for item in checklist:
        hint = item.get("topic_hint") or ""
        date_str = item.get("expected_date") or ""
        line = f"  Lecture {item['lecture_number']}"
        if date_str:
            line += f" — {date_str}"
        if hint:
            line += f" — \"{hint}\""
        schedule_lines.append(line)

    file_lines = [f"  {i + 1}. \"{f}\"" for i, f in enumerate(filenames)]

    prompt = (
        "Match these filenames to the lecture schedule below. "
        "Look for class numbers, lecture numbers, session numbers, week numbers, "
        "or topic keywords in the filenames.\n\n"
        "Lecture schedule:\n"
        + "\n".join(schedule_lines)
        + "\n\nFilenames:\n"
        + "\n".join(file_lines)
        + "\n\nRespond with ONLY a JSON array. Each element must have:\n"
        '  {"filename": "exact filename", "lecture_number": N, "confidence": 0.0-1.0}\n'
        "Set lecture_number to null and confidence to 0.0 if you cannot match a file."
    )

    client = get_genai_client()
    response = await client.aio.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt,
        config=types.GenerateContentConfig(
            temperature=0.0,
            max_output_tokens=1024,
        ),
    )

    text = response.text.strip()
    # Strip markdown fences if present
    if text.startswith("```"):
        text = re.sub(r"^```\w*\n?", "", text)
        text = re.sub(r"\n?```$", "", text)

    results = json.loads(text)
    if not isinstance(results, list):
        return []

    return [
        {
            "filename": r.get("filename", ""),
            "lecture_number": r.get("lecture_number"),
            "confidence": float(r.get("confidence", 0)),
        }
        for r in results
        if isinstance(r, dict) and "filename" in r
    ]
