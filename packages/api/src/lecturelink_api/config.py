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

    model_config = {"env_file": ".env", "extra": "ignore"}


@lru_cache
def get_settings() -> Settings:
    return Settings()
