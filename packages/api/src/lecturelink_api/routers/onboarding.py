"""Onboarding flow endpoints for guided course setup."""

from __future__ import annotations

import logging
from datetime import date, datetime

from fastapi import APIRouter, Depends, HTTPException, status
from lecturelink_api.auth import get_authenticated_supabase, get_current_user
from lecturelink_api.config import Settings, get_settings
from lecturelink_api.models.api_models import (
    FileMatchRequest,
    FileMatchResponse,
    FileMatchResult,
    LectureChecklistAdd,
    LectureChecklistItem,
    LectureChecklistUpdate,
    OnboardingCompleteResponse,
    OnboardingStartResponse,
    OnboardingStatusResponse,
    PersonalizedMessageRequest,
    PersonalizedMessageResponse,
    SemesterProgressResponse,
    SetPathRequest,
    SetPathResponse,
    StepUpdateRequest,
)
from lecturelink_api.services.onboarding import (
    _parse_due_date,
    generate_lecture_checklist,
    generate_personalized_message,
    get_semester_progress,
    seed_mastery_from_scores,
    suggest_onboarding_path,
)


logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/courses/{course_id}", tags=["onboarding"])

VALID_STEPS = {
    "syllabus_upload",
    "extraction_review",
    "path_selection",
    "personalized_message",
    "lecture_catchup",
    "past_results",
    "study_plan",
    "material_upload",
    "practice_intro",
}




def _get_course(sb, course_id: str, user_id: str) -> dict:
    """Fetch course and verify ownership."""
    result = (
        sb.table("courses")
        .select("*")
        .eq("id", course_id)
        .eq("user_id", user_id)
        .execute()
    )
    if not result.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Course not found",
        )
    return result.data[0]


# -----------------------------------------------------------------------
# POST /api/courses/{course_id}/onboarding/start
# -----------------------------------------------------------------------


@router.post(
    "/onboarding/start",
    response_model=OnboardingStartResponse,
    status_code=status.HTTP_201_CREATED,
)
async def start_onboarding(
    course_id: str,
    user: dict = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
):
    sb = get_authenticated_supabase(user, settings)
    course = _get_course(sb, course_id, user["id"])

    if course.get("onboarding_completed_at"):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Onboarding already completed for this course",
        )

    sb.table("courses").update({
        "onboarding_step": "syllabus_upload",
    }).eq("id", course_id).execute()

    # Create user_onboarding record if it doesn't exist
    existing = (
        sb.table("user_onboarding")
        .select("user_id")
        .eq("user_id", user["id"])
        .execute()
    )
    if not existing.data:
        sb.table("user_onboarding").insert({
            "user_id": user["id"],
            "has_seen_welcome": False,
            "first_course_created_at": datetime.utcnow().isoformat(),
        }).execute()

    return {"status": "started", "step": "syllabus_upload"}


# -----------------------------------------------------------------------
# GET /api/courses/{course_id}/onboarding/status
# -----------------------------------------------------------------------


@router.get(
    "/onboarding/status",
    response_model=OnboardingStatusResponse,
)
async def get_onboarding_status(
    course_id: str,
    user: dict = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
):
    sb = get_authenticated_supabase(user, settings)
    course = _get_course(sb, course_id, user["id"])

    completed = course.get("onboarding_completed_at")
    return {
        "path": course.get("onboarding_path"),
        "step": course.get("onboarding_step"),
        "completed_at": completed if completed else None,
        "welcome_message": course.get("onboarding_welcome"),
    }


# -----------------------------------------------------------------------
# PUT /api/courses/{course_id}/onboarding/step
# -----------------------------------------------------------------------


@router.put("/onboarding/step")
async def update_step(
    course_id: str,
    body: StepUpdateRequest,
    user: dict = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
):
    if body.step not in VALID_STEPS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid step. Must be one of: {', '.join(sorted(VALID_STEPS))}",
        )

    sb = get_authenticated_supabase(user, settings)
    _get_course(sb, course_id, user["id"])

    # Update and read back in a single query via .select() on update
    update_result = (
        sb.table("courses")
        .update({"onboarding_step": body.step})
        .eq("id", course_id)
        .execute()
    )
    course = update_result.data[0] if update_result.data else _get_course(sb, course_id, user["id"])
    completed = course.get("onboarding_completed_at")
    return {
        "path": course.get("onboarding_path"),
        "step": course.get("onboarding_step"),
        "completed_at": completed if completed else None,
        "welcome_message": course.get("onboarding_welcome"),
    }


