"""RAG answer generation — retrieves lecture chunks and generates grounded answers."""

from __future__ import annotations

import json
import logging

from .genai_client import get_genai_client as _get_client
from .search import format_chunks_for_context, search_lectures

logger = logging.getLogger(__name__)

RAG_MODEL = "gemini-2.5-flash"

RAG_SYSTEM_PROMPT = """You are a helpful study assistant answering questions about lecture content.

You will be given:
1. A student's question
2. Relevant lecture chunks with source information
3. The course name for context

Rules:
- ONLY answer based on the provided lecture chunks
- If the answer isn't in the provided content, say "I couldn't find information about this in \
your lectures" — do NOT make up an answer
- Cite sources using [Source N] format matching the source labels provided
- Explain concepts at the level appropriate for this course
- If multiple chunks address the question, synthesize them into a coherent answer
- Use examples from the lectures when available
- Keep answers concise but complete (2-4 paragraphs max)
- At the end, suggest 2-3 follow-up questions the student might want to explore

Output as JSON:
{
    "answer": "Your detailed answer with [Source N] citations...",
    "confidence": 0.0-1.0,
    "cited_sources": [1, 3, 5],
    "follow_up_suggestions": [
        "How does this relate to...",
        "What are the implications of...",
        "Can you explain the difference between..."
    ]
}"""


async def ask_lecture_question(
    supabase,
    course_id: str,
    question: str,
    lecture_ids: list[str] | None = None,
    course_name: str = "",
    user_id: str | None = None,
) -> dict:
    """Answer a student's question using RAG over lecture content.

    Args:
        supabase: Supabase client
        course_id: Course to search within
        question: Student's question
        lecture_ids: Optional filter to specific lectures
        course_name: For context in the prompt
        user_id: For RLS

    Returns:
        dict with: answer, confidence, source_chunks, follow_up_suggestions
    """
    # 1. Retrieve relevant chunks
    chunks = await search_lectures(
        supabase=supabase,
        course_id=course_id,
        query=question,
        lecture_ids=lecture_ids,
        limit=8,
        user_id=user_id,
    )

    if not chunks:
        return {
            "answer": (
                "I couldn't find any relevant lecture content to answer this question. "
                "Make sure you've uploaded and processed lectures for this course."
            ),
            "confidence": 0.0,
            "source_chunks": [],
            "follow_up_suggestions": [],
        }

    # 2. Format context
    context = format_chunks_for_context(chunks)

    # 3. Build prompt
    user_prompt = f"""Course: {course_name}

Question: {question}

Lecture Content:
{context}"""

    # 4. Generate answer
    try:
        response = await _get_client().aio.models.generate_content(
            model=RAG_MODEL,
            contents=user_prompt,
            config={
                "system_instruction": RAG_SYSTEM_PROMPT,
                "temperature": 0.3,
                "response_mime_type": "application/json",
            },
        )

        result = json.loads(response.text)

        # 5. Map cited sources back to chunk details
        cited_indices = result.get("cited_sources", [])
        source_chunks = []
        for idx in cited_indices:
            if 1 <= idx <= len(chunks):
                chunk = chunks[idx - 1]  # 1-indexed
                source_chunks.append(
                    {
                        "chunk_id": chunk["id"],
                        "content": chunk["content"][:200],  # Preview only
                        "lecture_title": chunk["lecture_title"],
                        "start_time": chunk.get("start_time"),
                        "end_time": chunk.get("end_time"),
                        "slide_number": chunk.get("slide_number"),
                    }
                )

        # If model didn't specify cited_sources, include all chunks
        if not source_chunks:
            source_chunks = [
                {
                    "chunk_id": c["id"],
                    "content": c["content"][:200],
                    "lecture_title": c["lecture_title"],
                    "start_time": c.get("start_time"),
                    "end_time": c.get("end_time"),
                    "slide_number": c.get("slide_number"),
                }
                for c in chunks[:5]
            ]

        return {
            "answer": result.get("answer", "Unable to generate answer."),
            "confidence": min(1.0, max(0.0, result.get("confidence", 0.5))),
            "source_chunks": source_chunks,
            "follow_up_suggestions": result.get("follow_up_suggestions", [])[:3],
        }

    except json.JSONDecodeError:
        # If model returns non-JSON, use the raw text as the answer
        logger.warning("RAG response was not valid JSON, using raw text")
        return {
            "answer": response.text,
            "confidence": 0.5,
            "source_chunks": [
                {
                    "chunk_id": c["id"],
                    "content": c["content"][:200],
                    "lecture_title": c["lecture_title"],
                    "start_time": c.get("start_time"),
                    "end_time": c.get("end_time"),
                    "slide_number": c.get("slide_number"),
                }
                for c in chunks[:5]
            ],
            "follow_up_suggestions": [],
        }
    except Exception as e:
        logger.error(f"RAG answer generation failed: {e}")
        raise
