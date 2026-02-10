"""Tests for lecture storage service."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from lecturelink_api.services.lecture_storage import (
    cleanup_lecture_data,
    store_chunks,
    store_concepts,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

USER_ID = "11111111-1111-1111-1111-111111111111"
COURSE_ID = "22222222-2222-2222-2222-222222222222"
LECTURE_ID = "33333333-3333-3333-3333-333333333333"


def _mock_supabase(insert_data=None, select_data=None):
    """Build a mock Supabase client with chained sync methods."""
    client = MagicMock()

    # insert().execute()
    insert_result = MagicMock(data=insert_data or [])
    insert_chain = MagicMock()
    insert_chain.execute.return_value = insert_result
    client.table.return_value.insert.return_value = insert_chain

    # select().eq().execute()
    select_result = MagicMock(data=select_data or [])
    eq_chain = MagicMock()
    eq_chain.execute.return_value = select_result
    client.table.return_value.select.return_value.eq.return_value = eq_chain

    # delete().eq().execute()
    delete_eq_chain = MagicMock()
    delete_eq_chain.execute.return_value = MagicMock(data=[])
    client.table.return_value.delete.return_value.eq.return_value = delete_eq_chain

    # delete().in_().execute()
    delete_in_chain = MagicMock()
    delete_in_chain.execute.return_value = MagicMock(data=[])
    client.table.return_value.delete.return_value.in_.return_value = delete_in_chain

    return client


# ---------------------------------------------------------------------------
# store_chunks
# ---------------------------------------------------------------------------


class TestStoreChunks:
    def test_inserts_with_correct_fields_no_fts(self):
        stored = [{"id": "chunk-abc", "chunk_index": 0}]
        sb = _mock_supabase(insert_data=stored)

        chunks = [
            {
                "chunk_index": 0,
                "content": "Hello world.",
                "start_time": 0.0,
                "end_time": 15.0,
                "slide_number": 1,
                "embedding": [0.1] * 768,
                "metadata": {"source": "aligned"},
            },
        ]

        result = store_chunks(sb, LECTURE_ID, USER_ID, chunks)

        assert result == stored

        # Verify insert was called
        sb.table.assert_called_with("lecture_chunks")
        insert_call = sb.table.return_value.insert
        assert insert_call.called
        inserted_rows = insert_call.call_args[0][0]
        assert len(inserted_rows) == 1

        row = inserted_rows[0]
        assert row["lecture_id"] == LECTURE_ID
        assert row["user_id"] == USER_ID
        assert row["chunk_index"] == 0
        assert row["content"] == "Hello world."
        assert "fts" not in row  # CRITICAL: fts is GENERATED

    def test_empty_list_returns_empty(self):
        sb = _mock_supabase()
        result = store_chunks(sb, LECTURE_ID, USER_ID, [])
        assert result == []
        sb.table.return_value.insert.assert_not_called()


# ---------------------------------------------------------------------------
# store_concepts
# ---------------------------------------------------------------------------


class TestStoreConcepts:
    def test_inserts_with_all_required_fields(self):
        stored = [{"id": "concept-abc"}]
        sb = _mock_supabase(insert_data=stored)

        concepts = [
            {
                "title": "Entropy",
                "description": "Measure of disorder",
                "category": "concept",
                "difficulty_estimate": 0.6,
                "source_chunk_ids": ["chunk-0", "chunk-1"],
                "embedding": [0.2] * 768,
            },
        ]

        result = store_concepts(sb, LECTURE_ID, COURSE_ID, USER_ID, concepts)

        assert result == stored

        sb.table.assert_called_with("concepts")
        inserted_rows = sb.table.return_value.insert.call_args[0][0]
        row = inserted_rows[0]
        assert row["lecture_id"] == LECTURE_ID
        assert row["course_id"] == COURSE_ID
        assert row["user_id"] == USER_ID
        assert row["title"] == "Entropy"
        assert row["source_chunk_ids"] == ["chunk-0", "chunk-1"]

    def test_empty_list_returns_empty(self):
        sb = _mock_supabase()
        result = store_concepts(sb, LECTURE_ID, COURSE_ID, USER_ID, [])
        assert result == []
        sb.table.return_value.insert.assert_not_called()


# ---------------------------------------------------------------------------
# cleanup_lecture_data
# ---------------------------------------------------------------------------


class TestCleanupLectureData:
    def test_deletes_in_correct_fk_order(self):
        """Deletion order: concept_assessment_links -> concepts -> lecture_chunks."""
        concept_ids = [{"id": "c1"}, {"id": "c2"}]
        sb = _mock_supabase(select_data=concept_ids)

        # Track table call order
        table_calls = []
        original_table = sb.table

        def tracking_table(name):
            table_calls.append(name)
            return original_table(name)

        sb.table = tracking_table

        cleanup_lecture_data(sb, LECTURE_ID)

        # Verify order: first select concepts, then delete links, concepts, chunks
        assert table_calls == [
            "concepts",                  # SELECT concept IDs
            "concept_assessment_links",  # DELETE links
            "concepts",                  # DELETE concepts
            "lecture_chunks",            # DELETE chunks
        ]

    def test_no_concepts_skips_link_deletion(self):
        sb = _mock_supabase(select_data=[])

        table_calls = []
        original_table = sb.table

        def tracking_table(name):
            table_calls.append(name)
            return original_table(name)

        sb.table = tracking_table

        cleanup_lecture_data(sb, LECTURE_ID)

        # No concept_assessment_links deletion since no concepts
        assert "concept_assessment_links" not in table_calls
        assert table_calls == ["concepts", "concepts", "lecture_chunks"]
