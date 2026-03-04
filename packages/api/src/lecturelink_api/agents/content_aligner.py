"""Content Aligner — aligns transcript segments to slide numbers.

Handles three input modes:
  1. audio+slides: Uses Gemini to semantically align transcript to slides
  2. audio_only: Passes through transcript segments tagged with source='audio'
  3. slides_only: Converts slide analyses to pseudo-segments tagged with source='slide'
"""

from __future__ import annotations

import json
import logging

from google import genai
from google.genai import types

logger = logging.getLogger(__name__)

ALIGNMENT_PROMPT = """Given transcript segments and slide analysis, align each \
transcript segment to the most relevant slide.

Use these signals to determine alignment:
1. Temporal: Slides typically advance every 2-5 minutes
2. Semantic: Match transcript topics to slide content
3. Verbal cues: "next slide", "as you can see here", "this diagram shows"
4. Sequential: Slides are shown in order; don't jump backwards unless the \
speaker explicitly references an earlier slide

Output: The same transcript segments with an added 'slide_number' field on \
each segment, plus a 'source' field set to 'aligned'.

If alignment is ambiguous, use the most recent confidently-aligned slide number.

TRANSCRIPT SEGMENTS:
{transcript}

SLIDE ANALYSIS:
{slides}

Output a JSON array of aligned segments:
[
    {{
        "start": 0.0,
        "end": 15.5,
        "text": "Welcome to today's lecture...",
        "speaker": "professor",
        "slide_number": 1,
        "source": "aligned"
    }}
]

Output ONLY the JSON array, no other text."""


async def align_content(
    transcript_segments: list[dict] | None,
    slide_analysis: list[dict] | None,
) -> list[dict]:
    """Align transcript segments to slides, or pass through single-source content.

    Handles three modes:
      1. audio+slides — align transcript to slides using Gemini
      2. audio_only — return transcript segments with source='audio'
      3. slides_only — convert slide analysis to pseudo-segments with source='slide'

    Args:
        transcript_segments: From audio transcriber (None if slides-only).
        slide_analysis: From slide analyzer (None if audio-only).

    Returns:
        List of aligned segments with keys: start, end, text, speaker,
        slide_number, source.

    Raises:
        ValueError: If neither transcript nor slides are provided.
    """
    has_transcript = bool(transcript_segments)
    has_slides = bool(slide_analysis)

    if has_transcript and has_slides:
        return await _align_with_gemini(transcript_segments, slide_analysis)

    if has_transcript:
        return [
            {
                "start": seg.get("start"),
                "end": seg.get("end"),
                "text": seg["text"],
                "speaker": seg.get("speaker", "professor"),
                "slide_number": None,
                "source": "audio",
            }
            for seg in transcript_segments
        ]

    if has_slides:
        return [
            {
                "start": None,
                "end": None,
                "text": _slide_to_text(slide),
                "speaker": "professor",
                "slide_number": slide["slide_number"],
                "source": "slide",
            }
            for slide in slide_analysis
        ]

    raise ValueError("No transcript or slide data available for alignment")


async def _align_with_gemini(
    transcript: list[dict],
    slides: list[dict],
) -> list[dict]:
    """Use Gemini to align transcript segments to slides."""
    client = genai.Client()

    prompt = ALIGNMENT_PROMPT.format(
        transcript=json.dumps(transcript, indent=2),
        slides=json.dumps(slides, indent=2),
    )

    try:
        response = await client.aio.models.generate_content(
            model="gemini-2.5-flash",
            contents=[types.Content(role="user", parts=[types.Part(text=prompt)])],
            config=types.GenerateContentConfig(
                temperature=0.1,
                max_output_tokens=65536,
            ),
        )

        result_text = response.text.strip()
        if result_text.startswith("```"):
            result_text = result_text.split("```")[1]
            if result_text.startswith("json"):
                result_text = result_text[4:]

        aligned = json.loads(result_text)
        return validate_alignment(aligned, len(slides))

    except Exception as e:
        logger.warning("Alignment failed: %s. Returning unaligned transcript.", e)
        return _alignment_failed_passthrough(transcript)


def _alignment_failed_passthrough(transcript: list[dict]) -> list[dict]:
    """Return transcript segments with no slide alignment.

    Used when Gemini alignment fails — honestly reports "no results"
    instead of fabricating slide assignments.
    """
    return [
        {
            "start": seg.get("start"),
            "end": seg.get("end"),
            "text": seg.get("text", ""),
            "speaker": seg.get("speaker", "professor"),
            "slide_number": None,
            "source": "unaligned",
        }
        for seg in transcript
    ]


def validate_alignment(
    segments: list[dict], total_slides: int
) -> list[dict]:
    """Validate aligned segments have valid slide numbers and required fields.

    Segments with empty or whitespace-only text are skipped.
    """
    validated = []
    for seg in segments:
        text = seg.get("text", "")
        if not text or not text.strip():
            continue

        slide_num = seg.get("slide_number")
        if slide_num is not None:
            slide_num = max(1, min(int(slide_num), total_slides))

        validated.append(
            {
                "start": seg.get("start"),
                "end": seg.get("end"),
                "text": text,
                "speaker": seg.get("speaker", "professor"),
                "slide_number": slide_num,
                "source": seg.get("source", "aligned"),
            }
        )
    return validated


def _slide_to_text(slide: dict) -> str:
    """Convert slide analysis to readable text for slides-only mode."""
    parts = []
    if slide.get("title"):
        parts.append(f"[Slide {slide['slide_number']}: {slide['title']}]")
    if slide.get("text_content"):
        parts.append(slide["text_content"])
    if slide.get("visual_description"):
        parts.append(f"[Visual: {slide['visual_description']}]")
    return "\n".join(parts) if parts else f"[Slide {slide['slide_number']}]"
