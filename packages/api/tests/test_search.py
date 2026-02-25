"""Tests for hybrid search wrapper and helper functions."""

from __future__ import annotations


class TestSearchLectures:
    """Test hybrid search wrapper."""

    async def test_returns_results_with_correct_fields(self, supabase_mock, mock_genai):
        """Results should include chunk_id, lecture_title, content, score."""
        from lecturelink_api.services.search import search_lectures

        # Setup mock to return search results
        supabase_mock.rpc.return_value.execute.return_value.data = [
            {
                "id": "chunk-1",
                "lecture_id": "lec-1",
                "content": "The first law of thermodynamics...",
                "start_time": 120.0,
                "end_time": 135.0,
                "slide_number": 3,
                "rrf_score": 0.85,
                "metadata": {"source": "aligned"},
            }
        ]
        supabase_mock.table.return_value.select.return_value.in_.return_value.execute.return_value.data = [
            {"id": "lec-1", "title": "Lecture 5: Thermodynamics"}
        ]

        results = await search_lectures(supabase_mock, "course-1", "first law")
        assert len(results) == 1
        assert results[0]["chunk_id"] == "chunk-1"
        assert results[0]["lecture_title"] == "Lecture 5: Thermodynamics"
        assert results[0]["score"] == 0.85

    async def test_empty_results_returns_empty_list(self, supabase_mock, mock_genai):
        from lecturelink_api.services.search import search_lectures

        supabase_mock.rpc.return_value.execute.return_value.data = []

        results = await search_lectures(supabase_mock, "course-1", "nonexistent topic")
        assert results == []

    async def test_lecture_filter_passed_to_rpc(self, supabase_mock, mock_genai):
        """When lecture_ids provided, they should be passed to the SQL function."""
        from lecturelink_api.services.search import search_lectures

        supabase_mock.rpc.return_value.execute.return_value.data = []

        await search_lectures(
            supabase_mock, "course-1", "query", lecture_ids=["lec-1", "lec-2"]
        )

        call_args = supabase_mock.rpc.call_args
        params = call_args[0][1] if len(call_args[0]) > 1 else call_args.kwargs
        assert params.get("p_lecture_ids") == ["lec-1", "lec-2"]

    async def test_respects_limit_parameter(self, supabase_mock, mock_genai):
        from lecturelink_api.services.search import search_lectures

        supabase_mock.rpc.return_value.execute.return_value.data = []

        await search_lectures(supabase_mock, "course-1", "query", limit=5)

        call_args = supabase_mock.rpc.call_args
        params = call_args[0][1] if len(call_args[0]) > 1 else call_args.kwargs
        assert params.get("p_limit") == 5

    async def test_missing_lecture_title_shows_unknown(self, supabase_mock, mock_genai):
        """When lecture title lookup fails, show 'Unknown'."""
        from lecturelink_api.services.search import search_lectures

        supabase_mock.rpc.return_value.execute.return_value.data = [
            {
                "id": "chunk-1",
                "lecture_id": "lec-missing",
                "content": "Some content",
                "rrf_score": 0.5,
            }
        ]
        # Return empty lecture list (title not found)
        supabase_mock.table.return_value.select.return_value.in_.return_value.execute.return_value.data = []

        results = await search_lectures(supabase_mock, "course-1", "query")
        assert results[0]["lecture_title"] == "Unknown"


class TestHighlightSearchTerms:
    """Test search term highlighting."""

    def test_highlights_matching_terms(self):
        from lecturelink_api.services.search import highlight_search_terms

        result = highlight_search_terms(
            "The first law of thermodynamics states...", "thermodynamics law"
        )
        assert "<mark>" in result
        assert "thermodynamics" in result.lower()

    def test_truncates_long_content(self):
        from lecturelink_api.services.search import highlight_search_terms

        long_text = "word " * 200
        result = highlight_search_terms(long_text, "word", max_length=100)
        assert len(result) < len(long_text)

    def test_handles_empty_query(self):
        from lecturelink_api.services.search import highlight_search_terms

        result = highlight_search_terms("Some content here", "")
        assert "Some content" in result

    def test_case_insensitive_highlighting(self):
        from lecturelink_api.services.search import highlight_search_terms

        result = highlight_search_terms("THERMODYNAMICS is important", "thermodynamics")
        assert "<mark>THERMODYNAMICS</mark>" in result

    def test_short_query_terms_ignored(self):
        """Terms <= 2 chars should be ignored (stopwords like 'is', 'a')."""
        from lecturelink_api.services.search import highlight_search_terms

        result = highlight_search_terms("A is the answer", "a is")
        # No highlighting since all terms are <= 2 chars
        assert "<mark>" not in result


class TestFormatChunksForContext:
    """Test context formatting for LLM."""

    def test_formats_with_source_labels(self):
        from lecturelink_api.services.search import format_chunks_for_context

        chunks = [
            {
                "lecture_title": "Lecture 5",
                "content": "The first law states...",
                "start_time": 120.0,
                "slide_number": 3,
            }
        ]
        result = format_chunks_for_context(chunks)
        assert "Source 1" in result
        assert "Lecture 5" in result
        assert "2:00" in result  # 120 seconds = 2:00
        assert "Slide 3" in result

    def test_respects_token_budget(self):
        from lecturelink_api.services.search import format_chunks_for_context

        chunks = [
            {"lecture_title": f"Lec {i}", "content": "x" * 1000}
            for i in range(20)
        ]
        result = format_chunks_for_context(chunks, max_tokens=2000)
        # Should not include all 20 chunks
        assert result.count("Source") < 20

    def test_empty_chunks_returns_empty(self):
        from lecturelink_api.services.search import format_chunks_for_context

        assert format_chunks_for_context([]) == ""

    def test_no_timestamp_when_missing(self):
        from lecturelink_api.services.search import format_chunks_for_context

        chunks = [
            {
                "lecture_title": "Lecture 1",
                "content": "Content here",
                "start_time": None,
                "slide_number": None,
            }
        ]
        result = format_chunks_for_context(chunks)
        assert "Time:" not in result
        assert "Slide" not in result
