"""Test chunk reference validator."""

from __future__ import annotations

from unittest.mock import MagicMock

from lecturelink_api.utils.chunk_validator import validate_chunk_references


def _mock_supabase(valid_ids: list[str]):
    """Create mock returning only the given valid IDs from the DB."""
    client = MagicMock()
    data = [{"id": vid} for vid in valid_ids]
    chain = client.table.return_value.select.return_value.in_.return_value
    chain.execute.return_value = MagicMock(data=data)
    return client


class TestValidateChunkReferences:
    def test_all_valid(self):
        ids = ["c1", "c2", "c3"]
        sb = _mock_supabase(ids)
        result = validate_chunk_references(sb, ids)
        assert result["valid_ids"] == ids
        assert result["has_orphans"] is False

    def test_some_orphaned(self):
        sb = _mock_supabase(["c1"])
        result = validate_chunk_references(sb, ["c1", "c2", "c3"])
        assert result["valid_ids"] == ["c1"]
        assert result["has_orphans"] is True

    def test_empty_list(self):
        sb = MagicMock()
        result = validate_chunk_references(sb, [])
        assert result["valid_ids"] == []
        assert result["has_orphans"] is False

    def test_all_orphaned(self):
        sb = _mock_supabase([])
        result = validate_chunk_references(sb, ["c1", "c2"])
        assert result["valid_ids"] == []
        assert result["has_orphans"] is True
