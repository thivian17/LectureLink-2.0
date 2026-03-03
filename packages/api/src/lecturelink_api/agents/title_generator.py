"""Title Generator — generates a concise academic lecture title from content.

Uses Gemini 2.5 Flash (fast, cheap — title gen doesn't need Pro).
"""

from __future__ import annotations

import logging

from google.genai import types

from ..services.genai_client import get_genai_client as _get_client

logger = logging.getLogger(__name__)

TITLE_GENERATION_PROMPT = """\
Generate a concise academic lecture title (5-10 words) from this content.
Output only the title, no quotes or extra text.

CONTENT:
{content}"""


async def generate_title(aligned_segments: list[dict]) -> str | None:
    """Generate a descriptive lecture title from aligned content.

    Args:
        aligned_segments: List of aligned segments from Content Aligner.

    Returns:
        A concise title string, or None if generation fails.
    """
    if not aligned_segments:
        return None

    # Build content text from first ~3000 chars (enough for topic identification)
    parts: list[str] = []
    char_count = 0
    for seg in aligned_segments:
        text = seg.get("text", "")
        if not text:
            continue
        parts.append(text)
        char_count += len(text)
        if char_count >= 3000:
            break

    content_text = "\n".join(parts)[:3000]
    if not content_text.strip():
        return None

    prompt = TITLE_GENERATION_PROMPT.format(content=content_text)

    try:
        client = _get_client()
        response = await client.aio.models.generate_content(
            model="gemini-2.5-flash",
            contents=[types.Content(role="user", parts=[types.Part(text=prompt)])],
            config=types.GenerateContentConfig(
                temperature=0.3,
                max_output_tokens=64,
            ),
        )

        title = response.text.strip().strip('"').strip("'")
        if not title or len(title) > 200:
            return None

        logger.info("Generated lecture title: %s", title)
        return title

    except Exception as e:
        logger.warning("Title generation failed (non-fatal): %s", e)
        return None
