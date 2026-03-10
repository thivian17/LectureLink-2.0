"""FastAPI application entry-point with ADK agent mount."""

from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from lecturelink_api.config import Settings, get_settings
from lecturelink_api.routers import (
    admin,
    analytics,
    assessments,
    coach,
    courses,
    feedback,
    gamification,
    google_calendar,
    internal,
    invites,
    learn,
    lectures,
    materials,
    onboarding,
    quizzes,
    search,
    study_actions,
    syllabi,
    tutor,
)

logger = logging.getLogger(__name__)


def _configure_vertex_ai() -> None:
    """Configure Google GenAI to use Vertex AI (ADC) when no API key is set."""
    try:
        settings = get_settings()
    except Exception:
        return  # Settings not available (e.g. in tests without env vars)

    if not settings.GOOGLE_API_KEY:
        os.environ.setdefault("GOOGLE_GENAI_USE_VERTEXAI", "TRUE")
        if settings.GOOGLE_CLOUD_PROJECT:
            os.environ.setdefault("GOOGLE_CLOUD_PROJECT", settings.GOOGLE_CLOUD_PROJECT)
        os.environ.setdefault("GOOGLE_CLOUD_LOCATION", "us-central1")


@asynccontextmanager
async def lifespan(application: FastAPI):
    # Configure Vertex AI
    _configure_vertex_ai()

    # Load secrets at startup (non-fatal)
    try:
        from lecturelink_api.config.secrets import load_all_secrets

        load_all_secrets()
    except Exception:
        logger.warning("Failed to load secrets at startup", exc_info=True)

    # Initialize observability (Sentry, LangFuse, PostHog)
    try:
        from lecturelink_api.services.observability import init_observability

        init_observability()
    except Exception:
        logger.warning("Observability init failed (non-fatal)", exc_info=True)

    # Redis connection pool (non-fatal — app works without Redis in dev)
    try:
        from lecturelink_api.services.redis_client import close_redis_pool, get_redis_pool

        settings = get_settings()
        if settings.REDIS_URL:
            await get_redis_pool(settings.REDIS_URL)
        else:
            logger.info("REDIS_URL not set — running without cache/queue")
    except Exception:
        logger.warning("Redis unavailable — running without cache/queue")

    # ADK agent mount (lazy so the app still starts if google-adk is unavailable)
    try:
        from google.adk.cli.fast_api import get_fast_api_app
        from google.adk.sessions import InMemorySessionService

        from lecturelink_api.agents.syllabus_processor import extraction_pipeline

        # Use persistent sessions in production, in-memory for development
        session_service: object
        try:
            settings = get_settings()
            if settings.ENVIRONMENT == "production" and settings.SUPABASE_URL:
                from supabase import create_client

                from lecturelink_api.services.session_service import (
                    DatabaseSessionService,
                )

                sb = create_client(settings.SUPABASE_URL, settings.SUPABASE_SERVICE_KEY or settings.SUPABASE_ANON_KEY)
                session_service = DatabaseSessionService(sb)
                logger.info("ADK using DatabaseSessionService (production)")
            else:
                session_service = InMemorySessionService()
                logger.info("ADK using InMemorySessionService (development)")
        except Exception:
            session_service = InMemorySessionService()
            logger.info("ADK falling back to InMemorySessionService")

        adk_app = get_fast_api_app(
            agent=extraction_pipeline,
            session_service=session_service,
        )
        application.mount("/agents", adk_app)
    except Exception:
        pass  # ADK mount is optional; API still works without it
    yield

    # Shutdown: close Redis pool
    try:
        from lecturelink_api.services.redis_client import close_redis_pool

        await close_redis_pool()
    except Exception:
        pass


app = FastAPI(title="LectureLink V2 API", lifespan=lifespan)

# CORS — allow the Next.js dev server + production origins
_allowed_origins = ["http://localhost:3000"]
_extra_origins = os.environ.get("CORS_ORIGINS", "")
if _extra_origins:
    _allowed_origins.extend(o.strip() for o in _extra_origins.split(",") if o.strip())

app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# REST routers
app.include_router(courses.router)
app.include_router(syllabi.router)
app.include_router(assessments.router)
app.include_router(lectures.router)
app.include_router(materials.router)
app.include_router(search.router)
app.include_router(quizzes.router)
app.include_router(coach.router)
app.include_router(study_actions.router)
app.include_router(onboarding.router)
app.include_router(tutor.router, prefix="/api/tutor")
app.include_router(gamification.router)
app.include_router(learn.router)
app.include_router(google_calendar.router)
app.include_router(invites.router)
app.include_router(feedback.router)
app.include_router(analytics.router)
app.include_router(admin.router)
app.include_router(internal.router)


@app.get("/health")
async def health(settings: Settings = Depends(get_settings)):
    return {"status": "ok", "version": "0.1.0", "environment": settings.ENVIRONMENT}


@app.get("/health/sentry-test", include_in_schema=False)
async def sentry_test(settings: Settings = Depends(get_settings)):
    """Trigger a test error to verify Sentry is working. Only in non-production."""
    if settings.ENVIRONMENT == "production":
        raise HTTPException(status_code=404)
    raise ValueError("Sentry test error — this is intentional")


@app.get("/health/ready")
async def health_ready(settings: Settings = Depends(get_settings)):
    """Readiness probe — checks Supabase connectivity."""
    try:
        from supabase import create_client

        sb = create_client(settings.SUPABASE_URL, settings.SUPABASE_ANON_KEY)
        sb.table("courses").select("id").limit(1).execute()
        return {"status": "ready", "database": "ok"}
    except Exception as exc:
        from fastapi.responses import JSONResponse

        return JSONResponse(
            status_code=503,
            content={"status": "not_ready", "database": str(exc)},
        )
