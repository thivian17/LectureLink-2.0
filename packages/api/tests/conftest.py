"""Shared test fixtures for the LectureLink API test suite."""

from __future__ import annotations

import pathlib
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import numpy as np
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


@pytest.fixture
def test_user():
    return {
        'id': '11111111-1111-1111-1111-111111111111',
        'email': 'student@university.edu',
    }

@pytest.fixture
def test_course(test_user):
    return {
        'id': '22222222-2222-2222-2222-222222222222',
        'user_id': test_user['id'],
        'name': 'PHYS 201 - Thermodynamics',
        'semester_start': '2026-01-12',
        'semester_end': '2026-04-24',
        'meeting_days': ['Monday', 'Wednesday', 'Friday'],
    }

@pytest.fixture
def test_lecture(test_course, test_user):
    return {
        'id': '33333333-3333-3333-3333-333333333333',
        'course_id': test_course['id'],
        'user_id': test_user['id'],
        'title': 'Lecture 1: Intro to Thermodynamics',
        'lecture_number': 1,
        'lecture_date': '2026-01-12',
        'processing_status': 'completed',
        'processing_stage': None,
        'processing_progress': 1.0,
        'duration_seconds': 3000,  # 50 minutes
        'summary': 'Introduction to thermodynamic systems, energy transfer, and the first law of thermodynamics.',
        'transcript': [
            {'start': 0.0, 'end': 15.5, 'text': 'Welcome to thermodynamics.', 'speaker': 'professor'},
            {'start': 15.5, 'end': 45.2, 'text': 'Today we will cover energy transfer.', 'speaker': 'professor'},
        ],
        'created_at': datetime.utcnow().isoformat(),
    }

@pytest.fixture
def test_chunks(test_lecture, test_user):
    """20 lecture chunks with mock 768-dim embeddings."""
    chunks = []
    for i in range(20):
        embedding = np.random.randn(768).tolist()
        # Normalize
        norm = np.linalg.norm(embedding)
        embedding = [x / norm for x in embedding]
        chunks.append({
            'id': f'chunk-{i:04d}-0000-0000-000000000000',
            'lecture_id': test_lecture['id'],
            'user_id': test_user['id'],
            'chunk_index': i,
            'content': f'Test chunk content {i}: This discusses thermodynamic concept number {i}.',
            'start_time': i * 150.0,  # ~2.5 min per chunk
            'end_time': (i + 1) * 150.0,
            'slide_number': (i // 4) + 1,  # 4 chunks per slide
            'embedding': embedding,
            'metadata': {'source': 'aligned'},
        })
    return chunks

@pytest.fixture
def test_concepts(test_lecture, test_course, test_user):
    """5 concepts linked to the test lecture."""
    concepts = [
        {'title': 'Thermodynamic System', 'description': 'A region of space defined by boundaries', 'category': 'definition', 'difficulty': 0.3},
        {'title': 'First Law of Thermodynamics', 'description': 'Energy cannot be created or destroyed', 'category': 'theorem', 'difficulty': 0.5},
        {'title': 'Heat Transfer', 'description': 'Movement of thermal energy between systems', 'category': 'process', 'difficulty': 0.4},
        {'title': 'Internal Energy', 'description': 'Total energy contained within a system', 'category': 'concept', 'difficulty': 0.5},
        {'title': 'Work-Energy Equivalence', 'description': 'Work and heat are equivalent forms of energy transfer', 'category': 'concept', 'difficulty': 0.6},
    ]
    result = []
    for i, c in enumerate(concepts):
        embedding = np.random.randn(768).tolist()
        norm = np.linalg.norm(embedding)
        embedding = [x / norm for x in embedding]
        result.append({
            'id': f'concept-{i:04d}-0000-0000-000000000000',
            'course_id': test_course['id'],
            'lecture_id': test_lecture['id'],
            'user_id': test_user['id'],
            'title': c['title'],
            'description': c['description'],
            'category': c['category'],
            'difficulty_estimate': c['difficulty'],
            'source_chunk_ids': [f'chunk-{i*4:04d}-0000-0000-000000000000'],
            'embedding': embedding,
        })
    return result

@pytest.fixture
def mock_supabase():
    """Mock Supabase client for unit tests."""
    client = MagicMock()
    client.table.return_value.select.return_value.eq.return_value.execute.return_value = MagicMock(
        data=[], count=0
    )
    client.table.return_value.insert.return_value.execute.return_value = MagicMock(
        data=[{'id': 'new-id'}]
    )
    client.table.return_value.update.return_value.eq.return_value.execute.return_value = MagicMock(
        data=[]
    )
    client.rpc.return_value.execute.return_value = MagicMock(
        data=[]
    )
    return client

@pytest.fixture
def mock_gemini_client():
    """Mock Gemini client that returns predictable responses."""
    client = MagicMock()
    
    # Mock embed_content
    mock_embedding = MagicMock()
    mock_embedding.values = np.random.randn(768).tolist()
    client.models.embed_content.return_value = MagicMock(
        embeddings=[mock_embedding]
    )
    
    # Mock generate_content
    client.models.generate_content.return_value = MagicMock(
        text='{"mock": "response"}'
    )

    return client


@pytest.fixture
def supabase_mock(mock_supabase):
    """Enhanced mock_supabase with in_() chain support for search enrichment."""
    mock_supabase.table.return_value.select.return_value.in_.return_value.execute.return_value = (
        MagicMock(data=[])
    )
    return mock_supabase


@pytest.fixture
def mock_genai():
    """Mock google-genai async client for embedding and RAG services.

    Patches the lazy ``_get_client()`` in both
    ``lecturelink_api.services.embedding`` and
    ``lecturelink_api.services.rag`` so unit tests never hit the
    real Gemini API.
    """
    mock_client = MagicMock()

    # --- aio.models.embed_content (async) ---
    def _embed_side_effect(*args, **kwargs):
        contents = kwargs.get("contents")
        if isinstance(contents, list):
            return MagicMock(
                embeddings=[MagicMock(values=[0.1] * 768) for _ in contents]
            )
        return MagicMock(embeddings=[MagicMock(values=[0.1] * 768)])

    mock_client.aio.models.embed_content = AsyncMock(side_effect=_embed_side_effect)

    # --- aio.models.generate_content (async) ---
    mock_client.aio.models.generate_content = AsyncMock(
        return_value=MagicMock(text='{"mock": "response"}')
    )

    with (
        patch(
            "lecturelink_api.services.embedding._get_client",
            return_value=mock_client,
        ),
        patch(
            "lecturelink_api.services.rag._get_client",
            return_value=mock_client,
        ),
    ):
        yield mock_client