"""Full end-to-end test with real Gemini and real Supabase.

Requires:
  Gemini auth      - Either GOOGLE_API_KEY env var or gcloud ADC
  SUPABASE_URL     - Project URL (or set in packages/api/.env)
  SUPABASE_ANON_KEY - Public anon key (or set in packages/api/.env)
  TEST_USER_EMAIL    - Test account email
  TEST_USER_PASSWORD - Test account password

Run with:
  cd packages/api
  python -m pytest tests/integration/test_full_e2e.py -v -m live -s
"""

from __future__ import annotations

import asyncio
import os
import shutil
import subprocess
import time
import uuid
from pathlib import Path

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from lecturelink_api.main import app
from supabase import create_client

from tests.integration.fixtures.syllabus_generator import ALL_SYLLABI
from tests.integration.metrics.accuracy import compute_accuracy
from tests.integration.metrics.reporter import MetricsReporter

pytestmark = [pytest.mark.live, pytest.mark.slow]

# ---------------------------------------------------------------------------
# Skip if credentials are missing
# ---------------------------------------------------------------------------


def _has_gemini_auth() -> bool:
    """Check if Gemini auth is available via API key or ADC."""
    if os.getenv("GOOGLE_API_KEY"):
        return True
    # Check for gcloud ADC
    gcloud = shutil.which("gcloud")
    if gcloud:
        try:
            result = subprocess.run(
                [gcloud, "auth", "application-default", "print-access-token"],
                capture_output=True, text=True, timeout=10,
            )
            return result.returncode == 0 and result.stdout.strip().startswith("ya29")
        except Exception:
            pass
    return False


_REQUIRED_ENV = [
    "SUPABASE_URL",
    "SUPABASE_ANON_KEY",
    "TEST_USER_EMAIL",
    "TEST_USER_PASSWORD",
]


def _missing_env() -> list[str]:
    missing = [k for k in _REQUIRED_ENV if not os.getenv(k)]
    if not _has_gemini_auth():
        missing.append("GOOGLE_API_KEY or gcloud ADC")
    return missing


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def _check_credentials():
    missing = _missing_env()
    if missing:
        pytest.skip(f"Missing env vars for live E2E: {', '.join(missing)}")


@pytest.fixture(scope="module")
def supabase_client(_check_credentials):
    """Create authenticated Supabase client with test credentials."""
    url = os.environ["SUPABASE_URL"]
    key = os.environ["SUPABASE_ANON_KEY"]
    client = create_client(url, key)
    auth_resp = client.auth.sign_in_with_password(
        {
            "email": os.environ["TEST_USER_EMAIL"],
            "password": os.environ["TEST_USER_PASSWORD"],
        }
    )
    return client


@pytest.fixture(scope="module")
def auth_token(supabase_client) -> str:
    session = supabase_client.auth.get_session()
    return session.access_token


@pytest_asyncio.fixture()
async def live_client(auth_token):
    """AsyncClient pointing at the real FastAPI app with real auth."""
    from lecturelink_api.config import Settings, get_settings

    # Override settings with real env vars
    real_settings = Settings(
        SUPABASE_URL=os.environ["SUPABASE_URL"],
        SUPABASE_ANON_KEY=os.environ["SUPABASE_ANON_KEY"],
    )
    app.dependency_overrides[get_settings] = lambda: real_settings
    # Don't override auth — let real JWT validation happen

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        ac.headers["Authorization"] = f"Bearer {auth_token}"
        yield ac

    app.dependency_overrides.pop(get_settings, None)


@pytest.fixture(scope="module")
def reporter():
    r = MetricsReporter()
    yield r
    # Write report after all tests in this module
    report_path = Path(__file__).parent.parent.parent / "test_metrics_report.json"
    r.write_report(report_path)


# ---------------------------------------------------------------------------
# Test course prefix for cleanup
# ---------------------------------------------------------------------------

TEST_PREFIX = f"[E2E-{uuid.uuid4().hex[:6]}]"


@pytest.fixture()
def cleanup_course(supabase_client):
    """Track course IDs for cleanup after test."""
    course_ids = []
    yield course_ids
    for cid in course_ids:
        try:
            supabase_client.table("courses").delete().eq("id", cid).execute()
        except Exception:
            pass  # best-effort cleanup


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _create_course(client, name_suffix: str) -> dict:
    resp = await client.post(
        "/api/courses",
        json={
            "name": f"{TEST_PREFIX} {name_suffix}",
            "code": name_suffix.split(":")[0] if ":" in name_suffix else None,
            "semester_start": "2026-01-12",
            "semester_end": "2026-05-01",
            "meeting_days": ["Tuesday", "Thursday"],
            "target_grade": 0.8,
        },
    )
    assert resp.status_code == 201, f"Course creation failed: {resp.text}"
    return resp.json()


async def _poll_status(
    client, syllabus_id: str, timeout: float = 300.0
) -> str:
    """Poll syllabus status until complete/error or timeout."""
    start = time.monotonic()
    while time.monotonic() - start < timeout:
        resp = await client.get(f"/api/syllabi/{syllabus_id}/status")
        assert resp.status_code == 200
        status = resp.json()["status"]
        if status in ("complete", "error"):
            return status
        await asyncio.sleep(2.0)
    return "timeout"


# ---------------------------------------------------------------------------
# Live E2E tests — one per syllabus type
# ---------------------------------------------------------------------------