# -----------------------------------------------------------------------
# GET /api/courses/{course_id}/onboarding/suggest-path
# -----------------------------------------------------------------------


@router.get("/onboarding/suggest-path")
async def get_suggested_path(
    course_id: str,
    user: dict = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
):
    sb = get_authenticated_supabase(user, settings)
    course = _get_course(sb, course_id, user["id"])

    suggested = suggest_onboarding_path(
        course.get("semester_start"),
        course.get("semester_end"),
    )
    progress = get_semester_progress(course)

    return {
        "suggested_path": suggested,
        "progress_pct": progress["progress_pct"],
    }


# -----------------------------------------------------------------------
# POST /api/courses/{course_id}/onboarding/set-path
# -----------------------------------------------------------------------


@router.post("/onboarding/set-path", response_model=SetPathResponse)
async def set_path(
    course_id: str,
    body: SetPathRequest,
    user: dict = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
):
    sb = get_authenticated_supabase(user, settings)
    course = _get_course(sb, course_id, user["id"])

    update_payload: dict = {"onboarding_path": body.path}
    if body.path == "course_complete":
        update_payload["mode"] = "review"

    sb.table("courses").update(update_payload).eq("id", course_id).execute()

    suggested = suggest_onboarding_path(
        course.get("semester_start"),
        course.get("semester_end"),
    )

    mode = update_payload.get("mode", course.get("mode", "active"))
    return {"path": body.path, "mode": mode, "suggested_path": suggested}


# -----------------------------------------------------------------------
# POST /api/courses/{course_id}/onboarding/personalized-message
# -----------------------------------------------------------------------


@router.post(
    "/onboarding/personalized-message",
    response_model=PersonalizedMessageResponse,
)
async def get_personalized_message(
    course_id: str,
    body: PersonalizedMessageRequest | None = None,
    user: dict = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
):
    sb = get_authenticated_supabase(user, settings)
    course = _get_course(sb, course_id, user["id"])

    force = body.force_regenerate if body else False
    cached = course.get("onboarding_welcome")
    current_path = course.get("onboarding_path") or "mid_semester"

    if cached and not force and cached.get("path") == current_path:
        return cached

    # Fetch assessments
    assessments_result = (
        sb.table("assessments")
        .select("*")
        .eq("course_id", course_id)
        .order("due_date")
        .execute()
    )
    assessments = assessments_result.data or []

    progress = get_semester_progress(course)

    # Get student name from profiles table
    student_name = None
    try:
        profile_result = (
            sb.table("profiles")
            .select("first_name")
            .eq("id", user["id"])
            .execute()
        )
        if profile_result.data:
            student_name = profile_result.data[0].get("first_name")
    except Exception:
        logger.debug("Failed to fetch student name for onboarding", exc_info=True)

    message = await generate_personalized_message(
        course=course,
        assessments=assessments,
        onboarding_path=current_path,
        semester_progress=progress,
        student_name=student_name,
    )

    now = datetime.utcnow().isoformat()
    welcome_data = {
        "message": message,
        "generated_at": now,
        "path": current_path,
    }

    sb.table("courses").update({
        "onboarding_welcome": welcome_data,
    }).eq("id", course_id).execute()

    return welcome_data


# -----------------------------------------------------------------------
# GET /api/courses/{course_id}/onboarding/lecture-checklist
# -----------------------------------------------------------------------


