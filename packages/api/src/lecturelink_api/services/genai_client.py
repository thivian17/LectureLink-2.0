"""Shared, loop-aware Gemini client singleton.

Every service that needs a ``google.genai.Client`` should import
``get_genai_client`` from here instead of creating its own singleton.

The client is automatically recreated when the running asyncio event
loop changes (e.g. after background processing on a temporary loop),
preventing the ``RuntimeError: Event loop is closed`` errors that
occur when httpx connection pools reference a stale loop.
"""

from __future__ import annotations

import asyncio
import logging
import threading

from google import genai

logger = logging.getLogger(__name__)

_client: genai.Client | None = None
_client_lock = threading.Lock()
_client_loop_id: int | None = None
# Keep references to replaced clients so their __del__ / aclose()
# finalizers don't fire on a closed event loop during garbage collection.
_retired_clients: list[genai.Client] = []


def get_genai_client() -> genai.Client:
    """Return a loop-aware Gemini client singleton.

    Thread-safe.  Recreates the client when called from a different
    event loop than the one it was originally created on.
    """
    global _client, _client_loop_id

    try:
        loop_id = id(asyncio.get_running_loop())
    except RuntimeError:
        loop_id = None

    need_new = _client is None or (
        loop_id is not None and loop_id != _client_loop_id
    )

    if need_new:
        with _client_lock:
            need_new = _client is None or (
                loop_id is not None and loop_id != _client_loop_id
            )
            if need_new:
                if _client is not None:
                    _retired_clients.append(_client)
                _client = genai.Client()
                _client_loop_id = loop_id

    return _client


def reset_genai_client() -> None:
    """Force-recreate the client on next call (used after loop errors)."""
    global _client, _client_loop_id
    with _client_lock:
        if _client is not None:
            _retired_clients.append(_client)
        _client = None
        _client_loop_id = None
