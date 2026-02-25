"""Study Actions (LLM) — Gemini-powered personalized study recommendations."""

from __future__ import annotations

import json
import logging
from datetime import date

from .genai_client import get_genai_client as _get_client
from .study_actions import (
    LectureGap,
    StudyAction,
    _gather_course_context,
    compute_lecture_gap,
)

logger = logging.getLogger(__name__)

ACTIONS_MODEL = "gemini-2.5-flash"


VALID_ACTION_TYPES = frozenset({
    "upload_syllabus",
    "review_syllabus",
    "upload_lectures",
    "assessment_prep",
    "take_quiz",
    "study_weak_concept",
})

SYSTEM_PROMPT = """\
You are a personalized study coach for a university student. Your job is to analyze \
their current situation across ALL their courses and generate a prioritized list of \
the most impactful study actions they should take right now.

RULES:
1. Generate 1-5 actions, ranked by importance (highest priority first).
2. Consider ALL courses holistically — an upcoming exam in one course outweighs a \
routine quiz in another.
3. Write natural, motivating titles and descriptions. Be specific — reference concept \
names, dates, lecture counts, and assessment names when available.
   - Good: "Your Algorithms midterm is in 3 days — drill Binary Trees (32% mastery)"
   - Bad: "Assessment prep for CS 201"
   - Good: "You're 4 lectures behind in Data Structures — your Monday class was 2 days ago"
   - Bad: "Upload lectures for your course"
4. ALWAYS use the pre-computed "days_until" field for time references. \
NEVER calculate days from dates yourself — your math will be wrong. For example, \
if days_until=1, say "tomorrow" or "in 1 day", NOT "in 36 days".
5. Each action MUST use one of these exact action_types:
   - "upload_syllabus": Course has no usable syllabus
   - "review_syllabus": AI extraction from syllabus needs human review
   - "upload_lectures": Student is behind on uploading lecture materials
   - "assessment_prep": Upcoming assessment with weak areas to study
   - "take_quiz": Practice quiz to strengthen a weak concept
   - "study_weak_concept": Broader review of a struggling topic
6. course_id, course_name, and course_code MUST be copied EXACTLY from the input data.
7. cta_url MUST be selected from the cta_urls provided for each course. Do NOT invent URLs.
8. cta_label should be a short imperative phrase (2-4 words): "Upload Syllabus", \
"Start Quiz", "Review Extraction", "Upload Lecture", "Study Now".
9. priority is a float from 0.0 to 1.0:
   - 0.9-1.0: Blocking issue (no syllabus) or exam tomorrow
   - 0.7-0.9: Urgent (exam this week, significantly behind on lectures)
   - 0.4-0.7: Important but not urgent (weak concepts, routine study)
   - 0.1-0.4: Nice-to-have (minor improvements)

OUTPUT FORMAT (strict JSON):
{
  "actions": [
    {
      "action_type": "one of the 6 types above",
      "priority": 0.85,
      "course_id": "exact-uuid-from-input",
      "course_name": "exact name from input",
      "course_code": "exact code or null",
      "title": "Your personalized, motivating title",
      "description": "1-2 sentence explanation of why this matters and what to do",
      "cta_label": "Button Text",
      "cta_url": "url from cta_urls",
      "metadata": {}
    }
  ]
}"""


# ---------------------------------------------------------------------------
# Context construction
# ---------------------------------------------------------------------------


def _build_llm_context(
    courses: list[dict],
    contexts: dict[str, dict],
    performances: dict[str, dict],
    lecture_gaps: dict[str, LectureGap | None],
) -> str:
    """Serialize all student data into compact JSON for the LLM prompt."""
    today = date.today()
    course_data = []

    for course in courses:
        cid = course["id"]
        base_url = f"/dashboard/courses/{cid}"
        ctx = contexts.get(cid, {})

        entry: dict = {
            "course_id": cid,
            "course_name": course["name"],
            "course_code": course.get("code"),
            "cta_urls": {
                "upload_syllabus": base_url,
                "review_syllabus": f"{base_url}/syllabus/review",
                "upload_lectures": f"{base_url}/lectures/new",
                "study": f"{base_url}/tutor",
            },
        }

        # Syllabus status
        syl = ctx.get("syllabus")
        if not syl:
            entry["syllabus_status"] = "none"
        else:
            entry["syllabus_status"] = syl.get("status", "unknown")
            if syl.get("needs_review") and not syl.get("reviewed_at"):
                entry["needs_review"] = True

        # Lecture gap
        gap = lecture_gaps.get(cid)
        if gap and gap.missing_count > 0:
            entry["lecture_gap"] = {
                "expected": gap.expected_count,
                "actual": gap.actual_count,
                "missing": gap.missing_count,
                "last_expected_date": (
                    gap.last_expected_date.isoformat() if gap.last_expected_date else None
                ),
                "next_expected_date": (
                    gap.next_expected_date.isoformat() if gap.next_expected_date else None
                ),
            }

        # Upcoming assessments
        upcoming = ctx.get("upcoming_assessments", [])
        if upcoming:
            assessment_entries = []
            for a in upcoming:
                ae: dict = {
                    "title": a["title"],
                    "type": a["type"],
                    "weight_percent": a.get("weight_percent"),
                }
                due_str = a.get("due_date")
                if due_str:
                    try:
                        due = date.fromisoformat(str(due_str)[:10])
                        ae["days_until"] = (due - today).days
                        ae["due_date_display"] = due.strftime("%b %d")
                    except (ValueError, TypeError):
                        pass
                topics = a.get("topics")
                if topics:
                    ae["topics"] = topics
                assessment_entries.append(ae)
            entry["upcoming_assessments"] = assessment_entries

        # Performance summary (compact)
        perf = performances.get(cid)
        if perf:
            weak = [
                {
                    "title": c["title"],
                    "mastery": round(c["mastery"], 2),
                    "trend": c["trend"],
                }
                for c in perf.get("concepts", [])
                if c["concept_id"] in set(perf.get("weak_concepts", []))
            ][:8]

            entry["performance"] = {
                "overall_accuracy": perf["overall"].get("overall_accuracy"),
                "quizzes_taken": perf["overall"].get("quizzes_taken"),
                "weak_concepts": weak,
                "strong_concepts_count": len(perf.get("strong_concepts", [])),
            }

        course_data.append(entry)

    return json.dumps(
        {"today": today.isoformat(), "day_of_week": today.strftime("%A"), "courses": course_data},
        indent=2,
        default=str,
    )