@router.get(
    "/onboarding/lecture-checklist",
    response_model=list[LectureChecklistItem],
)
async def get_lecture_checklist(
    course_id: str,
    user: dict = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
):
    sb = get_authenticated_supabase(user, settings)
    course = _get_course(sb, course_id, user["id"])

    # Try to get weekly schedule from syllabus
    weekly_schedule = None
    syllabus_result = (
        sb.table("syllabi")
        .select("raw_extraction")
        .eq("course_id", course_id)
        .order("created_at", desc=True)
        .limit(1)
        .execute()
    )
    if syllabus_result.data:
        extraction = syllabus_result.data[0].get("raw_extraction") or {}
        weekly_schedule = extraction.get("weekly_schedule")

    holidays = course.get("holidays")

    checklist = generate_lecture_checklist(
        course=course,
        syllabus_weekly_schedule=weekly_schedule,
        holidays=holidays,
    )

    # Merge in user-added lectures
    additions = (
        sb.table("lecture_schedule_corrections")
        .select("*")
        .eq("course_id", course_id)
        .eq("user_id", user["id"])
        .eq("is_addition", True)
        .execute()
    )
    for row in additions.data or []:
        checklist.append({
            "lecture_number": row["original_lecture_number"],
            "expected_date": row["corrected_date"] or "",
            "week_number": 0,
            "topic_hint": row.get("corrected_title") or row.get("corrected_description"),
            "day_of_week": "",
            "status": "pending",
            "is_user_added": True,
        })

    # Apply corrections to auto-generated items
    edits = (
        sb.table("lecture_schedule_corrections")
        .select("*")
        .eq("course_id", course_id)
        .eq("user_id", user["id"])
        .eq("is_addition", False)
        .execute()
    )
    corrections_by_num = {
        row["original_lecture_number"]: row for row in (edits.data or [])
    }
    for item in checklist:
        correction = corrections_by_num.get(item["lecture_number"])
        if correction:
            if correction.get("corrected_date"):
                item["expected_date"] = correction["corrected_date"]
            if correction.get("corrected_title") or correction.get("corrected_description"):
                item["topic_hint"] = (
                    correction.get("corrected_title")
                    or correction.get("corrected_description")
                    or item.get("topic_hint")
                )

    checklist.sort(key=lambda x: x["lecture_number"])

    return checklist


# -----------------------------------------------------------------------
# POST /api/courses/{course_id}/onboarding/match-files
# -----------------------------------------------------------------------


@router.post(
    "/onboarding/match-files",
    response_model=FileMatchResponse,
)
async def match_files_endpoint(
    course_id: str,
    body: FileMatchRequest,
    user: dict = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
):
    """Match uploaded filenames to lecture numbers using LLM + heuristics."""
    from lecturelink_api.services.file_matcher import match_files_to_lectures

    sb = get_authenticated_supabase(user, settings)
    course = _get_course(sb, course_id, user["id"])

    # Build checklist (same logic as get_lecture_checklist)
    weekly_schedule = None
    syllabus_result = (
        sb.table("syllabi")
        .select("raw_extraction")
        .eq("course_id", course_id)
        .order("created_at", desc=True)
        .limit(1)
        .execute()
    )
    if syllabus_result.data:
        extraction = syllabus_result.data[0].get("raw_extraction") or {}
        weekly_schedule = extraction.get("weekly_schedule")

    checklist = generate_lecture_checklist(
        course=course,
        syllabus_weekly_schedule=weekly_schedule,
        holidays=course.get("holidays"),
    )

    # Merge user-added lectures
    additions = (
        sb.table("lecture_schedule_corrections")
        .select("*")
        .eq("course_id", course_id)
        .eq("user_id", user["id"])
        .eq("is_addition", True)
        .execute()
    )
    for row in additions.data or []:
        checklist.append({
            "lecture_number": row["original_lecture_number"],
            "expected_date": row["corrected_date"] or "",
            "week_number": 0,
            "topic_hint": row.get("corrected_title") or row.get("corrected_description"),
            "day_of_week": "",
            "status": "pending",
            "is_user_added": True,
        })

    matches = await match_files_to_lectures(body.filenames, checklist)
    return FileMatchResponse(
        matches=[FileMatchResult(**m) for m in matches],
    )


# -----------------------------------------------------------------------
# GET /api/courses/{course_id}/semester-progress
# -----------------------------------------------------------------------


