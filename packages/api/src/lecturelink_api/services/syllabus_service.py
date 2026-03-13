"""Orchestrates the full syllabus processing flow.

Fetches semester context, runs the multi-agent pipeline, post-processes
the result, and persists extraction data to Supabase.
"""

from __future__ import annotations

import asyncio
import json
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import date

from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types as genai_types
from loguru import logger
from supabase import Client as SupabaseClient

from lecturelink_api.agents.syllabus_processor import (
    extraction_pipeline,
    merge_extraction_outputs,
    post_process_extraction,
)
from lecturelink_api.models.syllabus_models import (
    SyllabusExtraction,
    extraction_to_db_assessments,
)
from lecturelink_api.tools.date_resolver import (
    SemesterContext,
    resolve_all_dates,
)
from lecturelink_api.tools.document_tools import extract_document_text


def _build_semester_context(ctx: dict) -> SemesterContext | None:
    """Build a SemesterContext from the courses table row, or None if dates are missing."""
    start_str = ctx.get("semester_start")
    end_str = ctx.get("semester_end")
    if not start_str or not end_str:
        return None

    try:
        start = date.fromisoformat(str(start_str))
        end = date.fromisoformat(str(end_str))
    except (ValueError, TypeError):
        logger.warning("Invalid semester dates: start={}, end={}", start_str, end_str)
        return None

    meeting_days = ctx.get("meeting_days") or []
    # Normalize to lowercase
    meeting_days = [d.lower() for d in meeting_days]

    # Normalize holiday keys: DB stores start_date/end_date, resolver expects start/end
    raw_holidays = ctx.get("holidays") or []
    holidays = []
    for h in raw_holidays:
        holidays.append({
            "name": h.get("name", "Holiday"),
            "start": h.get("start") or h.get("start_date", ""),
            "end": h.get("end") or h.get("end_date", ""),
        })

    return SemesterContext(
        start=start,
        end=end,
        meeting_days=meeting_days,
        holidays=holidays,
    )


async def _fetch_semester_context(
    supabase: SupabaseClient,
    course_id: str,
) -> dict:
    """Fetch semester boundaries and schedule info from the courses table."""
    result = (
        supabase.table("courses")
        .select("semester_start, semester_end, meeting_days, holidays")
        .eq("id", course_id)
        .single()
        .execute()
    )
    return result.data or {}


_pipeline_executor = ThreadPoolExecutor(max_workers=2)


def _run_adk_pipeline_sync(raw_text: str, semester_context: dict, file_name: str) -> dict:
    """Run the ADK pipeline synchronously in a thread with a clean event loop.

    On Windows, uvicorn uses SelectorEventLoop which doesn't support SSL/TLS
    properly for async httpx connections. This creates a fresh ProactorEventLoop
    (on Windows) to run the ADK pipeline reliably.
    """
    if sys.platform == "win32":
        loop = asyncio.ProactorEventLoop()
    else:
        loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(
            _run_adk_pipeline_async(raw_text, semester_context, file_name)
        )
    finally:
        loop.close()


async def _run_adk_pipeline_async(
    raw_text: str, semester_context: dict, file_name: str
) -> dict:
    """The actual async ADK pipeline execution."""
    session_service = InMemorySessionService()
    runner = Runner(
        agent=extraction_pipeline,
        app_name="lecturelink_syllabus",
        session_service=session_service,
    )

    session = await session_service.create_session(
        app_name="lecturelink_syllabus",
        user_id="system",
        state={
            "raw_text": raw_text,
            "semester_context": json.dumps(semester_context),
        },
    )

    user_message = genai_types.Content(
        role="user",
        parts=[
            genai_types.Part(
                text=f"Extract structured data from this syllabus: {file_name}"
            ),
        ],
    )

    # Run the pipeline to completion
    async for _event in runner.run_async(
        session_id=session.id,
        user_id="system",
        new_message=user_message,
    ):
        pass

    # Retrieve individual extractor outputs from session state and merge
    final_session = await session_service.get_session(
        app_name="lecturelink_syllabus",
        user_id="system",
        session_id=session.id,
    )
    schedule_data = final_session.state.get("schedule_data")
    grading_data = final_session.state.get("grading_data")
    info_data = final_session.state.get("info_data")

    return merge_extraction_outputs(schedule_data, grading_data, info_data)


async def _run_agent_pipeline(
    file_bytes: bytes,
    file_name: str,
    mime_type: str,
    semester_context: dict,
) -> dict:
    """Run the multi-agent syllabus processor and return raw extraction dict.

    Text extraction is done deterministically before the LLM pipeline.
    The extraction_pipeline (parallel extractors + validation loop) then
    operates on the pre-extracted text via session state.
    """
    # Step 1: Extract text deterministically (no LLM needed for routing)
    logger.info("Extracting text from '{}' ({})", file_name, mime_type)
    extraction_result = await extract_document_text(file_bytes, file_name, mime_type)
    raw_text = extraction_result.get("text", "")
    if not raw_text:
        raise ValueError(
            f"Document text extraction returned empty text for {file_name}: "
            f"{extraction_result.get('error', 'unknown error')}"
        )
    logger.info(
        "Extracted {} chars via {} from '{}'",
        len(raw_text), extraction_result.get("method"), file_name,
    )

    # Step 2: Run the LLM extraction pipeline with pre-extracted text.
    # On Windows, uvicorn uses SelectorEventLoop which has broken SSL/TLS
    # for async connections. Run the ADK pipeline in a thread with its own
    # ProactorEventLoop to avoid this issue.
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(
        _pipeline_executor,
        _run_adk_pipeline_sync,
        raw_text,
        semester_context,
        file_name,
    )