class TestLiveE2E:
    """Full pipeline with real Gemini for each test syllabus."""

    @pytest.mark.live
    @pytest.mark.asyncio
    async def test_stem_syllabus(self, live_client, reporter, cleanup_course):
        await self._run_syllabus_e2e(
            live_client, reporter, cleanup_course, "stem", "PHYS 201: Thermodynamics"
        )

    @pytest.mark.live
    @pytest.mark.asyncio
    async def test_business_syllabus(self, live_client, reporter, cleanup_course):
        await self._run_syllabus_e2e(
            live_client, reporter, cleanup_course, "business", "BUS 301: Strategic Mgmt"
        )

    @pytest.mark.live
    @pytest.mark.asyncio
    async def test_minimal_syllabus(self, live_client, reporter, cleanup_course):
        await self._run_syllabus_e2e(
            live_client, reporter, cleanup_course, "minimal", "ENG 102: Composition"
        )

    @pytest.mark.live
    @pytest.mark.asyncio
    async def test_week_format_syllabus(self, live_client, reporter, cleanup_course):
        await self._run_syllabus_e2e(
            live_client, reporter, cleanup_course, "week_format", "CS 340: Algorithms"
        )

    @pytest.mark.live
    @pytest.mark.asyncio
    async def test_docx_syllabus(self, live_client, reporter, cleanup_course):
        await self._run_syllabus_e2e(
            live_client, reporter, cleanup_course, "docx", "HIST 215: World History"
        )

    async def _run_syllabus_e2e(
        self,
        client,
        reporter: MetricsReporter,
        cleanup_course: list,
        syllabus_key: str,
        course_name: str,
    ):
        """Run full E2E for a single syllabus type."""
        # Generate test document
        builder = ALL_SYLLABI[syllabus_key]
        file_bytes, mime_type, ground_truth = builder()
        ext = "docx" if "wordprocessing" in mime_type else "pdf"
        filename = f"test_{syllabus_key}.{ext}"

        # 1. Create course
        course = await _create_course(client, course_name)
        cleanup_course.append(course["id"])

        # 2. Upload syllabus
        start_time = time.monotonic()
        upload_resp = await client.post(
            "/api/syllabi/upload",
            data={"course_id": course["id"]},
            files={"file": (filename, file_bytes, mime_type)},
        )
        assert upload_resp.status_code == 201, (
            f"Upload failed for {syllabus_key}: {upload_resp.text}"
        )
        syllabus_id = upload_resp.json()["syllabus_id"]

        # 3. Poll for completion
        final_status = await _poll_status(client, syllabus_id, timeout=300)
        processing_time = time.monotonic() - start_time
        assert final_status == "complete", (
            f"Processing {syllabus_key} ended with status={final_status}"
        )

        # 4. Fetch extraction
        syl_resp = await client.get(f"/api/syllabi/{syllabus_id}")
        assert syl_resp.status_code == 200
        extraction = syl_resp.json().get("raw_extraction", {})

        # 5. Compute accuracy
        accuracy = compute_accuracy(extraction, ground_truth)
        reporter.record(syllabus_key, accuracy, processing_time)

        # 6. Assertions against target metrics
        assert accuracy.field_accuracy >= 0.70, (
            f"[{syllabus_key}] Field accuracy {accuracy.field_accuracy:.0%} "
            f"({accuracy.fields_correct}/{accuracy.fields_checked}) below 70%"
        )
        if ground_truth.get("date_count", 0) > 0:
            assert accuracy.date_accuracy >= 0.90, (
                f"[{syllabus_key}] Date accuracy {accuracy.date_accuracy:.0%} "
                f"({accuracy.dates_correct}/{accuracy.dates_checked}) below 90%"
            )
        # Multi-agent pipeline: PDF extraction + 3 parallel LLM calls + validation
        assert processing_time < 300, (
            f"[{syllabus_key}] Processing took {processing_time:.1f}s (>300s)"
        )

        # 7. Verify assessments populated
        assess_resp = await client.get(
            f"/api/courses/{course['id']}/assessments"
        )
        assert assess_resp.status_code == 200
        assessments = assess_resp.json()
        assert len(assessments) > 0, (
            f"[{syllabus_key}] No assessments created"
        )


# ---------------------------------------------------------------------------
# Priority scoring with real data
# ---------------------------------------------------------------------------


class TestLivePriorityScoring:
    """Validate priority scoring with real extracted data."""

    @pytest.mark.live
    @pytest.mark.asyncio
    async def test_priorities_ordered_correctly(
        self, live_client, cleanup_course
    ):
        """After processing a syllabus, priorities are ranked logically."""
        builder = ALL_SYLLABI["stem"]
        file_bytes, mime_type, _ = builder()

        course = await _create_course(live_client, "PHYS 201: Priority Test")
        cleanup_course.append(course["id"])

        # Upload and wait for processing
        resp = await live_client.post(
            "/api/syllabi/upload",
            data={"course_id": course["id"]},
            files={"file": ("test.pdf", file_bytes, mime_type)},
        )
        assert resp.status_code == 201
        sid = resp.json()["syllabus_id"]

        status = await _poll_status(live_client, sid, timeout=300)
        assert status == "complete"

        # Get priorities
        prio_resp = await live_client.get(
            f"/api/courses/{course['id']}/assessments/priorities"
        )
        assert prio_resp.status_code == 200
        priorities = prio_resp.json()

        if len(priorities) >= 2:
            # Verify descending order
            scores = [p["priority_score"] for p in priorities]
            assert scores == sorted(scores, reverse=True), (
                f"Priorities not in descending order: {scores}"
            )
