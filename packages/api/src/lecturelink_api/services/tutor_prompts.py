"""Prompt templates for the Study Tutor.

All prompts follow this philosophy:
1. GROUND in lecture content — reference specific lectures and examples
2. CHECK frequently — teach then verify
3. ADAPT — different angles for reteaching, not repetition
4. CONNECT — link concepts to assessments and prerequisites
5. BE DIRECT — no filler, no empty praise
"""

from __future__ import annotations

import json

# ---------------------------------------------------------------------------
# System prompt
# ---------------------------------------------------------------------------


def get_tutor_system_prompt(
    course_name: str,
    course_code: str,
    assessment_title: str,
    days_until: int,
    weight_percent: float | None,
    assessment_topics: list[str],
    student_name: str | None,
    mastery_summary: list[dict],
    mode: str,
    previous_session_summary: str | None = None,
) -> str:
    """Build the tutor system prompt with full context."""
    name_line = f"The student's name is {student_name}." if student_name else ""

    weight_line = (
        f"This assessment is worth {weight_percent}% of the final grade."
        if weight_percent is not None
        else "The weight of this assessment is unknown."
    )

    urgency = (
        "This is urgent — the assessment is imminent."
        if days_until <= 3
        else (
            "Time is limited — prioritize high-impact topics."
            if days_until <= 7
            else "There is reasonable time to build understanding."
        )
    )

    topics_str = ", ".join(assessment_topics) if assessment_topics else "general course material"

    mastery_lines = []
    for entry in mastery_summary:
        title = entry.get("title", "Unknown")
        m = entry.get("mastery", 0.5)
        level = "strong" if m >= 0.8 else "developing" if m >= 0.5 else "weak"
        mastery_lines.append(f"  - {title}: {level} (mastery {m:.0%})")
    mastery_str = "\n".join(mastery_lines) if mastery_lines else "  No mastery data available."

    mode_instructions = {
        "guided": (
            "Lead a structured lesson. Explain concepts, then check understanding "
            "with questions before moving on. Adapt based on student responses."
        ),
        "practice": (
            "Focus on practice problems and worked examples. Provide questions, "
            "evaluate answers, and reteach only when misconceptions arise."
        ),
        "diagnostic": (
            "Assess the student's current understanding. Ask probing questions "
            "across the key topics, then summarize strengths and gaps."
        ),
        "review": (
            "Help the student review material. Focus on connections between "
            "concepts and common exam patterns. Keep it concise and direct."
        ),
    }
    mode_instruction = mode_instructions.get(mode, mode_instructions["guided"])

    prev_session = ""
    if previous_session_summary:
        prev_session = (
            f"\n\nPrevious session summary:\n{previous_session_summary}\n"
            "Build on this — avoid re-covering material the student already knows."
        )

    return f"""\
You are a focused, adaptive study tutor for {course_name} ({course_code}).
{name_line}

TARGET: Prepare for "{assessment_title}" — {days_until} days away.
{weight_line}
{urgency}

Topics to cover: {topics_str}

Student mastery:
{mastery_str}

Mode: {mode}
{mode_instruction}

Core rules:
- Ground every explanation in lecture content. Cite lectures by title when possible.
- After explaining, CHECK with a question before moving on.
- If the student gets something wrong, reteach from a DIFFERENT angle — never repeat.
- Keep explanations between 150-250 words. Be concise and direct.
- No filler phrases. No empty praise. Acknowledge correct answers briefly, then move on.
- Connect concepts to the upcoming assessment whenever relevant.
- If the student asks something unrelated, briefly redirect to the study plan.{prev_session}"""


# ---------------------------------------------------------------------------
# Lesson plan
# ---------------------------------------------------------------------------


