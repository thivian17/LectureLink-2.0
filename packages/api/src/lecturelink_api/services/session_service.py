"""Database-backed ADK SessionService using Supabase/PostgreSQL.

Stores full session state (including events) as JSONB in the ``adk_sessions``
table.  Falls back gracefully on serialization errors so an agent run is never
blocked by persistence issues.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Optional
from uuid import uuid4

from google.adk.sessions import Session
from google.adk.sessions.base_session_service import (
    BaseSessionService,
    GetSessionConfig,
    ListSessionsResponse,
)

logger = logging.getLogger(__name__)


class DatabaseSessionService(BaseSessionService):
    """ADK SessionService backed by the ``adk_sessions`` table in Supabase."""

    def __init__(self, supabase_client: Any) -> None:
        self._sb = supabase_client

    # ------------------------------------------------------------------
    # Abstract method implementations
    # ------------------------------------------------------------------

    async def create_session(
        self,
        *,
        app_name: str,
        user_id: str,
        state: Optional[dict[str, Any]] = None,
        session_id: Optional[str] = None,
    ) -> Session:
        sid = session_id or str(uuid4())
        now = datetime.now(timezone.utc)

        session = Session(
            id=sid,
            app_name=app_name,
            user_id=user_id,
            state=state or {},
        )

        self._sb.table("adk_sessions").insert({
            "id": sid,
            "user_id": user_id,
            "agent_name": app_name,
            "state": session.model_dump(mode="json"),
            "created_at": now.isoformat(),
            "updated_at": now.isoformat(),
            "expires_at": (now + timedelta(hours=24)).isoformat(),
        }).execute()

        return session

    async def get_session(
        self,
        *,
        app_name: str,
        user_id: str,
        session_id: str,
        config: Optional[GetSessionConfig] = None,
    ) -> Optional[Session]:
        result = (
            self._sb.table("adk_sessions")
            .select("*")
            .eq("id", session_id)
            .execute()
        )
        if not result.data:
            return None

        row = result.data[0]

        # Check expiration
        expires_at = row.get("expires_at")
        if expires_at:
            exp = datetime.fromisoformat(str(expires_at))
            if exp.tzinfo is None:
                exp = exp.replace(tzinfo=timezone.utc)
            if exp < datetime.now(timezone.utc):
                return None

        # Reconstruct Session from stored JSONB
        session = Session.model_validate(row["state"])

        # Apply optional filters
        if config:
            if config.num_recent_events is not None:
                session.events = session.events[-config.num_recent_events:]
            if config.after_timestamp is not None:
                session.events = [
                    e for e in session.events
                    if getattr(e, "timestamp", None)
                    and e.timestamp > config.after_timestamp
                ]

        # Touch updated_at
        self._sb.table("adk_sessions").update({
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }).eq("id", session_id).execute()

        return session

    async def list_sessions(
        self,
        *,
        app_name: str,
        user_id: Optional[str] = None,
    ) -> ListSessionsResponse:
        query = (
            self._sb.table("adk_sessions")
            .select("*")
            .eq("agent_name", app_name)
            .gte("expires_at", datetime.now(timezone.utc).isoformat())
            .order("updated_at", desc=True)
        )
        if user_id is not None:
            query = query.eq("user_id", user_id)

        result = query.execute()

        sessions: list[Session] = []
        for row in result.data or []:
            try:
                data = row["state"]
                # Return sessions without events (ADK convention for list)
                sessions.append(Session(
                    id=data["id"],
                    app_name=data["app_name"],
                    user_id=data["user_id"],
                    state=data.get("state", {}),
                ))
            except Exception:
                logger.warning("Skipping malformed session row %s", row.get("id"))

        return ListSessionsResponse(sessions=sessions)

    async def delete_session(
        self,
        *,
        app_name: str,
        user_id: str,
        session_id: str,
    ) -> None:
        (
            self._sb.table("adk_sessions")
            .delete()
            .eq("id", session_id)
            .execute()
        )

    # ------------------------------------------------------------------
    # Event persistence (override base to save after each event)
    # ------------------------------------------------------------------

    async def append_event(self, session, event):
        """Append event via base class, then persist the updated session."""
        event = await super().append_event(session, event)
        try:
            self._sb.table("adk_sessions").update({
                "state": session.model_dump(mode="json"),
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }).eq("id", session.id).execute()
        except Exception:
            logger.warning(
                "Failed to persist session %s after event", session.id, exc_info=True,
            )
        return event


# ---------------------------------------------------------------------------
# Cleanup
# ---------------------------------------------------------------------------


def cleanup_expired_sessions(supabase_client: Any) -> int:
    """Delete expired ADK sessions. Returns count of deleted rows."""
    now = datetime.now(timezone.utc).isoformat()
    result = (
        supabase_client.table("adk_sessions")
        .delete()
        .lt("expires_at", now)
        .execute()
    )
    count = len(result.data) if result.data else 0
    logger.info("Cleaned up %d expired ADK sessions", count)
    return count
