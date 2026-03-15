"""Tests for lecture storage service."""

from __future__ import annotations

from unittest.mock import MagicMock

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
    """Tests for legacy cleanup path (pre-migration, RPC unavailable)."""

    def test_deletes_in_correct_fk_order(self):
        """Deletion order: concept_assessment_links -> concepts -> lecture_chunks."""
        concept_ids = [{"id": "c1"}, {"id": "c2"}]
        sb = _mock_supabase(select_data=concept_ids)
        # Force legacy path by making the RPC raise
        sb.rpc.return_value.execute.side_effect = Exception("RPC not found")

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
        # Force legacy path by making the RPC raise
        sb.rpc.return_value.execute.side_effect = Exception("RPC not found")

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


# ---------------------------------------------------------------------------
# cleanup_lecture_data — registry-aware (concept_lectures junction)
# ---------------------------------------------------------------------------


def _mock_registry_supabase(orphan_ids=None, rpc_raises=False):
    """Build a mock Supabase client supporting the registry cleanup path."""
    client = MagicMock()

    # rpc("get_orphan_concepts_for_lecture", ...).execute()
    rpc_chain = MagicMock()
    if rpc_raises:
        rpc_chain.execute.side_effect = Exception("RPC not found")
    else:
        rpc_data = [{"id": oid} for oid in (orphan_ids or [])]
        rpc_chain.execute.return_value = MagicMock(data=rpc_data)
    client.rpc.return_value = rpc_chain

    # delete().eq().execute() and delete().in_().execute()
    delete_chain = MagicMock()
    delete_chain.execute.return_value = MagicMock(data=[])
    delete_chain.eq.return_value = delete_chain
    delete_chain.in_.return_value = delete_chain
    client.table.return_value.delete.return_value = delete_chain

    # select().eq().execute() (for legacy fallback)
    select_chain = MagicMock()
    select_chain.execute.return_value = MagicMock(data=[])
    select_chain.eq.return_value = select_chain
    client.table.return_value.select.return_value = select_chain

    return client


class TestCleanupWithRegistry:
    def test_orphan_concepts_deleted_shared_survive(self):
        """Only orphan concepts are deleted; shared concepts stay."""
        sb = _mock_registry_supabase(orphan_ids=["orphan-1"])

        table_calls = []
        original_table = sb.table

        def tracking_table(name):
            table_calls.append(name)
            return original_table(name)

        sb.table = tracking_table

        cleanup_lecture_data(sb, LECTURE_ID)

        # RPC was called
        sb.rpc.assert_called_once_with(
            "get_orphan_concepts_for_lecture",
            {"p_lecture_id": LECTURE_ID},
        )

        # concept_lectures removed, then orphan links + concepts, then chunks
        assert table_calls == [
            "concept_lectures",
            "concept_assessment_links",
            "concepts",
            "lecture_chunks",
        ]

    def test_concept_lectures_entries_deleted(self):
        """Junction entries for the lecture are always removed."""
        sb = _mock_registry_supabase(orphan_ids=[])

        cleanup_lecture_data(sb, LECTURE_ID)

        # concept_lectures.delete().eq("lecture_id", ...) was called
        sb.table.assert_any_call("concept_lectures")
        sb.table.return_value.delete.return_value.eq.assert_called_with(
            "lecture_id", LECTURE_ID,
        )

    def test_assessment_links_deleted_for_orphans(self):
        """concept_assessment_links for orphan concepts are cleaned up."""
        sb = _mock_registry_supabase(orphan_ids=["o1", "o2"])

        cleanup_lecture_data(sb, LECTURE_ID)

        sb.table.assert_any_call("concept_assessment_links")
        sb.table.return_value.delete.return_value.in_.assert_any_call(
            "concept_id", ["o1", "o2"],
        )

    def test_chunks_always_deleted(self):
        """lecture_chunks are always deleted regardless of orphan count."""
        sb = _mock_registry_supabase(orphan_ids=[])

        cleanup_lecture_data(sb, LECTURE_ID)

        sb.table.assert_any_call("lecture_chunks")

    def test_no_orphans_skips_concept_deletion(self):
        """When there are no orphans, concept tables are not touched."""
        sb = _mock_registry_supabase(orphan_ids=[])

        table_calls = []
        original_table = sb.table

        def tracking_table(name):
            table_calls.append(name)
            return original_table(name)

        sb.table = tracking_table

        cleanup_lecture_data(sb, LECTURE_ID)

        assert "concept_assessment_links" not in table_calls
        assert table_calls == ["concept_lectures", "lecture_chunks"]

    def test_rpc_unavailable_falls_back_to_legacy(self):
        """When the RPC doesn't exist, legacy cleanup runs instead."""
        sb = _mock_registry_supabase(rpc_raises=True)

        table_calls = []
        original_table = sb.table

        def tracking_table(name):
            table_calls.append(name)
            return original_table(name)

        sb.table = tracking_table

        cleanup_lecture_data(sb, LECTURE_ID)

        # Legacy path: select concepts, delete concepts, delete chunks
        # (no concept_assessment_links since select returns [])
        assert table_calls == ["concepts", "concepts", "lecture_chunks"]
        # concept_lectures should NOT appear (legacy path)
        assert "concept_lectures" not in table_calls