def get_lesson_plan_prompt(
    concepts: list[dict],
    assessment_context: str,
    mode: str,
    custom_topic: str | None = None,
    suggested_duration_minutes: int = 30,
) -> str:
    """Prompt that generates the structured lesson plan JSON."""
    concepts_str = json.dumps(concepts, indent=2, default=str)

    custom_note = ""
    if custom_topic:
        custom_note = (
            f'\nThe student specifically requested help with: "{custom_topic}". '
            "Prioritize this topic above others."
        )

    return f"""\
Create a structured lesson plan for a {suggested_duration_minutes}-minute tutoring session.

Assessment context:
{assessment_context}

Session mode: {mode}
{custom_note}

Priority concepts (ordered by priority):
{concepts_str}

Design a focused session plan. For each concept, choose a teaching approach:
- "foundational": For mastery < 0.4 — build from basics with clear explanations.
- "application": For mastery 0.4–0.7 — use examples and practice problems.
- "synthesis": For mastery > 0.7 — connect to other concepts, exam-style challenges.

Each concept's outline should include steps of these types:
- "activate": Brief warm-up connecting to what they know (1-2 min)
- "explain": Core teaching block (3-5 min)
- "check": Comprehension question to verify understanding
- "practice": Practice problem or worked example
- "summary": Brief recap of the concept
- "transition": Bridge to the next concept

Respond ONLY with valid JSON, no markdown fences or preamble:
{{
  "session_title": "string — short descriptive title",
  "estimated_duration_minutes": {suggested_duration_minutes},
  "concepts": [
    {{
      "concept_id": "string or null",
      "title": "concept title",
      "mastery": 0.0,
      "priority_score": 0.0,
      "teaching_approach": "foundational | application | synthesis",
      "estimated_minutes": 8,
      "outline": [
        {{
          "type": "activate | explain | check | practice | summary | transition",
          "description": "what this step covers",
          "question_type": "mcq | short_answer | true_false | fill_in_blank | long_answer",
          "targets": "what understanding this checks (check steps only)"
        }}
      ]
    }}
  ],
  "wrap_up": {{
    "type": "summary",
    "description": "brief session wrap-up plan"
  }}
}}"""


# ---------------------------------------------------------------------------
# Teaching block
# ---------------------------------------------------------------------------


def get_teaching_block_prompt(
    concept_title: str,
    teaching_approach: str,
    mastery: float,
    lecture_chunks: list[dict],
    step_description: str,
) -> str:
    """Prompt for generating a teaching explanation block."""
    chunks_text = _format_chunks(lecture_chunks)

    approach_guidance = {
        "foundational": (
            "Build from the ground up. Define key terms clearly. "
            "Use a concrete example to illustrate the core idea. "
            "Assume limited prior understanding."
        ),
        "application": (
            "The student has basic understanding. Focus on HOW to apply this concept. "
            "Walk through a worked example step by step. "
            "Highlight common mistakes."
        ),
        "synthesis": (
            "The student understands the basics. Connect this concept to related ideas. "
            "Present a challenging scenario or comparison. "
            "Focus on deeper insight and exam-level reasoning."
        ),
    }
    approach_text = approach_guidance.get(teaching_approach, approach_guidance["foundational"])

    return f"""\
Explain the concept "{concept_title}" to a student.

Teaching goal: {step_description}
Teaching approach: {teaching_approach}
Student mastery: {mastery:.0%}

{approach_text}

Relevant lecture content:
{chunks_text}

Rules:
- 150-250 words. Be concise and direct.
- Ground your explanation in the lecture content above. Reference specific examples or statements.
- Use markdown formatting: **bold** for key terms, bullet points for lists.
- Do NOT end with "let's check your understanding" or similar — the question will appear automatically.
- Do NOT ask a question — that comes in the next step.
- Do NOT include empty praise or filler."""


# ---------------------------------------------------------------------------
# Check question
# ---------------------------------------------------------------------------


