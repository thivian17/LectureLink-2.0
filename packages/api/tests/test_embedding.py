"""Tests for query and batch embedding functions."""

from __future__ import annotations


class TestEmbedQuery:
    """Test query embedding function."""

    async def test_returns_768_dimensions(self, mock_genai):
        """Embedding vector has correct dimensions."""
        from lecturelink_api.services.embedding import embed_query

        result = await embed_query("What is thermodynamics?")
        assert len(result) == 768

    async def test_uses_retrieval_query_task_type(self, mock_genai):
        """Must use RETRIEVAL_QUERY, not RETRIEVAL_DOCUMENT."""
        from lecturelink_api.services.embedding import embed_query

        await embed_query("test query")
        call_args = mock_genai.aio.models.embed_content.call_args
        assert call_args.kwargs["config"]["task_type"] == "RETRIEVAL_QUERY"

    async def test_different_queries_produce_different_calls(self, mock_genai):
        """Distinct queries should produce distinct API calls."""
        from lecturelink_api.services.embedding import embed_query

        await embed_query("What is entropy?")
        await embed_query("How do plants grow?")
        assert mock_genai.aio.models.embed_content.call_count == 2


class TestEmbedTexts:
    """Test batch embedding function."""

    async def test_empty_list_returns_empty(self, mock_genai):
        from lecturelink_api.services.embedding import embed_texts

        result = await embed_texts([])
        assert result == []

    async def test_batch_processing(self, mock_genai):
        """Should split into batches of 100."""
        from lecturelink_api.services.embedding import embed_texts

        texts = [f"text {i}" for i in range(250)]
        result = await embed_texts(texts)
        assert len(result) == 250
        # Should have made 3 API calls (100 + 100 + 50)
        assert mock_genai.aio.models.embed_content.call_count == 3

    async def test_uses_specified_task_type(self, mock_genai):
        from lecturelink_api.services.embedding import embed_texts

        await embed_texts(["test"], task_type="SEMANTIC_SIMILARITY")
        call_args = mock_genai.aio.models.embed_content.call_args
        assert call_args.kwargs["config"]["task_type"] == "SEMANTIC_SIMILARITY"

    async def test_default_task_type_is_retrieval_document(self, mock_genai):
        from lecturelink_api.services.embedding import embed_texts

        await embed_texts(["test"])
        call_args = mock_genai.aio.models.embed_content.call_args
        assert call_args.kwargs["config"]["task_type"] == "RETRIEVAL_DOCUMENT"

    async def test_single_text_returns_single_embedding(self, mock_genai):
        from lecturelink_api.services.embedding import embed_texts

        result = await embed_texts(["single text"])
        assert len(result) == 1
        assert len(result[0]) == 768
