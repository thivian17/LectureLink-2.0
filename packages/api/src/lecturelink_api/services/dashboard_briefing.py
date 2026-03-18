"""Dashboard briefing service — deterministic data + single constrained LLM call.

Architecture:
  1. gather_briefing_context() — ALL DB queries, 0 LLM calls
  2. generate_greeting() — single Gemini Flash call, constrained to context data
  3. get_briefing() — orchestrator with 3-hour Redis cache

This follows the same pattern as study_actions.py (deterministic) →
study_actions_llm.py (LLM framing).
"""

from __future__ import annotations

import json
import logging
from datetime import date

from .mastery import compute_mastery

logger = logging.getLogger(__name__)

BRIEFING_MODEL = "gemini-2.5-flash"
CACHE_TTL_SECONDS = 0  # disabled — regenerate every visit

GREETING_SYSTEM_PROMPT = """\
You are a friendly study companion for a university student. Generate a personalized \
dashboard greeting using ONLY the structured data provided below.

STRICT RULES:
1. Every specific claim (dates, scores, concept names, assessment titles) MUST come from \
the context data. Do NOT invent or guess ANY facts.
2. Use the pre-computed "days_until" field for time references. NEVER calculate dates yourself.
3. Reference concept names and mastery scores EXACTLY as provided.
4. If the student has a streak > 0, mention it warmly.
5. If an assessment is within 7 days, lead with that urgency.
6. Keep the greeting to 3-5 sentences.
7. End with a warm check-in question about how they're feeling about classes.
8. If the student has no courses, warmly welcome them and encourage adding their first course.

Respond ONLY with valid JSON:
{
    "greeting": "Your personalized greeting (3-5 sentences)...",
    "session_pitch": "Why they should do today's session (1-2 sentences, reference specific concepts)...",
    "checkin_question": "A warm question about how they're feeling...",
    "encouragement": "Brief encouragement based on streak/progress (1 sentence, or empty string if no data)..."
}"""

NO_COURSES_GREETING = {
    "greeting": "Welcome to LectureLink! I'm your study companion, here to help you stay on top of your courses.",
    "session_pitch": "Add your first course and upload a syllabus to unlock personalized study sessions, smart quizzes, and mastery tracking.",
    "checkin_question": "Ready to get started? What course would you like to add first?",
    "encouragement": "",
}

CHAT_SYSTEM_PROMPT = """\
You are a supportive, friendly study companion for a university student. You have access \
to their academic data across ALL their courses (provided below as structured context).

YOUR ROLE:
- Be warm, empathetic, and encouraging
- Give practical, actionable study advice grounded in their actual data
- If they express anxiety about an assessment, acknowledge the feeling, then give \
  specific steps using their mastery data and time remaining
- If they ask about study strategies, tailor advice to their specific weak concepts
- Reference specific concept names, mastery scores, and assessment dates from the context
- Use the pre-computed "days_until" for time references. NEVER calculate dates yourself.

DO NOT:
- Invent facts, scores, or dates not in the context
- Give medical or mental health diagnoses
- Be dismissive of their feelings
- Provide generic advice when you have specific data to reference

Respond as natural conversational text (not JSON). Keep responses concise (3-6 sentences)."""