@router.get(
    "/semester-progress",
    response_model=SemesterProgressResponse,
)
async def get_semester_progress_endpoint(
    course_id: str,
    user: dict = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
):
    sb = get_authenticated_supabase(user, settings)
    course = _get_course(sb, course_id, user["id"])

    progress = get_semester_progress(course)
    today = date.today()

    assessments_result = (
        sb.table("assessments")
        .select(
            "id, title, type, due_date, weight_percent, student_score"
        )
        .eq("course_id", course_id)
        .order("due_date")
        .execute()
    )
    all_assessments = assessments_result.data or []

    past = []
    upcoming = []
    for a in all_assessments:
        dd = _parse_due_date(a.get("due_date"))
        if dd is None:
            continue
        if dd < today:
            past.append(a)
        else:
            upcoming.append(a)

    next_assessment = upcoming[0] if upcoming else None

    return {
        **progress,
        "past_assessments": past,
        "upcoming_assessments": upcoming,
        "next_assessment": next_assessment,
    }


# -----------------------------------------------------------------------
# PUT /api/courses/{course_id}/onboarding/complete
# -----------------------------------------------------------------------


@router.put(
    "/onboarding/complete",
    response_model=OnboardingCompleteResponse,
)
async def complete_onboarding(
    course_id: str,
    user: dict = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
):
    sb = get_authenticated_supabase(user, settings)
    course = _get_course(sb, course_id, user["id"])

    now = datetime.utcnow().isoformat()

    mastery_count = 0
    if course.get("onboarding_path") == "mid_semester":
        mastery_count = await seed_mastery_from_scores(
            sb, course_id, user["id"],
        )

    sb.table("courses").update({
        "onboarding_completed_at": now,
        "onboarding_step": None,
    }).eq("id", course_id).execute()

    try:
        from lecturelink_api.services.observability import track_event

        track_event(user["id"], "onboarding_completed", {
            "course_id": course_id,
            "path": course.get("onboarding_path"),
        })
    except Exception:
        pass  # Observability is non-critical

    return {"completed_at": now, "mastery_scores_seeded": mastery_count}


# -----------------------------------------------------------------------
# PATCH /api/courses/{course_id}/notifications/preferences
# -----------------------------------------------------------------------


@router.patch("/notifications/preferences")
async def update_notification_preferences(
    course_id: str,
    body: dict,
    user: dict = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
):
    """Update user email notification preferences."""
    enabled = body.get("email_notifications_enabled")
    if enabled is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="email_notifications_enabled required",
        )

    sb = get_authenticated_supabase(user, settings)
    sb.table("user_onboarding").upsert(
        {
            "user_id": user["id"],
            "email_notifications_enabled": bool(enabled),
        },
        on_conflict="user_id",
    ).execute()

    return {"email_notifications_enabled": bool(enabled)}


# -----------------------------------------------------------------------
# PATCH /api/courses/{course_id}/onboarding/lecture-checklist/{lecture_number}
# -----------------------------------------------------------------------


