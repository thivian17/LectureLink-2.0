"""Study Coach agent — ADK agent definition for future mounting.

This agent definition is available for mounting at /agents/study-coach
via the ADK dev UI. The primary chat endpoint uses the direct Gemini
API in services/coach.py for simplicity.
"""

from __future__ import annotations

from google.adk.agents import LlmAgent
from google.adk.tools import FunctionTool
from google.genai import types

from lecturelink_api.services.coach_tools import (
    get_performance_tool,
    get_upcoming_assessments_tool,
)
from lecturelink_api.services.rag_tool import ask_question_tool

_COACH_INSTRUCTION = """\
You are an expert study coach for a university student. You have access to their
performance data (concept mastery scores, quiz history) and can look up lecture content.

The student is asking: {user_message}

Context:
- Course ID: {course_id}
- User ID: {user_id}

Your approach:
1. First, use get_performance_tool to understand the student's current standing
2. Use get_upcoming_assessments_tool to see what's coming up
3. If the student asks a specific content question, use ask_question_tool to ground \
your answer
4. Synthesize everything into personalized, actionable advice

Guidelines:
- Be specific: name exact concepts and lectures
- Prioritize by: (a) upcoming assessment relevance, (b) concept mastery weakness, \
(c) trend
- If a concept is declining, flag it urgently
- Suggest concrete actions: "Take a quiz focused on X", "Review lecture Y at timestamp Z"
- Be encouraging but honest about weak areas
- Keep responses concise — students are busy
"""

study_coach_agent = LlmAgent(
    name="StudyCoach",
    model="gemini-2.5-flash",
    instruction=_COACH_INSTRUCTION,
    tools=[
        FunctionTool(func=get_performance_tool),
        FunctionTool(func=get_upcoming_assessments_tool),
        FunctionTool(func=ask_question_tool),
    ],
    generate_content_config=types.GenerateContentConfig(
        temperature=0.4,
    ),
)
