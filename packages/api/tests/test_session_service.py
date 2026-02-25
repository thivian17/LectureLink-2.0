"""Tests for DatabaseSessionService and cleanup_expired_sessions."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock

import pytest
from google.adk.sessions import Session
from lecturelink_api.services.session_service import (
    DatabaseSessionService,
    cleanup_expired_sessions,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _utc_now() -> datetime:
    return datetime.now(UTC)


def _make_row(
    session_id: str = "sess-1",
    user_id: str = "user-1",
    agent_name: str = "test-app",
    *,
    expired: bool = False,
    state_override: dict | None = None,
) -> dict:
    """Build a mock adk_sessions row."""
    now = _utc_now()
    expires = now - timedelta(hours=1) if expired else now + timedelta(hours=23)
    state = state_override or Session(
        id=session_id,
        app_name=agent_name,
        user_id=user_id,
        state={"key": "value"},
    ).model_dump(mode="json")
    return {
        "id": session_id,
        "user_id": user_id,
        "agent_name": agent_name,
        "state": state,
        "created_at": now.isoformat(),
        "updated_at": now.isoformat(),
        "expires_at": expires.isoformat(),
    }


def _mock_supabase(select_data: list | None = None) -> MagicMock:
    """Create a mock Supabase client with chainable query builder."""
    sb = MagicMock()

    # select chain: .table().select().eq().gte().order().eq().execute()
    select_chain = MagicMock()
    select_chain.execute.return_value = MagicMock(data=select_data or [])
    select_chain.eq.return_value = select_chain
    select_chain.gte.return_value = select_chain
    select_chain.lt.return_value = select_chain
    select_chain.order.return_value = select_chain

    # insert chain
    insert_chain = MagicMock()
    insert_chain.execute.return_value = MagicMock(data=[{"id": "new"}])

    # update chain
    update_chain = MagicMock()
    update_chain.eq.return_value = update_chain
    update_chain.execute.return_value = MagicMock(data=[])

    # delete chain
    delete_chain = MagicMock()
    delete_chain.eq.return_value = delete_chain
    delete_chain.lt.return_value = delete_chain
    delete_chain.execute.return_value = MagicMock(data=[])

    table = MagicMock()
    table.select.return_value = select_chain
    table.insert.return_value = insert_chain
    table.update.return_value = update_chain
    table.delete.return_value = delete_chain
    sb.table.return_value = table

    return sb


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestCreateSession:
    @pytest.mark.asyncio
    async def test_returns_valid_session(self):
        sb = _mock_supabase()
        svc = DatabaseSessionService(sb)

        session = await svc.create_session(
            app_name="test-app",
            user_id="user-1",
            state={"foo": "bar"},
            session_id="custom-id",
        )

        assert isinstance(session, Session)
        assert session.id == "custom-id"
        assert session.app_name == "test-app"
        assert session.user_id == "user-1"
        assert session.state["foo"] == "bar"

        # Verify DB insert was called
        sb.table.assert_called_with("adk_sessions")
        sb.table.return_value.insert.assert_called_once()
        inserted = sb.table.return_value.insert.call_args[0][0]
        assert inserted["id"] == "custom-id"
        assert inserted["user_id"] == "user-1"
        assert inserted["agent_name"] == "test-app"
        assert "expires_at" in inserted

    @pytest.mark.asyncio
    async def test_generates_id_when_not_provided(self):
        sb = _mock_supabase()
        svc = DatabaseSessionService(sb)

        session = await svc.create_session(
            app_name="test-app",
            user_id="user-1",
        )

        assert session.id  # Should be a generated UUID string
        assert len(session.id) == 36  # UUID format


class TestGetSession:
    @pytest.mark.asyncio
    async def test_returns_none_for_nonexistent(self):
        sb = _mock_supabase(select_data=[])
        svc = DatabaseSessionService(sb)

        result = await svc.get_session(
            app_name="test-app",
            user_id="user-1",
            session_id="nonexistent",
        )

        assert result is None

    @pytest.mark.asyncio
    async def test_returns_none_for_expired(self):
        row = _make_row(expired=True)
        sb = _mock_supabase(select_data=[row])
        svc = DatabaseSessionService(sb)

        result = await svc.get_session(
            app_name="test-app",
            user_id="user-1",
            session_id="sess-1",
        )

        assert result is None

    @pytest.mark.asyncio
    async def test_returns_session_for_valid(self):
        row = _make_row()
        sb = _mock_supabase(select_data=[row])
        svc = DatabaseSessionService(sb)

        result = await svc.get_session(
            app_name="test-app",
            user_id="user-1",
            session_id="sess-1",
        )

        assert result is not None
        assert isinstance(result, Session)
        assert result.id == "sess-1"
        assert result.state["key"] == "value"

    @pytest.mark.asyncio
    async def test_touches_updated_at(self):
        row = _make_row()
        sb = _mock_supabase(select_data=[row])
        svc = DatabaseSessionService(sb)

        await svc.get_session(
            app_name="test-app",
            user_id="user-1",
            session_id="sess-1",
        )

        # Verify update was called to touch updated_at
        sb.table.return_value.update.assert_called_once()


class TestListSessions:
    @pytest.mark.asyncio
    async def test_returns_only_non_expired_for_user(self):
        rows = [
            _make_row(session_id="s1", user_id="user-1"),
            _make_row(session_id="s2", user_id="user-1"),
        ]
        sb = _mock_supabase(select_data=rows)
        svc = DatabaseSessionService(sb)

        response = await svc.list_sessions(
            app_name="test-app",
            user_id="user-1",
        )

        assert len(response.sessions) == 2
        assert all(isinstance(s, Session) for s in response.sessions)
        assert {s.id for s in response.sessions} == {"s1", "s2"}

    @pytest.mark.asyncio
    async def test_returns_empty_when_no_sessions(self):
        sb = _mock_supabase(select_data=[])
        svc = DatabaseSessionService(sb)

        response = await svc.list_sessions(
            app_name="test-app",
            user_id="user-1",
        )

        assert len(response.sessions) == 0


class TestDeleteSession:
    @pytest.mark.asyncio
    async def test_deletes_session(self):
        sb = _mock_supabase()
        svc = DatabaseSessionService(sb)

        await svc.delete_session(
            app_name="test-app",
            user_id="user-1",
            session_id="sess-1",
        )

        sb.table.assert_called_with("adk_sessions")
        sb.table.return_value.delete.assert_called_once()
        sb.table.return_value.delete.return_value.eq.assert_called_with("id", "sess-1")


class TestCleanupExpiredSessions:
    def test_deletes_expired_and_returns_count(self):
        sb = _mock_supabase()
        # Simulate 3 expired rows deleted
        delete_chain = sb.table.return_value.delete.return_value
        delete_chain.lt.return_value.execute.return_value = MagicMock(
            data=[{"id": "e1"}, {"id": "e2"}, {"id": "e3"}]
        )

        count = cleanup_expired_sessions(sb)

        assert count == 3
        sb.table.assert_called_with("adk_sessions")
        sb.table.return_value.delete.assert_called_once()

    def test_returns_zero_when_nothing_expired(self):
        sb = _mock_supabase()
        delete_chain = sb.table.return_value.delete.return_value
        delete_chain.lt.return_value.execute.return_value = MagicMock(data=[])

        count = cleanup_expired_sessions(sb)

        assert count == 0
