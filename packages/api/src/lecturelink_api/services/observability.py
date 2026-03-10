"""Observability service -- Sentry, LangFuse, and PostHog clients.

Initialized once at application startup via init_observability().
All functions are no-ops if the corresponding secret is not configured,
so local development works without any observability keys.
"""

from __future__ import annotations

import logging
import os

logger = logging.getLogger(__name__)

_langfuse_client = None
_posthog_client = None
_sentry_initialized = False


def init_observability() -> None:
    """Initialize all observability clients. Call once at app startup."""
    global _sentry_initialized, _langfuse_client, _posthog_client

    # -- Sentry --
    try:
        from lecturelink_api.config.secrets import get_secret

        dsn = get_secret("SENTRY_DSN")
        if dsn:
            import sentry_sdk
            from sentry_sdk.integrations.asyncio import AsyncioIntegration
            from sentry_sdk.integrations.fastapi import FastApiIntegration

            sentry_sdk.init(
                dsn=dsn,
                environment=os.environ.get("ENVIRONMENT", "development"),
                integrations=[FastApiIntegration(), AsyncioIntegration()],
                traces_sample_rate=0.1,
                profiles_sample_rate=0.05,
            )
            _sentry_initialized = True
            logger.info("Sentry initialized")
    except Exception as e:
        logger.debug("Sentry not initialized: %s", e)

    # -- LangFuse --
    try:
        from lecturelink_api.config.secrets import get_secret

        secret_key = get_secret("LANGFUSE_SECRET_KEY")
        public_key = os.environ.get("LANGFUSE_PUBLIC_KEY", "")
        if secret_key and public_key:
            from langfuse import Langfuse

            _langfuse_client = Langfuse(
                secret_key=secret_key,
                public_key=public_key,
                host=os.environ.get(
                    "LANGFUSE_HOST", "https://cloud.langfuse.com"
                ),
            )
            logger.info("LangFuse initialized")
    except Exception as e:
        logger.debug("LangFuse not initialized: %s", e)

    # -- PostHog (server-side) --
    try:
        from lecturelink_api.config.secrets import get_secret

        api_key = get_secret("POSTHOG_API_KEY")
        if api_key:
            import posthog

            posthog.project_api_key = api_key
            posthog.host = "https://app.posthog.com"
            posthog.disabled = False
            _posthog_client = posthog
            logger.info("PostHog initialized")
    except Exception as e:
        logger.debug("PostHog not initialized: %s", e)


def get_langfuse():
    """Return the LangFuse client, or None if not configured."""
    return _langfuse_client


def track_event(
    user_id: str, event: str, properties: dict | None = None
) -> None:
    """Fire a PostHog analytics event. No-op if PostHog is not configured."""
    if _posthog_client is None:
        return
    try:
        _posthog_client.capture(
            distinct_id=user_id,
            event=event,
            properties=properties or {},
        )
    except Exception as e:
        logger.debug("PostHog track_event failed: %s", e)


def capture_exception(exc: Exception, context: dict | None = None) -> None:
    """Send an exception to Sentry. No-op if Sentry is not configured."""
    if not _sentry_initialized:
        return
    try:
        import sentry_sdk

        with sentry_sdk.push_scope() as scope:
            if context:
                for k, v in context.items():
                    scope.set_extra(k, v)
            sentry_sdk.capture_exception(exc)
    except Exception as e:
        logger.debug("Sentry capture_exception failed: %s", e)