def get_check_question_prompt(
    concept_title: str,
    question_type: str,
    target_understanding: str,
    lecture_chunks: list[dict],
    mastery: float,
) -> str:
    """Prompt that generates a question AND its grading rubric simultaneously."""
    chunks_text = _format_chunks(lecture_chunks)

    type_instructions = {
        "mcq": (
            "Create a multiple-choice question with exactly 4 options (A-D). "
            "Exactly one correct answer. Distractors should be plausible "
            "misconceptions, not obviously wrong."
        ),
        "short_answer": (
            "Create a question requiring a 1-3 sentence response. "
            "The answer should demonstrate understanding, not just recall."
        ),
        "true_false": (
            "Create a true/false statement. It should be unambiguous based on the lecture content."
        ),
        "fill_in_blank": (
            "Create a sentence with one key term blanked out. "
            "Provide 2-3 acceptable answers including common synonyms."
        ),
        "long_answer": (
            "Create a question requiring a paragraph-length response (3-5 sentences). "
            "Should test ability to explain or apply the concept."
        ),
    }
    type_text = type_instructions.get(question_type, type_instructions["short_answer"])

    difficulty = "basic" if mastery < 0.4 else "intermediate" if mastery < 0.7 else "advanced"

    return f"""\
Generate a {question_type} question about "{concept_title}".

Target understanding: {target_understanding}
Difficulty: {difficulty} (student mastery: {mastery:.0%})

{type_text}

Relevant lecture content:
{chunks_text}

The question MUST be answerable from the provided lecture content.

Respond ONLY with valid JSON, no markdown fences or preamble:
{{
  "question_text": "the question",
  "question_type": "{question_type}",
  "options": ["A) ...", "B) ...", "C) ...", "D) ..."],
  "correct_answer": "the correct answer text",
  "acceptable_answers": ["answer1", "answer2"],
  "rubric": {{
    "must_mention": ["key point 1", "key point 2"],
    "partial_credit_for": ["related idea that shows some understanding"],
    "common_misconceptions": [
      {{"misconception": "what students often think", "why_wrong": "brief explanation"}}
    ],
    "model_answer": "ideal complete answer",
    "misconception_detection": {{
      "if_mentions_X": "likely confused about Y",
      "if_misses_Z": "probably doesn't understand W"
    }}
  }}
}}

Notes:
- "options" is only for MCQ; omit or set to null for other types.
- "acceptable_answers" is only for fill_in_blank; omit or set to null for other types.
- "rubric" is required for ALL question types."""


# ---------------------------------------------------------------------------
# Grading
# ---------------------------------------------------------------------------


def get_grading_prompt(
    question_text: str,
    student_answer: str,
    rubric: dict,
    lecture_context: str,
) -> str:
    """Prompt for LLM-based grading (Tier 2 and 3)."""
    rubric_str = json.dumps(rubric, indent=2, default=str)

    return f"""\
Grade this student's answer.

Question: {question_text}

Student's answer: {student_answer}

Grading rubric:
{rubric_str}

Relevant lecture context:
{lecture_context}

Evaluate the student's response against the rubric. Be fair but rigorous.
- Check each "must_mention" criterion.
- Award partial credit where the rubric allows.
- Look for misconceptions listed in the rubric.
- Do NOT penalize correct answers that use different wording than the model answer.
- Do NOT give credit for vague or non-specific responses.

Respond ONLY with valid JSON, no markdown fences or preamble:
{{
  "is_correct": true,
  "partially_correct": false,
  "criteria_met": ["criterion 1"],
  "criteria_missed": ["criterion 2"],
  "misconceptions_detected": ["misconception description"],
  "misconception_type": "near_miss | fundamental | none",
  "feedback": "Specific, constructive feedback — what they got right and what to improve.",
  "confidence": 0.9
}}"""


# ---------------------------------------------------------------------------
# Reteach
# ---------------------------------------------------------------------------


def get_reteach_prompt(
    concept_title: str,
    original_explanation: str,
    misconception: str,
    misconception_type: str,
    lecture_chunks: list[dict],
) -> str:
    """Prompt for reteaching from a different angle."""
    chunks_text = _format_chunks(lecture_chunks)

    if misconception_type == "near_miss":
        length_guide = "50-100 words. Be brief and targeted."
        approach = (
            "The student almost has it. They have a small misunderstanding. "
            "Directly address the specific error. Use a precise correction."
        )
    else:
        length_guide = "150-250 words. Provide a thorough re-explanation."
        approach = (
            "The student has a fundamental misunderstanding. DO NOT repeat the "
            "original explanation — it didn't work. Instead, choose ONE of these "
            "alternative approaches:\n"
            "- Comparison: contrast the correct idea with a related but different concept\n"
            "- Analogy: relate to something from everyday experience\n"
            "- Concrete trace: walk through a specific example step by step\n"
            "- Counterexample: show why the misconception leads to a contradiction"
        )

    return f"""\
Reteach the concept "{concept_title}" to a student who got it wrong.

What was originally taught:
{original_explanation}

What the student got wrong:
{misconception}

Misconception type: {misconception_type}

{approach}

Relevant lecture content:
{chunks_text}

Rules:
- {length_guide}
- NEVER repeat the original explanation above.
- Ground in lecture content. Reference specific examples.
- End with a brief encouraging note to continue, such as "With this in mind, let's keep going."
- Do NOT ask a question or prompt for confirmation — the session will continue automatically."""


# ---------------------------------------------------------------------------
# Practice
# ---------------------------------------------------------------------------


