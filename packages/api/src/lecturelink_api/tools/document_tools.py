"""Document text extraction tool for the LectureLink syllabus processor.

Routes extraction by file type:
- PDF  → Gemini 2.5 Flash multimodal (via google-genai SDK)
- DOCX → python-docx local extraction
- PPTX → python-pptx local extraction
"""

from __future__ import annotations

import asyncio
import io
from typing import Any

from google import genai
from google.genai import types
from loguru import logger

from lecturelink_api.config import get_settings

# ---------------------------------------------------------------------------
# PDF extraction via Gemini 2.5 Flash
# ---------------------------------------------------------------------------

async def _extract_pdf_with_gemini(file_bytes: bytes) -> dict[str, Any]:
    """Send raw PDF bytes to Gemini 2.5 Flash and ask for structured text extraction."""
    try:
        settings = get_settings()
        if settings.GOOGLE_API_KEY:
            client = genai.Client(api_key=settings.GOOGLE_API_KEY)
        else:
            client = genai.Client(
                vertexai=True,
                project=settings.GOOGLE_CLOUD_PROJECT,
                location="us-central1",
            )

        pdf_part = types.Part.from_bytes(data=file_bytes, mime_type="application/pdf")

        prompt = (
            "Extract ALL text from this PDF document. "
            "Preserve the original structure including headings, sub-headings, "
            "bullet/numbered lists, and tables. "
            "For tables, reproduce them as markdown tables. "
            "Return only the extracted text with no additional commentary."
        )

        response = await asyncio.to_thread(
            client.models.generate_content,
            model="gemini-2.5-flash",
            contents=[pdf_part, prompt],
        )

        text = response.text or ""
        return {
            "text": text,
            "method": "gemini-pdf",
            "page_count": None,
        }
    except Exception as exc:
        logger.error("Gemini PDF extraction failed: {}", exc)
        return {
            "text": "",
            "method": "gemini-pdf",
            "page_count": None,
            "error": f"Gemini extraction failed: {exc}",
        }


# ---------------------------------------------------------------------------
# DOCX extraction via python-docx
# ---------------------------------------------------------------------------

_HEADING_MARKERS: dict[str, str] = {
    "Heading 1": "# ",
    "Heading 2": "## ",
    "Heading 3": "### ",
    "Heading 4": "#### ",
    "Title": "# ",
    "Subtitle": "## ",
}


def _table_to_markdown(table) -> str:
    """Convert a python-docx Table to a markdown-formatted table string."""
    rows: list[list[str]] = []
    for row in table.rows:
        rows.append([cell.text.strip() for cell in row.cells])

    if not rows:
        return ""

    lines: list[str] = []
    # header row
    lines.append("| " + " | ".join(rows[0]) + " |")
    lines.append("| " + " | ".join("---" for _ in rows[0]) + " |")
    # data rows
    for row in rows[1:]:
        lines.append("| " + " | ".join(row) + " |")

    return "\n".join(lines)


async def _extract_docx(file_bytes: bytes) -> dict[str, Any]:
    """Extract text from a DOCX file preserving headings and tables."""
    from docx import Document

    def _do_extract() -> dict[str, Any]:
        doc = Document(io.BytesIO(file_bytes))
        parts: list[str] = []

        # Iterate over document body elements to preserve ordering of
        # paragraphs and tables.
        from docx.oxml.ns import qn

        for element in doc.element.body:
            tag = element.tag

            if tag == qn("w:p"):
                # It's a paragraph
                from docx.text.paragraph import Paragraph

                para = Paragraph(element, doc)
                style_name = para.style.name if para.style else "Normal"
                prefix = _HEADING_MARKERS.get(style_name, "")
                text = para.text.strip()
                if text:
                    parts.append(f"{prefix}{text}")

            elif tag == qn("w:tbl"):
                # It's a table
                from docx.table import Table

                tbl = Table(element, doc)
                md = _table_to_markdown(tbl)
                if md:
                    parts.append(md)

        return {
            "text": "\n\n".join(parts),
            "method": "docx",
            "page_count": None,
        }

    return await asyncio.to_thread(_do_extract)


# ---------------------------------------------------------------------------
# PPTX extraction via python-pptx
# ---------------------------------------------------------------------------

def _shapes_text(shapes) -> list[str]:
    """Recursively extract text from shapes, including group shapes."""
    texts: list[str] = []
    for shape in shapes:
        if shape.shape_type == 6:  # MSO_SHAPE_TYPE.GROUP
            texts.extend(_shapes_text(shape.shapes))
        elif shape.has_table:
            rows: list[list[str]] = []
            for row in shape.table.rows:
                rows.append([cell.text.strip() for cell in row.cells])
            if rows:
                lines = []
                lines.append("| " + " | ".join(rows[0]) + " |")
                lines.append("| " + " | ".join("---" for _ in rows[0]) + " |")
                for row in rows[1:]:
                    lines.append("| " + " | ".join(row) + " |")
                texts.append("\n".join(lines))
        elif shape.has_text_frame:
            frame_text = "\n".join(
                para.text.strip() for para in shape.text_frame.paragraphs if para.text.strip()
            )
            if frame_text:
                texts.append(frame_text)
    return texts


async def _extract_pptx(file_bytes: bytes) -> dict[str, Any]:
    """Extract text from a PPTX file including titles, body text, tables, and notes."""
    from pptx import Presentation

    def _do_extract() -> dict[str, Any]:
        prs = Presentation(io.BytesIO(file_bytes))
        slide_parts: list[str] = []

        for idx, slide in enumerate(prs.slides, start=1):
            # Title
            title = ""
            if slide.shapes.title and slide.shapes.title.has_text_frame:
                title = slide.shapes.title.text_frame.text.strip()

            header = f"## Slide {idx}: {title}" if title else f"## Slide {idx}"

            # Body content from all shapes
            content_lines = _shapes_text(slide.shapes)
            content = "\n".join(content_lines)

            # Speaker notes
            notes = ""
            if slide.has_notes_slide and slide.notes_slide.notes_text_frame:
                notes = slide.notes_slide.notes_text_frame.text.strip()

            section = header
            if content:
                section += f"\n{content}"
            if notes:
                section += f"\n\n**Notes:** {notes}"

            slide_parts.append(section)

        return {
            "text": "\n\n".join(slide_parts),
            "method": "pptx",
            "page_count": len(prs.slides),
        }

    return await asyncio.to_thread(_do_extract)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

_MIME_ROUTER: dict[str, Any] = {
    "application/pdf": _extract_pdf_with_gemini,
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": _extract_docx,
    "application/vnd.openxmlformats-officedocument.presentationml.presentation": _extract_pptx,
}


async def extract_document_text(
    file_bytes: bytes,
    file_name: str,
    mime_type: str,
) -> dict[str, Any]:
    """Extract text from an uploaded syllabus document.

    Args:
        file_bytes: Raw bytes of the uploaded file.
        file_name: Original filename (used for logging).
        mime_type: MIME type of the file.

    Returns:
        Dict with keys: text, method, page_count, and optionally error.
    """
    logger.info("Extracting text from '{}' ({})", file_name, mime_type)

    handler = _MIME_ROUTER.get(mime_type)
    if handler is None:
        return {
            "text": "",
            "method": "unsupported",
            "page_count": None,
            "error": f"Unsupported file type: {mime_type}",
        }

    return await handler(file_bytes)
