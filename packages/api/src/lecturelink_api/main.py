"""FastAPI application entry-point with ADK agent mount."""

from __future__ import annotations

import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from lecturelink_api.config import get_settings
from lecturelink_api.routers import (
    assessments,
    coach,
    courses,
    lectures,
    quizzes,
    search,
    study_actions,
    syllabi,
)

# Configure Google GenAI to use Vertex AI (ADC) when no API key is set.
# Must happen before any ADK/genai imports that initialize clients.
_settings = get_settings()
if not _settings.GOOGLE_API_KEY:
    os.environ.setdefault("GOOGLE_GENAI_USE_VERTEXAI", "TRUE")
    if _settings.GOOGLE_CLOUD_PROJECT:
        os.environ.setdefault("GOOGLE_CLOUD_PROJECT", _settings.GOOGLE_CLOUD_PROJECT)
    os.environ.setdefault("GOOGLE_CLOUD_LOCATION", "us-central1")


@asynccontextmanager
async def lifespan(application: FastAPI):
    # ADK agent mount (lazy so the app still starts if google-adk is unavailable)
    try:
        from google.adk.cli.fast_api import get_fast_api_app
        from google.adk.sessions import InMemorySessionService

        from lecturelink_api.agents.syllabus_processor import extraction_pipeline

        adk_app = get_fast_api_app(
            agent=extraction_pipeline,
            session_service=InMemorySessionService(),
        )
        application.mount("/agents", adk_app)
    except Exception:
        pass  # ADK mount is optional; API still works without it
    yield


app = FastAPI(title="LectureLink V2 API", lifespan=lifespan)

# CORS — allow the Next.js dev server
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# REST routers
app.include_router(courses.router)
app.include_router(syllabi.router)
app.include_router(assessments.router)
app.include_router(lectures.router)
app.include_router(search.router)
app.include_router(quizzes.router)
app.include_router(coach.router)
app.include_router(study_actions.router)


@app.get("/health")
async def health():
    return {"status": "ok"}