async def process_syllabus(
    syllabus_id: str,
    file_bytes: bytes,
    file_name: str,
    mime_type: str,
    course_id: str,
    user_id: str,
    supabase: SupabaseClient,
) -> SyllabusExtraction:
    """Orchestrate the full syllabus processing flow.

    1. Fetches semester context from courses table
    2. Runs the multi-agent extraction pipeline
    3. Post-processes the result with deterministic validation
    4. Runs date resolution on all assessments
    5. Saves raw_extraction, grade_breakdown, extraction_confidence to syllabi table
    6. Sets needs_review=true on the syllabus
    7. Populates assessments table with denormalized rows

    Args:
        syllabus_id: ID of the syllabus record (already created).
        file_bytes: Raw bytes of the uploaded document.
        file_name: Original filename.
        mime_type: MIME type of the document.
        course_id: ID of the course this syllabus belongs to.
        user_id: ID of the user who uploaded the syllabus.
        supabase: Authenticated Supabase client.

    Returns:
        The post-processed SyllabusExtraction.
    """
    logger.info(
        "Processing syllabus {} for course {} (user {})",
        syllabus_id, course_id, user_id,
    )

    try:
        # 1. Fetch semester context
        semester_context = await _fetch_semester_context(supabase, course_id)

        # 2. Run the agent pipeline
        raw_result = await _run_agent_pipeline(
            file_bytes=file_bytes,
            file_name=file_name,
            mime_type=mime_type,
            semester_context=semester_context,
        )

        # 3. Post-process: patch structural issues, validate grade weights
        extraction = post_process_extraction(raw_result, semester_context)

        # 4. Run date resolution on all assessments
        sem_ctx = _build_semester_context(semester_context)
        if sem_ctx is not None:
            extraction.assessments = resolve_all_dates(extraction.assessments, sem_ctx)
            logger.info(
                "Resolved dates for {} assessments", len(extraction.assessments)
            )

        # 5. Finalize: compute confidence, validate dates, flag low-confidence
        #    (runs AFTER date resolution so it uses final resolved values)
        from lecturelink_api.agents.syllabus_processor import finalize_extraction

        extraction = finalize_extraction(extraction, semester_context)

        # 6. Save to syllabi table
        grade_breakdown_dicts = [
            comp.model_dump(mode="json") for comp in extraction.grade_breakdown
        ]
        supabase.table("syllabi").update(
            {
                "raw_extraction": extraction.model_dump(mode="json"),
                "grade_breakdown": grade_breakdown_dicts,
                "extraction_confidence": extraction.extraction_confidence,
                "needs_review": True,
                "status": "processed",
            }
        ).eq("id", syllabus_id).execute()

        # 7. Populate assessments table
        assessment_rows = extraction_to_db_assessments(
            extraction, course_id, syllabus_id
        )
        if assessment_rows:
            supabase.table("assessments").insert(assessment_rows).execute()
            logger.info(
                "Inserted {} assessments for syllabus {}",
                len(assessment_rows), syllabus_id,
            )

        return extraction

    except Exception:
        logger.exception(
            "Syllabus processing failed for syllabus_id={}", syllabus_id
        )
        # Save failure state so the UI knows extraction failed
        supabase.table("syllabi").update(
            {
                "extraction_confidence": 0.0,
                "raw_extraction": {"error": "Extraction failed", "syllabus_id": syllabus_id},
                "needs_review": True,
                "status": "error",
            }
        ).eq("id", syllabus_id).execute()
        raise


async def update_assessment_from_review(
    assessment_id: str,
    updates: dict,
    supabase: SupabaseClient,
) -> dict:
    """Apply manual corrections from the review UI to a single assessment.

    Args:
        assessment_id: The assessment row ID.
        updates: Dict of fields to update (title, type, due_date, etc.).
        supabase: Authenticated Supabase client.

    Returns:
        The updated assessment row as a dict.
    """
    logger.info("Updating assessment {} from review: {}", assessment_id, list(updates.keys()))

    # If a date was manually corrected, clear the ambiguous flag
    if "due_date" in updates and updates["due_date"] is not None:
        updates["is_date_ambiguous"] = False

    result = (
        supabase.table("assessments")
        .update(updates)
        .eq("id", assessment_id)
        .execute()
    )

    if not result.data:
        logger.error("Assessment {} not found for review update", assessment_id)
        raise ValueError(f"Assessment {assessment_id} not found")

    return result.data[0]


async def accept_syllabus_review(
    syllabus_id: str,
    supabase: SupabaseClient,
) -> dict:
    """Accept all extractions for a syllabus, marking review as complete.

    Sets needs_review=false and reviewed_at=now() on the syllabus row.

    Args:
        syllabus_id: The syllabus row ID.
        supabase: Authenticated Supabase client.

    Returns:
        Dict with syllabus_id and assessment_count.
    """
    logger.info("Accepting review for syllabus {}", syllabus_id)

    # Mark syllabus as reviewed
    supabase.table("syllabi").update(
        {
            "needs_review": False,
            "reviewed_at": "now()",
        }
    ).eq("id", syllabus_id).execute()

    # Count assessments for this syllabus
    count_result = (
        supabase.table("assessments")
        .select("id", count="exact")
        .eq("syllabus_id", syllabus_id)
        .execute()
    )
    assessment_count = len(count_result.data) if count_result.data else 0

    logger.info(
        "Syllabus {} review accepted with {} assessments",
        syllabus_id, assessment_count,
    )

    return {
        "syllabus_id": syllabus_id,
        "assessment_count": assessment_count,
    }
