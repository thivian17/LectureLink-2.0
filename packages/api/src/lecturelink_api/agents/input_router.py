"""Input Router — classifies uploaded files and determines the processing path."""

from __future__ import annotations

import logging
from pathlib import PurePosixPath
from urllib.parse import urlparse

from lecturelink_api.models.lecture_models import RouteResult

logger = logging.getLogger(__name__)

SUPPORTED_AUDIO = {".mp3", ".wav", ".m4a", ".ogg", ".webm", ".flac"}
SUPPORTED_SLIDES = {".pdf", ".pptx"}
SUPPORTED_ALL = SUPPORTED_AUDIO | SUPPORTED_SLIDES
MAX_AUDIO_SIZE_MB = 200


async def route_input(file_urls: list[str]) -> RouteResult:
    """Classify uploaded files and determine processing path.

    Returns a ``RouteResult`` indicating which branch the pipeline should take.

    Raises:
        ValueError: No supported files, unsupported format, or multiple audio files.
    """
    if not file_urls:
        raise ValueError("No files provided")

    audio_files: list[str] = []
    slide_files: list[str] = []

    for url in file_urls:
        # Strip query params from signed URLs before extracting extension
        clean_path = urlparse(url).path if url.startswith("http") else url
        ext = PurePosixPath(clean_path).suffix.lower()
        if ext in SUPPORTED_AUDIO:
            audio_files.append(url)
        elif ext in SUPPORTED_SLIDES:
            slide_files.append(url)
        else:
            raise ValueError(
                f"Unsupported file format: {ext}. "
                f"Supported: {sorted(SUPPORTED_ALL)}"
            )

    if not audio_files and not slide_files:
        raise ValueError("No supported audio or slide files found")

    if len(audio_files) > 1:
        raise ValueError(
            "Please upload a single audio file. "
            "Multiple audio file concatenation coming soon."
        )

    has_audio = len(audio_files) > 0
    has_slides = len(slide_files) > 0

    if has_audio and has_slides:
        path = "audio+slides"
    elif has_audio:
        path = "audio_only"
    else:
        path = "slides_only"

    result = RouteResult(
        processing_path=path,
        audio_url=audio_files[0] if has_audio else None,
        slides_url=slide_files[0] if has_slides else None,
    )

    logger.info(
        "Routed input: path=%s audio=%s slides=%s",
        path, result.audio_url, result.slides_url,
    )
    return result
