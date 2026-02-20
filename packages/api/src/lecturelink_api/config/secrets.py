"""Secret management — Google Secret Manager in production, env vars in development."""

from __future__ import annotations

import logging
import os

logger = logging.getLogger(__name__)

_secrets_cache: dict[str, str] = {}

# Secrets that should be loaded at startup
_SECRET_NAMES = [
    "SUPABASE_URL",
    "SUPABASE_SERVICE_KEY",
    "SUPABASE_ANON_KEY",
    "GOOGLE_API_KEY",
    "RESEND_API_KEY",
    "SENTRY_DSN",
    "POSTHOG_API_KEY",
    "LANGFUSE_SECRET_KEY",
    "INTERNAL_API_KEY",
]


def _get_secret_from_gsm(secret_id: str, project_id: str) -> str:
    """Fetch the latest version of a secret from Google Secret Manager."""
    from google.cloud import secretmanager

    client = secretmanager.SecretManagerServiceClient()
    name = f"projects/{project_id}/secrets/{secret_id}/versions/latest"
    response = client.access_secret_version(request={"name": name})
    return response.payload.data.decode("UTF-8")


def get_secret(secret_id: str) -> str:
    """Retrieve a secret value.

    In production, fetches from Google Secret Manager (with caching).
    In development, reads from os.environ (already populated by pydantic-settings).
    """
    if secret_id in _secrets_cache:
        return _secrets_cache[secret_id]

    environment = os.environ.get("ENVIRONMENT", "development")

    if environment == "production":
        project_id = os.environ.get("GOOGLE_CLOUD_PROJECT", "")
        if not project_id:
            raise RuntimeError(
                "GOOGLE_CLOUD_PROJECT must be set in production to use Secret Manager"
            )
        value = _get_secret_from_gsm(secret_id, project_id)
    else:
        value = os.environ.get(secret_id, "")

    _secrets_cache[secret_id] = value
    return value


def load_all_secrets() -> None:
    """Pre-load all application secrets into the cache.

    Called once at application startup. In development mode, this simply
    reads from environment variables (already loaded by pydantic-settings).
    In production, it fetches each secret from Google Secret Manager.
    """
    environment = os.environ.get("ENVIRONMENT", "development")
    logger.info("Loading secrets (environment=%s)", environment)

    for secret_name in _SECRET_NAMES:
        try:
            get_secret(secret_name)
        except Exception:
            # Non-fatal: some secrets may be optional (e.g. SENTRY_DSN)
            logger.debug("Could not load secret %s, skipping", secret_name)

    loaded = [k for k in _SECRET_NAMES if _secrets_cache.get(k)]
    logger.info("Loaded %d/%d secrets", len(loaded), len(_SECRET_NAMES))