@router.patch(
    "/onboarding/lecture-checklist/{lecture_number}",
    response_model=LectureChecklistItem,
)
async def update_lecture_checklist_item(
    course_id: str,
    lecture_number: int,
    body: LectureChecklistUpdate,
    user: dict = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
):
    """Edit the title, date, or description of an auto-generated lecture."""
    sb = get_authenticated_supabase(user, settings)
    course = _get_course(sb, course_id, user["id"])

    # Regenerate the checklist to find the original item
    weekly_schedule = None
    syllabus_result = (
        sb.table("syllabi")
        .select("raw_extraction")
        .eq("course_id", course_id)
        .order("created_at", desc=True)
        .limit(1)
        .execute()
    )
    if syllabus_result.data:
        extraction = syllabus_result.data[0].get("raw_extraction") or {}
        weekly_schedule = extraction.get("weekly_schedule")

    checklist = generate_lecture_checklist(
        course=course,
        syllabus_weekly_schedule=weekly_schedule,
        holidays=course.get("holidays"),
    )

    original = next(
        (item for item in checklist if item["lecture_number"] == lecture_number),
        None,
    )

    # Also check user-added lectures if not found in auto-generated checklist
    is_user_added = False
    if original is None:
        added = (
            sb.table("lecture_schedule_corrections")
            .select("*")
            .eq("course_id", course_id)
            .eq("user_id", user["id"])
            .eq("original_lecture_number", lecture_number)
            .eq("is_addition", True)
            .execute()
        )
        if added.data:
            row = added.data[0]
            original = {
                "lecture_number": lecture_number,
                "expected_date": row.get("corrected_date") or "",
                "week_number": 0,
                "topic_hint": row.get("corrected_title") or row.get("corrected_description"),
                "day_of_week": "",
                "status": "pending",
            }
            is_user_added = True

    if original is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Lecture {lecture_number} not found in checklist",
        )

    # Store correction for future improvement
    sb.table("lecture_schedule_corrections").insert({
        "course_id": course_id,
        "user_id": user["id"],
        "original_lecture_number": lecture_number,
        "original_title": f"Lecture {lecture_number}",
        "original_date": original["expected_date"] or None,
        "original_topic_hint": original.get("topic_hint"),
        "corrected_title": body.title,
        "corrected_date": body.lecture_date.isoformat() if body.lecture_date else None,
        "corrected_description": body.description,
        "is_addition": False,
    }).execute()

    # Return updated item
    return LectureChecklistItem(
        lecture_number=lecture_number,
        expected_date=body.lecture_date.isoformat() if body.lecture_date else original["expected_date"],
        week_number=original["week_number"],
        topic_hint=body.title or body.description or original.get("topic_hint"),
        day_of_week=original["day_of_week"],
        status=original["status"],
        is_user_added=is_user_added,
    )


# -----------------------------------------------------------------------
# POST /api/courses/{course_id}/onboarding/lecture-checklist
# -----------------------------------------------------------------------


@router.post(
    "/onboarding/lecture-checklist",
    response_model=LectureChecklistItem,
    status_code=status.HTTP_201_CREATED,
)
async def add_lecture_checklist_item(
    course_id: str,
    body: LectureChecklistAdd,
    user: dict = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
):
    """Add a missing lecture to the checklist."""
    sb = get_authenticated_supabase(user, settings)
    course = _get_course(sb, course_id, user["id"])

    # Get current checklist to determine next lecture number
    weekly_schedule = None
    syllabus_result = (
        sb.table("syllabi")
        .select("raw_extraction")
        .eq("course_id", course_id)
        .order("created_at", desc=True)
        .limit(1)
        .execute()
    )
    if syllabus_result.data:
        extraction = syllabus_result.data[0].get("raw_extraction") or {}
        weekly_schedule = extraction.get("weekly_schedule")

    checklist = generate_lecture_checklist(
        course=course,
        syllabus_weekly_schedule=weekly_schedule,
        holidays=course.get("holidays"),
    )

    # Also count user-added lectures
    existing_additions = (
        sb.table("lecture_schedule_corrections")
        .select("original_lecture_number")
        .eq("course_id", course_id)
        .eq("user_id", user["id"])
        .eq("is_addition", True)
        .execute()
    )
    added_numbers = [
        r["original_lecture_number"]
        for r in (existing_additions.data or [])
        if r.get("original_lecture_number") is not None
    ]

    max_existing = max(
        [item["lecture_number"] for item in checklist] + added_numbers + [0]
    )
    new_number = max_existing + 1

    # Store the addition for future improvement
    sb.table("lecture_schedule_corrections").insert({
        "course_id": course_id,
        "user_id": user["id"],
        "original_lecture_number": new_number,
        "original_title": None,
        "original_date": None,
        "original_topic_hint": None,
        "corrected_title": body.title,
        "corrected_date": body.lecture_date.isoformat() if body.lecture_date else None,
        "corrected_description": body.description,
        "is_addition": True,
    }).execute()

    date_str = body.lecture_date.isoformat() if body.lecture_date else date.today().isoformat()
    day_of_week = body.lecture_date.strftime("%A").lower() if body.lecture_date else ""

    return LectureChecklistItem(
        lecture_number=new_number,
        expected_date=date_str,
        week_number=body.week_number or 0,
        topic_hint=body.title or body.description,
        day_of_week=day_of_week,
        status="pending",
        is_user_added=True,
    )