def get_practice_prompt(
    concept_title: str,
    mastery: float,
    lecture_chunks: list[dict],
) -> str:
    """Prompt for generating a practice problem or worked example."""
    chunks_text = _format_chunks(lecture_chunks)

    if mastery < 0.4:
        style = (
            "Create a WORKED EXAMPLE: present a problem, then walk through the "
            "solution step by step. The student should follow along and understand "
            "the approach."
        )
    elif mastery < 0.7:
        style = (
            "Create a PRACTICE PROBLEM: present a problem similar to the lecture "
            "examples but with different values or a slight twist. Provide the "
            "answer separately at the end."
        )
    else:
        style = (
            "Create a CHALLENGE PROBLEM: present a problem that requires "
            "combining this concept with related ideas or applying it in a "
            "novel context. Provide a hint and the full solution."
        )

    return f"""\
Generate a practice problem about "{concept_title}".

Student mastery: {mastery:.0%}

{style}

Relevant lecture content:
{chunks_text}

Rules:
- The problem MUST be solvable using concepts from the provided lecture content.
- Use concrete values and realistic scenarios.
- Format the problem clearly with markdown.
- If providing a solution, use a step-by-step format."""


# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------


def get_summary_prompt(
    concept_title: str,
    questions_asked: int,
    questions_correct: int,
    key_misconceptions: list[str],
) -> str:
    """Prompt for end-of-concept summary block."""
    accuracy = questions_correct / questions_asked if questions_asked > 0 else 0

    misconceptions_note = ""
    if key_misconceptions:
        items = "\n".join(f"  - {m}" for m in key_misconceptions)
        misconceptions_note = f"\n\nMisconceptions encountered:\n{items}"

    return f"""\
Summarize the student's performance on "{concept_title}".

Performance: {questions_correct}/{questions_asked} correct ({accuracy:.0%})
{misconceptions_note}

Write a brief summary (2-4 sentences):
- What they demonstrated understanding of
- What still needs work (if anything)
- One concrete next step for continued practice

Be direct. No empty praise. If they did well, acknowledge it briefly and move on.
If they struggled, be honest but constructive."""


# ---------------------------------------------------------------------------
# Transition
# ---------------------------------------------------------------------------


def get_transition_prompt(
    completed_concept: str,
    next_concept: str,
    connection: str | None = None,
) -> str:
    """Prompt for bridging between concepts."""
    connection_note = ""
    if connection:
        connection_note = f'\nThese concepts are connected: "{connection}".'

    return f"""\
Write a brief transition (2-3 sentences) from "{completed_concept}" to "{next_concept}".
{connection_note}

Connect what the student just learned to what comes next.
Make the transition feel natural and purposeful — explain WHY we're moving to this topic.
Keep it under 50 words."""


# ---------------------------------------------------------------------------
# Chat relevance
# ---------------------------------------------------------------------------


def get_chat_relevance_prompt(
    student_message: str,
    current_concept: str,
    assessment_topics: list[str],
) -> str:
    """Prompt to classify student's chat message relevance."""
    topics_str = ", ".join(assessment_topics) if assessment_topics else "general course material"

    return f"""\
Classify this student message relative to the current study session.

Current concept being studied: {current_concept}
Assessment topics: {topics_str}

Student's message: "{student_message}"

Respond ONLY with valid JSON, no markdown fences or preamble:
{{
  "relevance": "on_topic | related | off_topic",
  "should_answer": true,
  "redirect_message": "optional — if off_topic, a brief message redirecting them back"
}}

Classification guide:
- "on_topic": Directly about the current concept
- "related": About a related concept or the assessment — still useful to answer
- "off_topic": Completely unrelated to the course or assessment"""


# ---------------------------------------------------------------------------
# Chat answer
# ---------------------------------------------------------------------------


def get_chat_answer_prompt(
    student_message: str,
    current_concept: str,
    lecture_chunks: list[dict],
    assessment_context: str,
) -> str:
    """Prompt for answering a student's inline chat question."""
    chunks_text = _format_chunks(lecture_chunks)

    return f"""\
The student asked a question during a tutoring session on "{current_concept}".

Student's question: "{student_message}"

Assessment context: {assessment_context}

Relevant lecture content:
{chunks_text}

Answer the question directly and concisely (100-200 words).
- Ground your answer in the lecture content.
- Connect to the current concept or upcoming assessment when relevant.
- If the question is tangential, answer briefly and redirect to the main topic.
- Use markdown for formatting."""