# ---------------------------------------------------------------------------
# Post-processing validation
# ---------------------------------------------------------------------------


def _validate_llm_actions(raw: dict, courses: list[dict]) -> list[StudyAction]:
    """Parse LLM output into validated StudyAction objects.

    Drops any action with an invalid action_type or missing course_id.
    Overwrites course_name/code from DB and auto-corrects bad cta_urls.
    """
    raw_actions = raw.get("actions", [])
    if not isinstance(raw_actions, list):
        logger.warning("LLM returned non-list actions: %s", type(raw_actions))
        return []

    valid_courses = {c["id"] for c in courses}
    course_lookup = {c["id"]: c for c in courses}

    validated: list[StudyAction] = []
    for item in raw_actions:
        try:
            if not isinstance(item, dict):
                continue

            action_type = item.get("action_type")
            if action_type not in VALID_ACTION_TYPES:
                logger.debug("Dropping action with invalid type: %s", action_type)
                continue

            cid = item.get("course_id")
            if cid not in valid_courses:
                logger.debug("Dropping action with invalid course_id: %s", cid)
                continue

            # Auto-correct cta_url if it doesn't match expected prefix
            base = f"/dashboard/courses/{cid}"
            cta = item.get("cta_url", "")
            if not cta.startswith(base):
                url_map = {
                    "upload_syllabus": base,
                    "review_syllabus": f"{base}/syllabus/review",
                    "upload_lectures": f"{base}/lectures/new",
                    "assessment_prep": f"{base}/tutor",
                    "take_quiz": f"{base}/tutor",
                    "study_weak_concept": f"{base}/tutor",
                }
                cta = url_map.get(action_type, base)

            # Clamp priority
            priority = max(0.0, min(1.0, float(item.get("priority", 0.5))))

            # Overwrite structural data from DB
            course = course_lookup[cid]

            action = StudyAction(
                action_type=action_type,
                priority=priority,
                course_id=cid,
                course_name=course["name"],
                course_code=course.get("code"),
                title=str(item.get("title", "")),
                description=str(item.get("description", "")),
                cta_label=str(item.get("cta_label", "Go")),
                cta_url=cta,
                metadata=item.get("metadata") if isinstance(item.get("metadata"), dict) else {},
            )
            validated.append(action)

        except Exception:
            logger.debug("Dropping invalid action: %s", item, exc_info=True)
            continue

    return validated


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------


async def get_study_actions_llm(
    supabase,
    user_id: str,
    course_id: str | None = None,
    limit: int = 5,
) -> list[StudyAction]:
    """Compute ranked study actions using Gemini LLM.

    Gathers context deterministically, then delegates prioritization
    and language generation to Gemini 2.5 Flash.
    """
    # 1. Fetch courses
    query = supabase.table("courses").select("*").eq("user_id", user_id)
    if course_id:
        query = query.eq("id", course_id)

    courses_result = query.execute()
    courses = courses_result.data or []

    if not courses:
        return []

    # 2. Gather context per course
    contexts: dict[str, dict] = {}
    performances: dict[str, dict] = {}
    lecture_gaps: dict[str, LectureGap | None] = {}

    for course in courses:
        cid = course["id"]

        # Course context (syllabus, lectures, assessments)
        try:
            ctx = await _gather_course_context(supabase, course, user_id)
            contexts[cid] = ctx
        except Exception:
            logger.warning("Failed to gather context for %s", cid, exc_info=True)
            contexts[cid] = {}

        ctx = contexts[cid]

        # Performance data (only when there's content to analyze)
        if ctx.get("syllabus") and ctx.get("lecture_count", 0) > 0:
            try:
                from .performance import get_performance

                perf = await get_performance(supabase, cid, user_id)
                performances[cid] = perf
            except Exception:
                logger.debug("Skipping performance for %s", cid, exc_info=True)

        # Lecture gap
        meeting_days = course.get("meeting_days") or []
        sem_start_str = course.get("semester_start")
        if meeting_days and sem_start_str:
            try:
                sem_start = date.fromisoformat(str(sem_start_str))
                lecture_gaps[cid] = compute_lecture_gap(
                    sem_start,
                    meeting_days,
                    course.get("holidays") or [],
                    ctx.get("lecture_count", 0),
                )
            except (ValueError, TypeError):
                pass

    # 3. Build context string
    context_str = _build_llm_context(courses, contexts, performances, lecture_gaps)

    # 4. Call Gemini
    try:
        response = await _get_client().aio.models.generate_content(
            model=ACTIONS_MODEL,
            contents=f"Generate study actions for this student:\n\n{context_str}",
            config={
                "system_instruction": SYSTEM_PROMPT,
                "temperature": 0.4,
                "response_mime_type": "application/json",
            },
        )
        raw = json.loads(response.text)
    except Exception:
        logger.error("Study actions LLM call failed", exc_info=True)
        return []

    # 5. Validate and return
    actions = _validate_llm_actions(raw, courses)
    actions.sort(key=lambda a: a.priority, reverse=True)
    return actions[:limit]
