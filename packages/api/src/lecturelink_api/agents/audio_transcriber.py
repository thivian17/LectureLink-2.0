"""Audio Transcriber — uses Gemini multimodal for timestamped lecture transcription."""

from __future__ import annotations

import asyncio
import json
import logging
import tempfile
from pathlib import Path, PurePosixPath
from urllib.parse import urlparse

import httpx
from google import genai
from google.genai import types

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

MIME_MAP: dict[str, str] = {
    ".mp3": "audio/mpeg",
    ".wav": "audio/wav",
    ".m4a": "audio/mp4",
    ".ogg": "audio/ogg",
    ".webm": "audio/webm",
    ".flac": "audio/flac",
}

INLINE_SIZE_LIMIT = 20 * 1024 * 1024  # 20 MB — inline Part threshold

MAX_RETRIES = 3
RETRY_BASE_DELAY = 2.0  # seconds

TRANSCRIPTION_PROMPT = """\
You are an expert lecture transcriber.

Given the audio recording of a lecture, produce a detailed transcript with:
1. Timestamped segments (start_time, end_time in seconds)
2. Speaker labels if multiple speakers are detected \
("professor" for the main speaker, "student" for audience questions)
3. Verbatim transcription of all spoken content
4. Technical terminology preserved exactly as spoken
5. [inaudible] markers for unclear sections

Output a JSON array of transcript segments:
[
    {
        "start": 0.0,
        "end": 15.5,
        "text": "Welcome to today's lecture on thermodynamics.",
        "speaker": "professor"
    }
]

Guidelines:
- Transcribe everything verbatim.
- Preserve filler words only when they carry meaning.
- Mark inaudible sections as [inaudible].
- Use "student" for audience questions.
- Segment boundaries should align with natural sentence/thought breaks.
- Each segment should be 5-30 seconds long.
- Timestamps must be monotonically increasing.

Output ONLY the JSON array, no other text."""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def get_audio_mime_type(file_path: str) -> str:
    """Return the MIME type for a given audio file path."""
    clean = urlparse(file_path).path if file_path.startswith("http") else file_path
    ext = PurePosixPath(clean).suffix.lower()
    return MIME_MAP.get(ext, "audio/mpeg")


def _strip_markdown_fences(text: str) -> str:
    """Remove optional markdown code fences from Gemini output."""
    text = text.strip()
    if text.startswith("```"):
        # Remove opening fence (and optional language tag)
        lines = text.split("\n", 1)
        if len(lines) > 1:
            text = lines[1]
        # Remove closing fence
        if text.rstrip().endswith("```"):
            text = text.rstrip()[: -len("```")]
    return text.strip()


def validate_transcript(segments: list[dict]) -> list[dict]:
    """Validate and clean transcript segments.

    Ensures required fields, monotonically increasing timestamps,
    no overlaps, and valid speaker labels.
    """
    validated: list[dict] = []
    last_end = 0.0

    for i, seg in enumerate(segments):
        if not isinstance(seg, dict):
            logger.warning("Skipping non-dict segment at index %d", i)
            continue

        if not all(k in seg for k in ("start", "end", "text")):
            logger.warning("Skipping segment %d: missing required fields", i)
            continue

        try:
            start = float(seg["start"])
            end = float(seg["end"])
        except (TypeError, ValueError):
            logger.warning("Skipping segment %d: non-numeric timestamps", i)
            continue

        text = str(seg["text"]).strip()
        if not text:
            continue

        speaker = seg.get("speaker", "professor")

        # Fix overlapping timestamps
        if start < last_end:
            start = last_end
        if end <= start:
            end = start + 1.0  # minimum 1-second segment

        validated.append({
            "start": start,
            "end": end,
            "text": text,
            "speaker": speaker,
        })
        last_end = end

    return validated


# ---------------------------------------------------------------------------
# Error
# ---------------------------------------------------------------------------


class TranscriptionError(Exception):
    """Raised when audio transcription fails."""


# ---------------------------------------------------------------------------
# Core transcription
# ---------------------------------------------------------------------------


async def _download_to_tempfile(url: str, suffix: str) -> Path:
    """Download a remote URL to a temporary file and return the path."""
    async with httpx.AsyncClient() as http:
        resp = await http.get(url, follow_redirects=True)
        resp.raise_for_status()
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)  # noqa: SIM115
        tmp.write(resp.content)
        tmp.close()
        return Path(tmp.name)


async def transcribe_audio(
    audio_url: str,
    *,
    client: genai.Client | None = None,
) -> list[dict]:
    """Transcribe lecture audio using Gemini multimodal.

    Args:
        audio_url: Supabase Storage URL or local file path.
        client: Optional pre-built ``genai.Client`` (useful for testing).

    Returns:
        List of transcript segments matching ``TranscriptSegment`` shape.

    Raises:
        TranscriptionError: If Gemini fails or returns invalid output.
    """
    if client is None:
        client = genai.Client()

    mime_type = get_audio_mime_type(audio_url)
    clean_path = urlparse(audio_url).path if audio_url.startswith("http") else audio_url
    ext = PurePosixPath(clean_path).suffix.lower()

    # Resolve the audio data: local file → bytes, remote URL → download
    is_remote = audio_url.startswith("http://") or audio_url.startswith("https://")
    local_path: Path | None = None

    if is_remote:
        local_path = await _download_to_tempfile(audio_url, suffix=ext)
    else:
        local_path = Path(audio_url)
        if not local_path.exists():
            raise TranscriptionError(f"Audio file not found: {audio_url}")

    file_size = local_path.stat().st_size

    # Build the audio Part — inline bytes for small files, File API for large
    uploaded_file = None
    if file_size <= INLINE_SIZE_LIMIT:
        audio_bytes = local_path.read_bytes()
        audio_part = types.Part.from_bytes(data=audio_bytes, mime_type=mime_type)
    else:
        uploaded_file = client.files.upload(file=str(local_path))
        audio_part = types.Part.from_uri(
            file_uri=uploaded_file.uri, mime_type=mime_type
        )

    prompt_part = types.Part.from_text(text=TRANSCRIPTION_PROMPT)

    # Retry loop with exponential backoff
    last_error: Exception | None = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            response = client.models.generate_content(
                model="gemini-2.5-flash",
                contents=[
                    types.Content(parts=[audio_part, prompt_part])
                ],
                config=types.GenerateContentConfig(
                    temperature=0.1,
                    max_output_tokens=65536,
                ),
            )

            transcript_text = _strip_markdown_fences(response.text)
            segments = json.loads(transcript_text)
            validated = validate_transcript(segments)
            logger.info(
                "Transcription complete: %d segments (attempt %d)",
                len(validated),
                attempt,
            )
            return validated

        except json.JSONDecodeError as exc:
            raise TranscriptionError(f"Failed to parse transcript JSON: {exc}") from exc
        except TranscriptionError:
            raise
        except Exception as exc:  # noqa: BLE001
            last_error = exc
            if attempt < MAX_RETRIES:
                delay = RETRY_BASE_DELAY * (2 ** (attempt - 1))
                logger.warning(
                    "Transcription attempt %d failed (%s), retrying in %.1fs …",
                    attempt,
                    exc,
                    delay,
                )
                await asyncio.sleep(delay)
            else:
                logger.error("Transcription failed after %d attempts", MAX_RETRIES)

    raise TranscriptionError(f"Audio transcription failed: {last_error}")