async def gather_briefing_context(supabase, user_id: str) -> dict:
    """Gather all structured data for the briefing. Zero LLM calls.

    Returns a dict with student_name, streak, xp, courses (with assessments,
    mastery, recent sessions, weak concepts, lecture gaps), and
    top_priority_course_id.
    """
    today = date.today()
    context: dict = {
        "student_name": "",
        "current_streak": 0,
        "total_xp": 0,
        "current_level": 1,
        "courses": [],
        "top_priority_course_id": None,
        "has_courses": False,
    }

    # --- Student profile ---
    try:
        profile = (
            supabase.table("profiles")
            .select("first_name")
            .eq("id", user_id)
            .maybe_single()
            .execute()
        )
        if profile.data and profile.data.get("first_name"):
            context["student_name"] = profile.data["first_name"]
        else:
            # Fallback to auth metadata or email prefix
            user_result = supabase.auth.get_user()
            if user_result and user_result.user:
                meta = user_result.user.user_metadata or {}
                context["student_name"] = (
                    meta.get("first_name", "")
                    or meta.get("full_name", "")
                    or (user_result.user.email or "").split("@")[0]
                )
    except Exception:
        pass

    # --- Streak + XP ---
    try:
        streak_result = (
            supabase.table("user_streaks")
            .select("current_streak, longest_streak")
            .eq("user_id", user_id)
            .single()
            .execute()
        )
        if streak_result.data:
            context["current_streak"] = streak_result.data.get("current_streak", 0)
    except Exception:
        pass

    try:
        level_result = (
            supabase.table("user_levels")
            .select("total_xp, current_level")
            .eq("user_id", user_id)
            .single()
            .execute()
        )
        if level_result.data:
            context["total_xp"] = level_result.data.get("total_xp", 0)
            context["current_level"] = level_result.data.get("current_level", 1)
    except Exception:
        pass

    # --- Courses ---
    try:
        courses_result = (
            supabase.table("courses")
            .select("id, name, code, semester_start, semester_end, meeting_days, holidays")
            .eq("user_id", user_id)
            .execute()
        )
        courses = courses_result.data or []
    except Exception:
        courses = []

    if not courses:
        return context

    context["has_courses"] = True

    # For each course, gather assessments, mastery, recent sessions
    course_data_list = []
    highest_priority = -1.0
    top_course_id = courses[0]["id"]

    for course in courses:
        cid = course["id"]
        course_entry: dict = {
            "course_id": cid,
            "course_name": course.get("name", ""),
            "course_code": course.get("code", ""),
            "next_assessment": None,
            "weak_concepts": [],
            "session_recommendation": None,
            "recent_session": None,
            "lecture_gap": 0,
        }

        # --- Next assessment ---
        try:
            assess_result = (
                supabase.table("assessments")
                .select("id, title, due_date, weight_percent, type")
                .eq("course_id", cid)
                .gte("due_date", today.isoformat())
                .order("due_date")
                .limit(1)
                .execute()
            )
            if assess_result.data:
                a = assess_result.data[0]
                due = date.fromisoformat(str(a["due_date"]))
                days_until = (due - today).days
                course_entry["next_assessment"] = {
                    "title": a["title"],
                    "due_date": a["due_date"],
                    "days_until": days_until,
                    "weight_percent": a.get("weight_percent", 0),
                    "type": a.get("type", ""),
                    "assessment_id": a["id"],
                }
                # Priority: closer + heavier = higher
                priority = (1.0 / max(days_until, 1)) * (a.get("weight_percent", 10) / 100)
                if priority > highest_priority:
                    highest_priority = priority
                    top_course_id = cid
        except Exception:
            pass

        # --- Weak concepts (bottom 3 by mastery) ---
        try:
            mastery_result = supabase.rpc(
                "get_concept_mastery",
                {"p_course_id": cid, "p_user_id": user_id},
            ).execute()
            mastery_rows = mastery_result.data or []

            scored = []
            for m in mastery_rows:
                acc = m.get("accuracy", 0.0)
                rec = m.get("recent_accuracy", 0.0)
                attempts = m.get("total_attempts", 0)
                if attempts > 0:
                    score = compute_mastery(acc, rec, attempts)
                    scored.append({
                        "concept_id": m["concept_id"],
                        "title": m.get("concept_title", ""),
                        "mastery": round(score, 2),
                    })

            scored.sort(key=lambda x: x["mastery"])
            course_entry["weak_concepts"] = scored[:3]
        except Exception:
            pass

        # --- Most recent completed learn session ---
        try:
            session_result = (
                supabase.table("learn_sessions")
                .select("completed_at, concepts_planned, session_data")
                .eq("user_id", user_id)
                .eq("course_id", cid)
                .eq("status", "completed")
                .order("completed_at", desc=True)
                .limit(1)
                .execute()
            )
            if session_result.data:
                s = session_result.data[0]
                sd = s.get("session_data", {})
                briefing = sd.get("daily_briefing", {})
                concepts_covered = [
                    c.get("title", "") for c in briefing.get("concepts_planned", [])
                ]
                quiz_results = sd.get("quiz_results", [])
                total_q = len(quiz_results)
                correct_q = sum(1 for r in quiz_results if r.get("correct"))
                course_entry["recent_session"] = {
                    "completed_at": s.get("completed_at", ""),
                    "concepts_covered": concepts_covered[:3],
                    "quiz_score": round(correct_q / max(total_q, 1), 2),
                }
        except Exception:
            pass

        # --- Lecture gap ---
        try:
            from .schedule_utils import compute_lecture_gap

            sem_start_str = course.get("semester_start")
            meeting_days = course.get("meeting_days") or []
            if sem_start_str and meeting_days:
                # Count actual lectures uploaded
                lecture_count_result = (
                    supabase.table("lectures")
                    .select("id", count="exact")
                    .eq("course_id", cid)
                    .execute()
                )
                actual_count = lecture_count_result.count or 0

                gap_result = compute_lecture_gap(
                    semester_start=date.fromisoformat(str(sem_start_str)),
                    meeting_days=meeting_days,
                    holidays=course.get("holidays"),
                    actual_lecture_count=actual_count,
                )
                course_entry["lecture_gap"] = gap_result.missing_count
        except Exception:
            pass

        # --- Session recommendation (concepts to study) ---
        if course_entry["next_assessment"] and course_entry["weak_concepts"]:
            course_entry["session_recommendation"] = {
                "concepts": [c["title"] for c in course_entry["weak_concepts"][:2]],
                "reason": "assessment_prep",
                "time_budget": 15,
            }
        elif course_entry["next_assessment"]:
            # Assessment upcoming but no quiz attempts yet — recommend starting
            try:
                concepts_result = (
                    supabase.table("concepts")
                    .select("title")
                    .eq("course_id", cid)
                    .order("created_at", desc=True)
                    .limit(2)
                    .execute()
                )
                concept_titles = [
                    c["title"] for c in (concepts_result.data or []) if c.get("title")
                ]
                if concept_titles:
                    course_entry["session_recommendation"] = {
                        "concepts": concept_titles,
                        "reason": "first_session",
                        "time_budget": 15,
                    }
            except Exception:
                pass
        elif course_entry["weak_concepts"]:
            # No upcoming assessment but has weak concepts — general review
            course_entry["session_recommendation"] = {
                "concepts": [c["title"] for c in course_entry["weak_concepts"][:2]],
                "reason": "review",
                "time_budget": 15,
            }

        course_data_list.append(course_entry)

    context["courses"] = course_data_list
    context["top_priority_course_id"] = top_course_id
    return context


