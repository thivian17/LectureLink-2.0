"""Shared test fixtures for the LectureLink API test suite."""

from __future__ import annotations

import pathlib

import pytest

FIXTURES_DIR = pathlib.Path(__file__).parent / "fixtures"


# ---------------------------------------------------------------------------
# Minimal PDF generator (pure Python, no external deps)
# ---------------------------------------------------------------------------


def _build_sample_syllabus_pdf() -> bytes:
    """Build a minimal valid PDF containing sample syllabus text.

    Produces a single-page PDF with Helvetica text that most PDF readers
    (and Gemini's multimodal endpoint) can parse.
    """
    text_lines = [
        "CS 101 - Introduction to Computer Science",
        "Fall 2025 Syllabus",
        "",
        "Instructor: Dr. Jane Smith",
        "Email: jsmith@university.edu",
        "Office Hours: Mon/Wed 2-3pm, Room 301",
        "",
        "Grade Breakdown:",
        "  Midterm Exams: 30%",
        "  Final Exam: 35%",
        "  Homework: 25% - lowest score dropped",
        "  Participation: 10%",
        "",
        "Course Schedule:",
        "  Week 1 - Aug 25-29: Course overview, Intro to Python",
        "  Week 2 - Sep 1-5: Variables and Data Types",
        "  Week 3 - Sep 8-12: Control Flow",
        "",
        "Assessments:",
        "  Midterm 1 - October 10 - Chapters 1-5 - 15%",
        "  Final Exam - December 15 - Chapters 1-12 - 35%",
        "  Homework 1 - Sep 10 - Chapter 1 - 5%",
        "",
        "Late Policy: 10% penalty per day, max 3 days",
        "Academic Integrity: Zero tolerance for plagiarism",
    ]

    # PDF text operators: BT/ET = begin/end text block
    # Tf = set font, Td = move cursor, TL = set leading, ' = newline + show
    ops = ["BT", "/F1 10 Tf", "72 750 Td", "12 TL"]
    for line in text_lines:
        escaped = line.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
        ops.append(f"({escaped}) '")
    ops.append("ET")
    stream = "\n".join(ops).encode("latin-1")

    # Build five PDF indirect objects
    obj1 = b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n"
    obj2 = b"2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n"
    obj3 = (
        b"3 0 obj\n"
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792]\n"
        b"   /Contents 4 0 R\n"
        b"   /Resources << /Font << /F1 5 0 R >> >> >>\n"
        b"endobj\n"
    )
    obj4 = (
        f"4 0 obj\n<< /Length {len(stream)} >>\nstream\n".encode()
        + stream
        + b"\nendstream\nendobj\n"
    )
    obj5 = b"5 0 obj\n<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>\nendobj\n"

    objects = [obj1, obj2, obj3, obj4, obj5]

    header = b"%PDF-1.4\n"

    # Compute byte offsets for the cross-reference table
    offsets: list[int] = []
    pos = len(header)
    for obj in objects:
        offsets.append(pos)
        pos += len(obj)

    xref_start = pos

    xref = b"xref\n"
    xref += f"0 {len(objects) + 1}\n".encode()
    xref += b"0000000000 65535 f \n"
    for offset in offsets:
        xref += f"{offset:010d} 00000 n \n".encode()

    trailer = (
        f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\n"
        f"startxref\n{xref_start}\n%%EOF\n"
    ).encode()

    return header + b"".join(objects) + xref + trailer


# ---------------------------------------------------------------------------
# Session-scoped fixture: generate sample PDF once per test run
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session", autouse=True)
def _ensure_fixtures():
    """Create test fixture files if they don't already exist."""
    FIXTURES_DIR.mkdir(exist_ok=True)

    pdf_path = FIXTURES_DIR / "sample_syllabus.pdf"
    if not pdf_path.exists():
        pdf_path.write_bytes(_build_sample_syllabus_pdf())
