"""Tests for the document text extraction tool."""

from __future__ import annotations

import io
from unittest.mock import MagicMock, patch

import pytest
from docx import Document
from pptx import Presentation
from pptx.util import Inches

from lecturelink_api.tools.document_tools import extract_document_text


# ---------------------------------------------------------------------------
# Helpers to build in-memory test fixtures
# ---------------------------------------------------------------------------

def _make_docx_bytes() -> bytes:
    """Create a minimal DOCX file in memory with headings, a paragraph, and a table."""
    doc = Document()
    doc.add_heading("Syllabus", level=1)
    doc.add_heading("Course Overview", level=2)
    doc.add_paragraph("This is the course description.")

    table = doc.add_table(rows=2, cols=2)
    table.cell(0, 0).text = "Week"
    table.cell(0, 1).text = "Topic"
    table.cell(1, 0).text = "1"
    table.cell(1, 1).text = "Introduction"

    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


def _make_pptx_bytes() -> bytes:
    """Create a minimal PPTX file in memory with a title slide and a content slide."""
    prs = Presentation()

    # Slide 1 — title slide
    slide_layout = prs.slide_layouts[0]  # title layout
    slide = prs.slides.add_slide(slide_layout)
    slide.shapes.title.text = "Lecture 1"
    slide.placeholders[1].text = "Welcome to the course"

    # Slide 2 — content with a table
    slide_layout2 = prs.slide_layouts[5]  # blank layout
    slide2 = prs.slides.add_slide(slide_layout2)
    txBox = slide2.shapes.add_textbox(Inches(1), Inches(1), Inches(4), Inches(1))
    txBox.text_frame.text = "Key concepts"

    # Add a table
    tbl = slide2.shapes.add_table(2, 2, Inches(1), Inches(2.5), Inches(4), Inches(1.5)).table
    tbl.cell(0, 0).text = "Term"
    tbl.cell(0, 1).text = "Definition"
    tbl.cell(1, 0).text = "API"
    tbl.cell(1, 1).text = "Application Programming Interface"

    # Add speaker notes to slide 2
    slide2.notes_slide.notes_text_frame.text = "Remember to explain APIs"

    buf = io.BytesIO()
    prs.save(buf)
    return buf.getvalue()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_docx_extraction():
    """DOCX extraction should capture headings, paragraphs, and tables."""
    docx_bytes = _make_docx_bytes()

    result = await extract_document_text(
        file_bytes=docx_bytes,
        file_name="syllabus.docx",
        mime_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )

    assert result["method"] == "docx"
    assert "error" not in result

    text = result["text"]
    assert "# Syllabus" in text
    assert "## Course Overview" in text
    assert "This is the course description." in text
    # Table rendered as markdown
    assert "| Week | Topic |" in text
    assert "| 1 | Introduction |" in text


@pytest.mark.asyncio
async def test_pptx_extraction():
    """PPTX extraction should capture slide titles, body text, tables, and notes."""
    pptx_bytes = _make_pptx_bytes()

    result = await extract_document_text(
        file_bytes=pptx_bytes,
        file_name="lecture.pptx",
        mime_type="application/vnd.openxmlformats-officedocument.presentationml.presentation",
    )

    assert result["method"] == "pptx"
    assert result["page_count"] == 2
    assert "error" not in result

    text = result["text"]
    assert "## Slide 1: Lecture 1" in text
    assert "Welcome to the course" in text
    assert "Key concepts" in text
    # Table
    assert "| Term | Definition |" in text
    assert "| API | Application Programming Interface |" in text
    # Speaker notes
    assert "Remember to explain APIs" in text


@pytest.mark.asyncio
async def test_unsupported_mime_type():
    """Unsupported MIME types should return an error dict, not raise."""
    result = await extract_document_text(
        file_bytes=b"not a real file",
        file_name="data.csv",
        mime_type="text/csv",
    )

    assert result["method"] == "unsupported"
    assert result["text"] == ""
    assert "error" in result
    assert "Unsupported file type" in result["error"]


@pytest.mark.asyncio
async def test_pdf_extraction_calls_gemini():
    """PDF extraction should call Gemini and return the response text."""
    mock_response = MagicMock()
    mock_response.text = "Extracted syllabus content from PDF"

    mock_client = MagicMock()
    mock_client.models.generate_content.return_value = mock_response

    with patch("lecturelink_api.tools.document_tools.genai.Client", return_value=mock_client):
        result = await extract_document_text(
            file_bytes=b"%PDF-1.4 fake pdf content",
            file_name="syllabus.pdf",
            mime_type="application/pdf",
        )

    assert result["method"] == "gemini-pdf"
    assert result["text"] == "Extracted syllabus content from PDF"
    assert "error" not in result

    # Verify the Gemini client was called with the right model
    call_kwargs = mock_client.models.generate_content.call_args
    assert call_kwargs.kwargs["model"] == "gemini-2.5-flash"


@pytest.mark.asyncio
async def test_pdf_extraction_handles_gemini_error():
    """If Gemini fails, we should get an error dict instead of an exception."""
    mock_client = MagicMock()
    mock_client.models.generate_content.side_effect = RuntimeError("API quota exceeded")

    with patch("lecturelink_api.tools.document_tools.genai.Client", return_value=mock_client):
        result = await extract_document_text(
            file_bytes=b"%PDF-1.4 fake pdf content",
            file_name="syllabus.pdf",
            mime_type="application/pdf",
        )

    assert result["method"] == "gemini-pdf"
    assert result["text"] == ""
    assert "error" in result
    assert "API quota exceeded" in result["error"]