async def generate_greeting(context: dict) -> dict:
    """Generate a greeting from structured context via a single Gemini Flash call.

    If the student has no courses, returns a static welcome message (zero LLM cost).
    """
    if not context.get("has_courses"):
        return NO_COURSES_GREETING

    from .genai_client import get_genai_client as _get_client

    prompt = f"Student context:\n{json.dumps(context, indent=2, default=str)}"

    try:
        response = await _get_client().aio.models.generate_content(
            model=BRIEFING_MODEL,
            contents=prompt,
            config={
                "system_instruction": GREETING_SYSTEM_PROMPT,
                "temperature": 0.4,
                "response_mime_type": "application/json",
            },
        )
        result = json.loads(response.text)

        # Validate required fields
        for key in ("greeting", "session_pitch", "checkin_question"):
            if key not in result or not result[key]:
                raise ValueError(f"Missing required field: {key}")

        return result
    except Exception:
        logger.warning("Greeting generation failed, using fallback", exc_info=True)
        # Deterministic fallback — no LLM, just template
        name = context.get("student_name", "there")
        courses = context.get("courses", [])
        top = courses[0] if courses else {}
        assess = top.get("next_assessment", {})

        greeting = f"Hey {name}!"
        if assess:
            greeting += f" Your next assessment is {assess.get('title', 'coming up')} in {assess.get('days_until', '?')} days."
        if context.get("current_streak", 0) > 0:
            greeting += f" You're on a {context['current_streak']}-day streak."

        return {
            "greeting": greeting,
            "session_pitch": "Start a study session to keep building momentum.",
            "checkin_question": "How are you feeling about your classes?",
            "encouragement": "",
        }


async def get_briefing(supabase, user_id: str) -> dict:
    """Orchestrator: gather data → generate greeting.

    Regenerates on every visit for a fresh, contextual experience.
    """
    # 1. Gather deterministic context
    context = await gather_briefing_context(supabase, user_id)

    # 2. Generate greeting (single LLM call or static fallback)
    greeting = await generate_greeting(context)

    # 3. Build response
    return {
        "context": context,
        "greeting": greeting,
    }


async def chat_cross_course(
    supabase,
    user_id: str,
    message: str,
    conversation_history: list[dict] | None = None,
) -> dict:
    """Process a cross-course chat message.

    Uses the same deterministic context as the briefing, but with a
    conversational system prompt focused on emotional support + advice.
    """
    from .genai_client import get_genai_client as _get_client

    # Reuse the briefing context (may hit cache)
    context = await gather_briefing_context(supabase, user_id)

    # Build conversation
    messages = []
    if conversation_history:
        for msg in conversation_history[-10:]:  # Keep last 10 turns
            messages.append({
                "role": msg.get("role", "user"),
                "parts": [{"text": msg.get("content", "")}],
            })
    messages.append({"role": "user", "parts": [{"text": message}]})

    context_block = f"Student academic context:\n{json.dumps(context, indent=2, default=str)}"

    try:
        response = await _get_client().aio.models.generate_content(
            model=BRIEFING_MODEL,
            contents=[
                {"role": "user", "parts": [{"text": context_block}]},
                {"role": "model", "parts": [{"text": "I have the student's academic context. I'll use it to give personalized advice."}]},
                *messages,
            ],
            config={
                "system_instruction": CHAT_SYSTEM_PROMPT,
                "temperature": 0.5,
            },
        )
        return {
            "message": response.text,
            "context_used": True,
        }
    except Exception:
        logger.error("Cross-course chat failed", exc_info=True)
        return {
            "message": "I'm having trouble connecting right now. In the meantime, check your dashboard for study recommendations.",
            "context_used": False,
        }