# ---------------------------------------------------------------------------
# Diagnostic questions
# ---------------------------------------------------------------------------


def get_diagnostic_questions_prompt(
    concepts: list[dict],
    assessment_context: str,
) -> str:
    """Prompt to generate 5-8 diagnostic questions across priority concepts."""
    concepts_str = json.dumps(concepts, indent=2, default=str)

    return f"""\
Generate 5-8 diagnostic questions to assess a student's understanding before a study session.

Assessment context:
{assessment_context}

Concepts to assess (ordered by priority):
{concepts_str}

Requirements:
- Mix question types: ~50% MCQ, ~25% short_answer, ~25% true_false or fill_in_blank
- Medium difficulty — we're assessing, not challenging
- Order from easiest to hardest concept
- Each question must include its grading rubric
- Cover the highest-priority concepts first, but spread across at least 3-4 concepts

Respond ONLY with valid JSON, no markdown fences or preamble:
[
  {{
    "question_text": "the question",
    "question_type": "mcq | short_answer | true_false | fill_in_blank",
    "concept_title": "which concept this tests",
    "options": ["A) ...", "B) ...", "C) ...", "D) ..."],
    "correct_answer": "the correct answer",
    "acceptable_answers": ["alt answer 1"],
    "rubric": {{
      "must_mention": ["key point"],
      "partial_credit_for": ["related idea"],
      "common_misconceptions": [
        {{"misconception": "what students often think", "why_wrong": "brief explanation"}}
      ],
      "model_answer": "ideal answer",
      "misconception_detection": {{"if_mentions_X": "likely confused about Y"}}
    }}
  }}
]

- "options" only for MCQ, null otherwise.
- "acceptable_answers" only for fill_in_blank, null otherwise."""


# ---------------------------------------------------------------------------
# Diagnostic analysis
# ---------------------------------------------------------------------------


def get_diagnostic_analysis_prompt(
    questions_and_results: list[dict],
) -> str:
    """Prompt to analyze diagnostic results and identify gaps."""
    results_str = json.dumps(questions_and_results, indent=2, default=str)

    return f"""\
Analyze this student's diagnostic quiz results.

Questions and results:
{results_str}

Provide a structured analysis of the student's understanding.

Respond ONLY with valid JSON, no markdown fences or preamble:
{{
  "concept_results": [
    {{
      "concept_title": "Concept Name",
      "questions_asked": 2,
      "questions_correct": 1,
      "estimated_mastery": 0.5,
      "identified_gaps": ["specific gap or misconception"],
      "strengths": ["what they demonstrated understanding of"]
    }}
  ],
  "identified_gaps": ["gap 1 — what topic and why", "gap 2"],
  "recommended_focus": [
    {{
      "concept_title": "Concept to focus on",
      "reason": "why this should be prioritized",
      "teaching_approach": "foundational | application | synthesis"
    }}
  ],
  "overall_readiness": "low | medium | high",
  "summary": "2-3 sentence natural language summary of the student's preparedness"
}}"""


# ---------------------------------------------------------------------------
# Session summary
# ---------------------------------------------------------------------------


def get_session_summary_prompt(
    session_data: dict,
) -> str:
    """Prompt to generate a natural-language session summary."""
    data_str = json.dumps(session_data, indent=2, default=str)

    return f"""\
Generate a brief summary of this tutoring session for the student's records.

Session data:
{data_str}

Write a natural-language summary (3-5 sentences) that includes:
- What topics were covered
- How the student performed (specific numbers: X/Y correct)
- Key takeaways or misconceptions addressed
- What to focus on next time

Be direct and specific. No generic encouragement. Reference actual concepts and performance."""


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _format_chunks(chunks: list[dict]) -> str:
    """Format lecture chunks for inclusion in prompts."""
    if not chunks:
        return "(No lecture content available)"

    parts = []
    for i, chunk in enumerate(chunks):
        label_parts = [f"Source {i + 1}"]
        if chunk.get("lecture_title"):
            label_parts.append(f"Lecture: {chunk['lecture_title']}")
        if chunk.get("start_time") is not None:
            mins = int(chunk["start_time"] // 60)
            secs = int(chunk["start_time"] % 60)
            label_parts.append(f"Time: {mins}:{secs:02d}")
        header = " | ".join(label_parts)
        parts.append(f"[{header}]\n{chunk['content']}")

    return "\n\n---\n\n".join(parts)
