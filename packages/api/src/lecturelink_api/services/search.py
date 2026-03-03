"""Hybrid search wrapper around the SQL hybrid_search RPC function."""

from __future__ import annotations

import logging
import re

from .embedding import embed_query

logger = logging.getLogger(__name__)


async def search_lectures(
    supabase,
    course_id: str,
    query: str,
    lecture_ids: list[str] | None = None,
    limit: int = 8,
    user_id: str | None = None,
) -> list[dict]:
    """Search lecture content using hybrid search (vector + full-text).

    Calls the ``hybrid_search`` PostgreSQL function which combines vector
    similarity with BM25 full-text scoring via Reciprocal Rank Fusion.

    Args:
        supabase: Supabase client
        course_id: Filter to specific course
        query: Natural language search query
        lecture_ids: Optional filter to specific lectures
        limit: Max results to return (default 8)
        user_id: For RLS verification

    Returns:
        List of dicts with: chunk_id, lecture_id, lecture_title, content,
        start_time, end_time, slide_number, score, metadata
    """
    # 1. Generate query embedding
    if not query or not query.strip():
        return []

    query_embedding = await embed_query(query)

    # 2. Call the SQL hybrid_search function via RPC
    params: dict = {
        "p_query_embedding": query_embedding,
        "p_query_text": query,
        "p_course_id": course_id,
        "p_limit": limit,
    }

    # Add optional lecture filter
    if lecture_ids:
        params["p_lecture_ids"] = lecture_ids

    result = supabase.rpc("hybrid_search", params).execute()

    if not result.data:
        return []

    # 3. Enrich with lecture titles
    lecture_id_set = {r["lecture_id"] for r in result.data}
    if lecture_id_set:
        lectures = (
            supabase.table("lectures")
            .select("id, title")
            .in_("id", list(lecture_id_set))
            .execute()
        )
        title_map = {lec["id"]: lec["title"] for lec in lectures.data}
    else:
        title_map = {}

    # 4. Format results
    chunks = []
    for r in result.data:
        chunks.append(
            {
                "chunk_id": r.get("chunk_id", r.get("id")),
                "lecture_id": r["lecture_id"],
                "lecture_title": title_map.get(r["lecture_id"], "Unknown"),
                "content": r["content"],
                "start_time": r.get("start_time"),
                "end_time": r.get("end_time"),
                "slide_number": r.get("slide_number"),
                "score": r.get("combined_score", r.get("rrf_score", r.get("score", 0.0))),
                "metadata": r.get("metadata", {}),
            }
        )

    logger.debug("search_lectures: %d results for %r", len(chunks), query[:60])
    return chunks


def highlight_search_terms(content: str, query: str, max_length: int = 300) -> str:
    """Create a highlighted snippet for search results.

    Finds the most relevant section of content and wraps matching
    terms in <mark> tags for frontend highlighting.

    Args:
        content: Full chunk text
        query: Search query
        max_length: Max snippet length

    Returns:
        HTML string with <mark>matched terms</mark>
    """
    query_terms = [t.lower() for t in query.split() if len(t) > 2]

    if not query_terms:
        return content[:max_length] + ("..." if len(content) > max_length else "")

    # Find the best window position (where most terms cluster)
    text_lower = content.lower()
    best_pos = 0
    best_score = 0
    window = max_length

    for i in range(0, max(1, len(content) - window), 20):
        window_text = text_lower[i : i + window]
        score = sum(1 for term in query_terms if term in window_text)
        if score > best_score:
            best_score = score
            best_pos = i

    # Extract snippet
    start = max(0, best_pos)
    snippet = content[start : start + max_length]

    if start > 0:
        snippet = "..." + snippet
    if start + max_length < len(content):
        snippet = snippet + "..."

    # Highlight terms
    for term in query_terms:
        pattern = re.compile(re.escape(term), re.IGNORECASE)
        snippet = pattern.sub(lambda m: f"<mark>{m.group()}</mark>", snippet)

    return snippet


def format_chunks_for_context(chunks: list[dict], max_tokens: int = 6000) -> str:
    """Format retrieved chunks into a context string for the LLM.

    Used by both RAG Q&A and Quiz Generator to present source material.

    Args:
        chunks: Search results from search_lectures()
        max_tokens: Approximate token budget (chars * 0.67)

    Returns:
        Formatted context string with source labels
    """
    if not chunks:
        return ""

    context_parts: list[str] = []
    total_chars = 0
    char_budget = int(max_tokens / 0.67)  # rough chars-to-tokens

    for i, chunk in enumerate(chunks):
        # Build source label
        source_parts = [f"Source {i + 1}"]
        source_parts.append(f"Lecture: {chunk['lecture_title']}")
        if chunk.get("start_time") is not None:
            mins = int(chunk["start_time"] // 60)
            secs = int(chunk["start_time"] % 60)
            source_parts.append(f"Time: {mins}:{secs:02d}")
        if chunk.get("slide_number"):
            source_parts.append(f"Slide {chunk['slide_number']}")

        header = " | ".join(source_parts)
        entry = f"[{header}]\n{chunk['content']}\n"

        if total_chars + len(entry) > char_budget:
            break

        context_parts.append(entry)
        total_chars += len(entry)

    return "\n---\n".join(context_parts)
