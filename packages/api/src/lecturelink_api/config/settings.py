"""Application settings loaded from environment variables."""

from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    SUPABASE_URL: str
    SUPABASE_ANON_KEY: str
    SUPABASE_SERVICE_KEY: str = ""
    GOOGLE_API_KEY: str = ""
    GOOGLE_CLOUD_PROJECT: str = ""
    ENVIRONMENT: str = "development"
    DATABASE_URL: str = ""
    INTERNAL_API_KEY: str = ""
    RESEND_API_KEY: str = ""
    SENTRY_DSN: str = ""
    POSTHOG_API_KEY: str = ""
    LANGFUSE_SECRET_KEY: str = ""
    REDIS_URL: str = "redis://localhost:6379"
    GOOGLE_OAUTH_CLIENT_ID: str = ""
    GOOGLE_OAUTH_CLIENT_SECRET: str = ""
    GITHUB_TOKEN: str = ""
    GITHUB_FEEDBACK_REPO: str = "thivian17/LectureLink-2.0"

    model_config = {"env_file": ".env", "extra": "ignore"}


@lru_cache
def get_settings() -> Settings:
    return Settings()
