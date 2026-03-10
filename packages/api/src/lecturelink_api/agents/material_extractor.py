"""Material Text Extractor — extracts clean text from course material documents.

Supports PDF (via Gemini vision), DOCX (via python-docx/pandoc), PPTX (via
slide_analyzer), and plain text (TXT/MD).
"""

from __future__ import annotations

import io
import json
import logging

import httpx
from google import genai
from google.genai import types

logger = logging.getLogger(__name__)


class MaterialExtractionError(Exception):
    """Raised when material text extraction fails."""


EXTRACTION_PROMPT = """Extract ALL text content from this document.

Preserve the document's logical structure:
- Identify section headings and their hierarchy
- Keep numbered/bulleted lists intact
- Preserve any questions, problems, or exercises as structured items
- Note page breaks where visible

Output as JSON:
{
    "title": "detected title or null",
    "page_count": number or null,
    "sections": [
        {
            "title": "Section heading or null",
            "content": "Full text content of this section",
            "page_number": number or null
        }
    ],
    "full_text": "Complete concatenated text"
}

Extract EVERYTHING — do not summarize or skip content."""


async def extract_material_text(
    file_url: str,
    file_extension: str,
) -> dict:
    """Extract text from a material document.

    Args:
        file_url: Supabase storage URL for the file.
        file_extension: File extension (e.g., ".pdf", ".docx").

    Returns:
        Dict with keys: title, full_text, page_count, sections, preview
    """
    ext = file_extension.lower()

    if ext == ".pdf":
        return await _extract_from_pdf(file_url)
    elif ext == ".pptx":
        return await _extract_from_pptx(file_url)
    elif ext == ".docx":
        return await _extract_from_docx(file_url)
    elif ext in (".txt", ".md"):
        return await _extract_from_text(file_url)
    else:
        raise MaterialExtractionError(f"Unsupported file type: {ext}")


async def _extract_from_pdf(file_url: str) -> dict:
    """Extract text from PDF using Gemini vision."""
    try:
        if file_url.startswith(("http://", "https://")):
            part = types.Part.from_uri(file_uri=file_url, mime_type="application/pdf")
        else:
            from pathlib import Path

            data = Path(file_url).read_bytes()
            part = types.Part.from_bytes(data=data, mime_type="application/pdf")

        content = types.Content(
            role="user",
            parts=[part, types.Part(text=EXTRACTION_PROMPT)],
        )

        client = genai.Client()
        response = await client.aio.models.generate_content(
            model="gemini-2.5-flash",
            contents=[content],
            config=types.GenerateContentConfig(
                temperature=0.1,
                max_output_tokens=65536,
            ),
        )

        return _parse_extraction_response(response.text or "")
    except MaterialExtractionError:
        raise
    except Exception as e:
        raise MaterialExtractionError(f"PDF extraction failed: {e}") from e


async def _extract_from_pptx(file_url: str) -> dict:
    """Extract text from PPTX using slide_analyzer."""
    try:
        from .slide_analyzer import analyze_slides

        slides = await analyze_slides(file_url)

        sections = []
        all_text_parts = []
        for slide in slides:
            text = slide.get("text_content", "")
            title = slide.get("title")
            slide_num = slide.get("slide_number")
            if text:
                sections.append({
                    "title": title,
                    "content": text,
                    "page_number": slide_num,
                })
                all_text_parts.append(text)

        full_text = "\n\n".join(all_text_parts)
        detected_title = slides[0].get("title") if slides else None

        return {
            "title": detected_title,
            "full_text": full_text,
            "page_count": len(slides),
            "sections": sections,
            "preview": full_text[:500],
        }
    except Exception as e:
        raise MaterialExtractionError(f"PPTX extraction failed: {e}") from e


async def _extract_from_docx(file_url: str) -> dict:
    """Extract text from DOCX using Gemini vision as primary method."""
    try:
        if file_url.startswith(("http://", "https://")):
            async with httpx.AsyncClient() as client:
                resp = await client.get(file_url)
                resp.raise_for_status()
                file_bytes = resp.content
        else:
            from pathlib import Path

            file_bytes = Path(file_url).read_bytes()

        # Try python-docx first for better quality
        try:
            from docx import Document

            doc = Document(io.BytesIO(file_bytes))
            paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
            full_text = "\n\n".join(paragraphs)

            if full_text.strip():
                return {
                    "title": paragraphs[0] if paragraphs else None,
                    "full_text": full_text,
                    "page_count": None,
                    "sections": [{"title": None, "content": full_text, "page_number": None}],
                    "preview": full_text[:500],
                }
        except ImportError:
            logger.info("python-docx not available, falling back to Gemini")

        # Fallback: use Gemini vision
        part = types.Part.from_bytes(
            data=file_bytes,
            mime_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        )
        content = types.Content(
            role="user",
            parts=[part, types.Part(text=EXTRACTION_PROMPT)],
        )

        client = genai.Client()
        response = await client.aio.models.generate_content(
            model="gemini-2.5-flash",
            contents=[content],
            config=types.GenerateContentConfig(
                temperature=0.1,
                max_output_tokens=65536,
            ),
        )
        return _parse_extraction_response(response.text or "")

    except MaterialExtractionError:
        raise
    except Exception as e:
        raise MaterialExtractionError(f"DOCX extraction failed: {e}") from e


async def _extract_from_text(file_url: str) -> dict:
    """Read plain text or markdown files directly."""
    try:
        if file_url.startswith(("http://", "https://")):
            async with httpx.AsyncClient() as client:
                resp = await client.get(file_url)
                resp.raise_for_status()
                full_text = resp.text
        else:
            from pathlib import Path

            full_text = Path(file_url).read_text(encoding="utf-8")

        # Split into sections by markdown headings or double newlines
        lines = full_text.split("\n")
        title = None
        if lines and lines[0].startswith("#"):
            title = lines[0].lstrip("#").strip()

        return {
            "title": title,
            "full_text": full_text,
            "page_count": None,
            "sections": [{"title": title, "content": full_text, "page_number": None}],
            "preview": full_text[:500],
        }
    except Exception as e:
        raise MaterialExtractionError(f"Text extraction failed: {e}") from e


def _parse_extraction_response(text: str) -> dict:
    """Parse Gemini JSON response into extraction result dict."""
    result_text = text.strip()

    # Strip markdown code fences if present
    if result_text.startswith("```"):
        result_text = result_text.split("```")[1]
        if result_text.startswith("json"):
            result_text = result_text[4:]

    try:
        data = json.loads(result_text)
    except json.JSONDecodeError as e:
        # If JSON parsing fails, treat raw text as full_text
        logger.warning("Failed to parse Gemini JSON response: %s", e)
        return {
            "title": None,
            "full_text": text,
            "page_count": None,
            "sections": [],
            "preview": text[:500],
        }

    full_text = data.get("full_text", "")
    sections = data.get("sections", [])

    # If full_text is empty but sections exist, concatenate
    if not full_text and sections:
        full_text = "\n\n".join(s.get("content", "") for s in sections)

    return {
        "title": data.get("title"),
        "full_text": full_text,
        "page_count": data.get("page_count"),
        "sections": sections,
        "preview": full_text[:500],
    }
