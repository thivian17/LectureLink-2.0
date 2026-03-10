# LectureLink V2 — Full Codebase Documentation

LectureLink is an AI-powered study platform that processes lecture recordings, extracts concepts, generates quizzes, provides AI tutoring, and tracks academic performance. It is built as a monorepo with a FastAPI backend and a Next.js frontend, deployed on Google Cloud Run with Supabase as the database.

**Live URL:** `https://lecturelink.ca`
**API URL:** `https://api.lecturelink.ca`

---

## Table of Contents

1. [Architecture Overview](#1-architecture-overview)
2. [Project Structure](#2-project-structure)
3. [Backend API](#3-backend-api)
   - [Entry Point & Lifespan](#31-entry-point--lifespan)
   - [Configuration](#32-configuration)
   - [Authentication](#33-authentication)
   - [REST API Routes](#34-rest-api-routes)
   - [Services](#35-services)
   - [AI Agents](#36-ai-agents)
   - [Lecture Processing Pipeline](#37-lecture-processing-pipeline)
   - [Background Worker](#38-background-worker)
   - [Data Models](#39-data-models)
4. [Frontend Web App](#4-frontend-web-app)
   - [Pages & Routes](#41-pages--routes)
   - [API Client](#42-api-client)
   - [Components](#43-components)
   - [Hooks](#44-hooks)
   - [Types](#45-types)
5. [Database Schema](#5-database-schema)
   - [Tables](#51-tables)
   - [Functions & RPCs](#52-functions--rpcs)
   - [Migrations](#53-migrations)
6. [Deployment](#6-deployment)
   - [Architecture Diagram](#61-architecture-diagram)
   - [CI/CD Pipelines](#62-cicd-pipelines)
   - [Infrastructure](#63-infrastructure)
   - [Environment Variables](#64-environment-variables)
7. [Development Guide](#7-development-guide)
   - [Prerequisites](#71-prerequisites)
   - [Setup](#72-setup)
   - [Running Locally](#73-running-locally)
   - [Testing](#74-testing)

---

## 1. Architecture Overview

```
┌─────────────────────────────────────────────────────────┐
│                     Client (Browser)                     │
└────────────┬──────────────────────────┬─────────────────┘
             │                          │
             ▼                          ▼
┌────────────────────┐     ┌────────────────────────────┐
│  lecturelink.ca    │     │  api.lecturelink.ca        │
│  Next.js 16        │     │  FastAPI                   │
│  Cloud Run (web)   │     │  Cloud Run (api)           │
│  256Mi, 1-5 inst   │     │  512Mi, 1-10 inst          │
└────────────────────┘     └──────┬─────────┬───────────┘
                                  │         │
                           ┌──────┘         └──────┐
                           ▼                       ▼
                ┌──────────────────┐    ┌──────────────────┐
                │  Redis           │    │  Supabase        │
                │  Memorystore     │    │  PostgreSQL      │
                │  Cache + Queue   │    │  + pgvector      │
                └────────┬─────────┘    │  + Auth          │
                         │              │  + Storage       │
                         ▼              └──────────────────┘
                ┌──────────────────┐
                │  arq Worker      │
                │  Cloud Run       │
                │  512Mi, 1-3 inst │
                │  (always-on)     │
                └──────────────────┘
                         │
                         ▼
                ┌──────────────────┐
                │  Google Gemini   │
                │  2.5-Flash       │
                │  (AI/LLM)       │
                └──────────────────┘
```

**Technology Stack:**

| Layer | Technology |
|-------|-----------|
| Frontend | Next.js 16.1.6, React 19, TypeScript 5, Tailwind CSS 4, shadcn/ui |
| Backend | FastAPI 0.115, Python 3.12, Pydantic 2.10 |
| Database | Supabase (PostgreSQL + pgvector for vector search) |
| AI/LLM | Google Gemini 2.5-Flash (via API key or Vertex AI ADC) |
| Task Queue | arq (Redis-backed async job queue) |
| Caching | Redis (Google Cloud Memorystore) |
| Auth | Supabase Auth (JWT-based) |
| Storage | Supabase Storage (S3-compatible) |
| Deployment | Google Cloud Run (serverless containers) |
| CI/CD | GitHub Actions with Workload Identity Federation |
| Package Managers | uv (Python), npm (Node) |

---

## 2. Project Structure

```
LectureLink-2.0/
├── pyproject.toml              # uv workspace root config + ruff linting
├── uv.lock                     # Python dependency lockfile
├── package.json                # Root npm config (minimal)
├── env.example                 # Environment variable template
├── DEPLOY.md                   # GCP Cloud Run deployment guide
├── CODEBASE.md                 # Codebase reference
├── AGENTIC_WORKFLOWS.md        # Agentic system documentation
│
├── packages/
│   ├── api/                    # Backend (FastAPI)
│   │   ├── pyproject.toml      # Python deps, pytest config
│   │   ├── Dockerfile          # Multi-stage build
│   │   ├── src/lecturelink_api/
│   │   │   ├── main.py         # App entry point
│   │   │   ├── auth.py         # JWT authentication
│   │   │   ├── worker.py       # arq worker settings
│   │   │   ├── routers/        # 13 REST API routers
│   │   │   ├── services/       # 41 business logic modules
│   │   │   ├── agents/         # 12 AI agent modules
│   │   │   ├── models/         # 9 Pydantic model files
│   │   │   ├── pipeline/       # Lecture processing pipeline
│   │   │   ├── config/         # Settings, secrets, auth config
│   │   │   ├── middleware/     # Rate limiting
│   │   │   ├── utils/          # Utility functions
│   │   │   └── tools/          # Tool implementations
│   │   └── tests/              # 628 passing tests
│   │       ├── conftest.py
│   │       ├── fixtures/
│   │       ├── test_*.py
│   │       └── integration/
│   │
│   └── web/                    # Frontend (Next.js)
│       ├── package.json        # Node deps
│       ├── next.config.ts      # Standalone output
│       ├── tsconfig.json       # TypeScript config
│       ├── tailwind.config.ts  # Tailwind CSS
│       ├── Dockerfile          # Multi-stage build
│       ├── middleware.ts        # Auth + session middleware
│       ├── app/                # Next.js App Router pages
│       ├── components/         # React components (13 feature groups)
│       ├── lib/                # API client, hooks, utilities
│       └── types/              # TypeScript interfaces
│
├── migrations/                 # 10 SQL migration files
│
├── infra/                      # GCP infrastructure scripts
│   ├── scheduler-setup.sh      # Cloud Scheduler config
│   └── setup-wif.sh            # Workload Identity Federation setup
│
└── .github/workflows/
    ├── deploy.yml              # Production CI/CD (push to main)
    └── deploy-staging.yml      # Staging CI/CD (push to develop)
```

---

## 3. Backend API

### 3.1 Entry Point & Lifespan

**File:** `packages/api/src/lecturelink_api/main.py`

The FastAPI application uses an async lifespan manager that:

1. Configures Vertex AI when `GOOGLE_API_KEY` is not set (falls back to Application Default Credentials)
2. Loads secrets from Google Secret Manager in production, or from environment variables in development
3. Initializes the Redis connection pool (non-fatal if unavailable — the app degrades gracefully)
4. Optionally mounts the Google ADK agent at `/agents` for syllabus extraction

**CORS:** Configured for `localhost:3000` (dev) plus any origins in the `CORS_ORIGINS` env var.

**Health Endpoints:**
- `GET /health` — basic status check, returns version and environment
- `GET /health/ready` — readiness probe, verifies Supabase connectivity

**Routers Included:** 13 routers covering courses, syllabi, lectures, assessments, quizzes, search, coach, tutor, learn, onboarding, gamification, study actions, Google Calendar, and internal endpoints.

---

### 3.2 Configuration

**File:** `packages/api/src/lecturelink_api/config/settings.py`

Uses `pydantic-settings` with `@lru_cache` for singleton loading. Environment variables:

| Variable | Required | Description |
|----------|----------|-------------|
| `SUPABASE_URL` | Yes | Supabase project URL |
| `SUPABASE_ANON_KEY` | Yes | Supabase public anon key |
| `SUPABASE_SERVICE_KEY` | No | Service role key (bypasses RLS) |
| `GOOGLE_API_KEY` | No | Gemini API key (omit for Vertex AI) |
| `GOOGLE_CLOUD_PROJECT` | No | GCP project ID (for Vertex AI) |
| `ENVIRONMENT` | No | `"development"` or `"production"` |
| `REDIS_URL` | No | Redis URL (default: `redis://localhost:6379`) |
| `INTERNAL_API_KEY` | No | Secret for Cloud Tasks validation |
| `GOOGLE_OAUTH_CLIENT_ID` | No | Google OAuth client ID |
| `GOOGLE_OAUTH_CLIENT_SECRET` | No | Google OAuth client secret |

**File:** `packages/api/src/lecturelink_api/config/secrets.py`

In production, secrets are fetched from Google Cloud Secret Manager with in-memory caching. In development, they are read from `os.environ`. Nine secrets are pre-loaded at startup (non-fatal if missing).

---

### 3.3 Authentication

**File:** `packages/api/src/lecturelink_api/auth.py`

- `get_current_user()` — FastAPI dependency that validates the Supabase JWT from the `Authorization: Bearer <token>` header
- Uses Redis cache (60-second TTL) to avoid hitting Supabase Auth API on every request
- Falls back to Supabase Auth API if Redis is unavailable
- Returns a user dict with `id`, `email`, `token`
- `get_authenticated_supabase()` — creates a user-scoped Supabase client that enforces Row Level Security

---

### 3.4 REST API Routes

All endpoints require authentication unless noted otherwise.

#### Courses — `GET/POST/PATCH/DELETE /api/courses`

**File:** `packages/api/src/lecturelink_api/routers/courses.py`

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/courses` | Create course (returns onboarding flags) |
| `GET` | `/api/courses` | List user's courses (ordered by created_at desc) |
| `GET` | `/api/courses/{course_id}` | Get single course |
| `PATCH` | `/api/courses/{course_id}` | Update course fields |
| `DELETE` | `/api/courses/{course_id}` | Delete course |

All endpoints verify course ownership via `user_id` match.

---

#### Syllabi — `/api/syllabi`

**File:** `packages/api/src/lecturelink_api/routers/syllabi.py`

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/syllabi/upload` | Upload syllabus PDF/DOCX, triggers async extraction |
| `GET` | `/api/syllabi/{syllabus_id}` | Get syllabus metadata + extraction |
| `GET` | `/api/syllabi/{syllabus_id}/status` | Get processing status |
| `PUT` | `/api/syllabi/{syllabus_id}/review` | Review and confirm extraction |

Upload flow: validate file type → verify course ownership → clean up old syllabi/assessments → upload to Supabase Storage → create record with `status="processing"` → enqueue async extraction via arq.

---

#### Lectures — `/api/lectures`

**File:** `packages/api/src/lecturelink_api/routers/lectures.py`

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/lectures/upload` | Upload audio/slides, triggers processing pipeline |
| `GET` | `/api/lectures/{lecture_id}` | Full lecture detail (transcript, concepts, signed URLs) |
| `GET` | `/api/lectures/{lecture_id}/status` | Processing status |
| `GET` | `/api/courses/{course_id}/lectures` | List course lectures |
| `POST` | `/api/lectures/{lecture_id}/retry` | Retry failed processing (max 3 retries) |
| `POST` | `/api/lectures/{lecture_id}/reprocess` | Clean up and reprocess from scratch |

**Supported files:**
- Audio: `.mp3`, `.wav`, `.m4a`, `.ogg`, `.webm`, `.flac` (max 500 MB)
- Slides: `.pdf`, `.pptx` (max 50 MB)

**Rate limit:** 30 uploads per 24 hours.

Lecture detail response includes transcript segments with timing, extracted concepts with linked assessments, and fresh signed URLs (6-hour TTL) for audio/slides.

---

#### Assessments — `/api/assessments`

**File:** `packages/api/src/lecturelink_api/routers/assessments.py`

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/courses/{course_id}/assessments` | List assessments (ordered by due_date) |
| `GET` | `/api/courses/{course_id}/assessments/priorities` | Study priorities (SQL RPC) |
| `PATCH` | `/api/assessments/{assessment_id}` | Update assessment |
| `DELETE` | `/api/assessments/{assessment_id}` | Delete assessment |
| `PUT` | `/api/assessments/{assessment_id}/result` | Save student score (for onboarding) |

---

#### Quizzes — `/api/quizzes`

**File:** `packages/api/src/lecturelink_api/routers/quizzes.py`

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/quizzes/generate` | Start quiz generation (rate limit: 10/24h) |
| `GET` | `/api/quizzes/{quiz_id}` | Get quiz with questions |
| `GET` | `/api/quizzes/{quiz_id}/status` | Generation status |
| `GET` | `/api/quizzes/{quiz_id}/questions` | Get quiz questions (detail view) |
| `POST` | `/api/quizzes/{quiz_id}/submit` | Submit answers, returns score + feedback |
| `GET` | `/api/courses/{course_id}/quizzes` | List course quizzes |
| `GET` | `/api/courses/{course_id}/concepts` | List course concepts |
| `POST` | `/api/quizzes/{quiz_id}/questions/{question_id}/hint` | Get code question hint |

**Question types:** `mcq`, `true_false`, `short_answer`, `code_writing`, `code_fix`, `code_explain`

Quiz generation uses a generator-critic loop: plan → retrieve grounding chunks → generate questions → LLM critique for faithfulness/clarity/difficulty → revise flagged questions (max 3 iterations) → store.

---

#### Search & Q&A — `/api/search`, `/api/qa`

**File:** `packages/api/src/lecturelink_api/routers/search.py`

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/search` | Hybrid search across lecture chunks (vector + BM25) |
| `POST` | `/api/qa` | RAG-based Q&A with citations (rate limit: 50/hour) |

Search uses a PostgreSQL `hybrid_search` RPC that combines pgvector cosine similarity with BM25 full-text search via Reciprocal Rank Fusion (RRF).

Q&A retrieves 8 relevant chunks, generates a grounded answer with Gemini, and returns it only if confidence exceeds 0.7.

---

#### Study Coach — `/api/courses/{course_id}/study-coach/chat`

**File:** `packages/api/src/lecturelink_api/routers/coach.py`

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/courses/{course_id}/study-coach/chat` | Chat with AI coach (rate limit: 30/hour) |
| `GET` | `/api/courses/{course_id}/performance` | Course performance analytics |

Coach chat returns a message, study action recommendations, and optional quiz suggestions.

---

#### AI Tutor — `/api/tutor`

**File:** `packages/api/src/lecturelink_api/routers/tutor.py`

The tutor router has no prefix in its own definition; it is included in `main.py` with `prefix="/api/tutor"`.

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/tutor/{course_id}/entry` | Entry point with upcoming assessments |
| `POST` | `/api/tutor/{course_id}/session/start` | Start tutoring session |
| `GET` | `/api/tutor/{course_id}/session/active` | Get active session for course |
| `POST` | `/api/tutor/session/{session_id}/answer` | Submit answer to tutor question |
| `PUT` | `/api/tutor/session/{session_id}/pause` | Pause session |
| `POST` | `/api/tutor/session/{session_id}/resume` | Resume session |
| `PUT` | `/api/tutor/session/{session_id}/complete` | Complete session (returns summary) |
| `POST` | `/api/tutor/session/{session_id}/grading-feedback` | Submit grading feedback |
| `GET` | `/api/tutor/{course_id}/history` | Past session history |
| `GET` | `/api/tutor/session/{session_id}/summary` | Session summary |
| `POST` | `/api/tutor/session/{session_id}/next-block` | Get next content block |
| `POST` | `/api/tutor/session/{session_id}/generate-concept` | Generate concept content |
| `POST` | `/api/tutor/session/{session_id}/chat` | Chat with tutor |
| `POST` | `/api/tutor/session/{session_id}/diagnostic` | Start diagnostic from existing session |
| `POST` | `/api/tutor/{course_id}/diagnostic` | Start standalone diagnostic |
| `POST` | `/api/tutor/session/{session_id}/diagnostic/submit` | Submit diagnostic answers |
| `GET` | `/api/tutor/{course_id}/assessment/{assessment_id}/readiness` | Assessment readiness |

**Session modes:** `diagnostic` (assess knowledge gaps), `full_lesson` (adaptive tutoring), `custom_topic` (focused learning), `custom_plan`.

The tutor system tracks concepts completed, questions asked/correct, adapts lesson plans based on performance, triggers reteaching on misconceptions, and provides grade projections.

---

#### Learn Mode — `/api/learn`

**File:** `packages/api/src/lecturelink_api/routers/learn.py`

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/learn/{course_id}/session/start` | Start 10-25 min learning session |
| `POST` | `/api/learn/session/{session_id}/flash-review` | Submit flash review card answer |
| `GET` | `/api/learn/session/{session_id}/concept/{index}` | Get concept brief |
| `POST` | `/api/learn/session/{session_id}/gut-check` | Submit gut check answer |
| `GET` | `/api/learn/session/{session_id}/quiz` | Get power quiz (3-5 questions) |
| `POST` | `/api/learn/session/{session_id}/quiz/answer` | Submit quiz answer |
| `PUT` | `/api/learn/session/{session_id}/complete` | Complete session |
| `PUT` | `/api/learn/session/{session_id}/abandon` | Abandon session |
| `GET` | `/api/learn/session/{session_id}` | Get session state |

**Session flow:** Daily briefing → Flash review cards → Gut check → Concept briefs → Power quiz → Session summary with XP, streak, and badges.

---

#### Onboarding — `/api/courses/{course_id}`

**File:** `packages/api/src/lecturelink_api/routers/onboarding.py`

Router prefix: `/api/courses/{course_id}`

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `.../onboarding/start` | Start onboarding flow |
| `GET` | `.../onboarding/status` | Get current step + progress |
| `PUT` | `.../onboarding/step` | Update current onboarding step |
| `GET` | `.../onboarding/suggest-path` | Get suggested study path |
| `POST` | `.../onboarding/set-path` | Set onboarding path |
| `POST` | `.../onboarding/personalized-message` | Generate motivational message |
| `GET` | `.../onboarding/lecture-checklist` | Lecture catch-up checklist |
| `GET` | `.../semester-progress` | Semester summary |
| `PUT` | `.../onboarding/complete` | Mark onboarding complete |

**Steps:** syllabus_upload → extraction_review → path_selection → personalized_message → lecture_catchup → past_results → study_plan → material_upload → practice_intro.

---

#### Gamification — `/api/gamification`

**File:** `packages/api/src/lecturelink_api/routers/gamification.py`

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/gamification/state` | Full state (streaks, levels, XP, badges) |
| `GET` | `/api/gamification/xp/history` | Daily XP breakdown |
| `POST` | `/api/gamification/streak/freeze` | Use streak freeze |
| `GET` | `/api/gamification/badges` | Get earned and available badges |
| `GET` | `/api/gamification/readiness` | All assessment readiness |
| `GET` | `/api/gamification/readiness/{assessment_id}` | Single assessment readiness score |
| `GET` | `/api/gamification/courses/{course_id}/readiness` | Course readiness summary |
| `GET` | `/api/gamification/courses/{course_id}/grade-projection` | Projected final grade |
| `GET` | `/api/gamification/weekly-progress` | Weekly study metrics |

---

#### Study Actions — `/api/study-actions`

**File:** `packages/api/src/lecturelink_api/routers/study_actions.py`

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/study-actions` | Fast deterministic study recommendations |
| `GET` | `/api/study-actions/enhanced` | LLM-enhanced personalized recommendations |
| `GET` | `/api/courses/{course_id}/study-actions` | Course-specific actions |

The fast endpoint analyzes due dates, performance, and concept gaps without LLM cost. The enhanced endpoint uses Gemini to generate natural, motivating language.

---

#### Google Calendar — `/api/google`

**File:** `packages/api/src/lecturelink_api/routers/google_calendar.py`

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/google/tokens` | Store Google OAuth tokens |
| `DELETE` | `/api/google/tokens` | Disconnect Google account |
| `GET` | `/api/google/sync/status` | Check sync status |
| `POST` | `/api/google/sync` | Trigger calendar sync |
| `PUT` | `/api/google/sync/toggle` | Enable/disable calendar sync |

---

#### Internal — `/internal`

**File:** `packages/api/src/lecturelink_api/routers/internal.py`

All endpoints require `X-Internal-API-Key` header.

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/internal/process-lecture` | Cloud Tasks trigger for lecture processing |
| `POST` | `/internal/daily-refresh` | Daily study actions refresh |
| `POST` | `/internal/send-notification` | Send notification |

---

### 3.5 Services

Business logic is organized into 41 service modules in `packages/api/src/lecturelink_api/services/`.

#### Core Infrastructure

| Service | File | Purpose |
|---------|------|---------|
| GenAI Client | `genai_client.py` | Loop-aware singleton for Google Gemini client. Detects event loop changes and recreates the client to prevent "Event loop is closed" errors. |
| Embedding | `embedding.py` | `embed_query()` and `embed_texts()` using `gemini-embedding-001` with 2000 output dimensions. Batches up to 100 texts. |
| Search | `search.py` | `search_lectures()` — generates query embedding, calls the `hybrid_search` PostgreSQL RPC, enriches results with lecture titles. |
| RAG | `rag.py` | `ask_lecture_question()` — retrieves relevant chunks, calls Gemini with a RAG system prompt, parses JSON response (answer, confidence, sources, follow-ups), filters by 0.7 confidence threshold. |
| Redis Client | `redis_client.py` | Connection pool (max 20 connections, 3s timeout), `cache_get/set/delete` with JSON serialization and TTL. |
| Task Queue | `task_queue.py` | `TaskQueueService` — enqueues lecture processing, quiz generation, and syllabus processing via arq. Falls back to `threading.Thread(daemon=True)` when Redis is unavailable. |
| Rate Limit | `middleware/rate_limit.py` | Sliding window rate limiting with Redis backend (Supabase DB fallback). Limits: quiz_generate 10/24h, qa_question 50/1h, lecture_upload 30/24h, study_coach 30/1h. |

#### Quiz System

| Service | File | Purpose |
|---------|------|---------|
| Quiz Generation | `quiz.py` | Generator-critic loop: plan → retrieve grounding chunks → generate → critique → revise (max 3 iterations) → store. |
| Quiz Scoring | `quiz.py` (`score_quiz`) | Scores answers, identifies misconceptions, recommends next concepts. Handles MCQ, true/false, short answer, and code questions. |
| Quiz Planning | `quiz_planner.py` | Selects concepts and difficulty distribution for quiz generation. |
| Quiz Critique | `quiz_critic.py` | LLM reviews generated questions for faithfulness, clarity, and appropriate difficulty. |
| Code Questions | `code_question.py` | Generates coding challenges (write, fix, explain) with starter code and grading rubrics. |
| Code Grading | `code_grading.py` | Grades code submissions against rubrics with line-level feedback. |

#### Tutor System

| Service | File | Purpose |
|---------|------|---------|
| Tutor Session | `tutor.py` | Session lifecycle: create, get, update progress, complete, history. |
| Tutor Content | `tutor_content.py` | Generates teaching blocks, reteaching content, and chat responses. |
| Tutor Grading | `tutor_grading.py` | Grades student answers: is_correct, feedback, misconception type, reteach trigger. |
| Tutor Planner | `tutor_planner.py` | Generates diagnostics, analyzes results, creates adaptive lesson plans, predicts assessment performance. |

#### Study Features

| Service | File | Purpose |
|---------|------|---------|
| Learn Session | `learn_session.py` | Orchestrates learn mode: start session, submit flash reviews, get power quiz, complete session with XP/streaks/badges. |
| Flash Review | `flash_review.py` | Generates spaced-repetition flash cards for concept review. |
| Concept Brief | `concept_brief.py` | AI-generated concept explanations with difficulty-appropriate language. |
| Coach Chat | `coach.py` | AI study coach conversation with course context and performance data. |
| Study Actions | `study_actions.py` | Deterministic study recommendations based on due dates, performance, and concept gaps. |
| Study Actions LLM | `study_actions_llm.py` | LLM-enhanced version with natural, motivating language. |
| Performance | `performance.py` | Course analytics: concept mastery scores, trends, assessment progress. |

#### Gamification

| Service | File | Purpose |
|---------|------|---------|
| Gamification | `gamification.py` | XP tracking, streak management, level progression. |
| Badges | `badges.py` | 20+ badge types, earned for study achievements. |
| Readiness | `readiness.py` | Assessment readiness scoring, course readiness summaries, final grade projections. Considers concept mastery, assessment weight, trend, and due date urgency. |

#### Other Services

| Service | File | Purpose |
|---------|------|---------|
| Onboarding | `onboarding.py` | Suggested study paths, personalized messages, lecture checklists, mastery seeding from past scores. |
| Google Calendar | `google_calendar.py` | Syncs assessments to Google Calendar events using OAuth refresh tokens. |
| Processing | `processing.py` | Updates lecture processing status and progress percentage. |
| Session Service | `session_service.py` | ADK `DatabaseSessionService` for persistent agent sessions. |

---

### 3.6 AI Agents

Located in `packages/api/src/lecturelink_api/agents/`. These are purpose-built modules that interact with Google Gemini for specific tasks.

| Agent | File | Purpose |
|-------|------|---------|
| Input Router | `input_router.py` | Classifies uploaded files by extension. Determines processing path: `audio_only`, `slides_only`, or `audio+slides`. Validates formats and sizes. |
| Audio Transcriber | `audio_transcriber.py` | Transcribes audio files using the Gemini API. Returns timestamped transcript segments. |
| Slide Analyzer | `slide_analyzer.py` | Extracts text and visual descriptions from PDF/PPTX slides. |
| Content Aligner | `content_aligner.py` | Aligns transcript segments to slide page numbers, producing segments with both timing and slide context. |
| Title Generator | `title_generator.py` | Generates a human-readable lecture title from the content. |
| Concept Extractor | `concept_extractor.py` | Extracts key concepts, definitions, and theorems. Assigns difficulty estimates and categories. |
| Chunker | `chunker.py` | Segments content into ~200-token semantic chunks. Generates 2000-dimensional embeddings for each chunk. |
| Concept-Chunk Linker | `concept_chunk_linker.py` | Links each extracted concept to its source chunks via `source_chunk_ids`. |
| Concept Mapper | `concept_mapper.py` | Maps lecture concepts to syllabus assessments with relevance scores. |
| Syllabus Processor | `syllabus_processor.py` | Google ADK-based three-agent parallel extraction: schedule extractor, grading extractor, info extractor. Merges outputs into a `SyllabusExtraction`. |
| Study Coach | `study_coach.py` | Agentic study coaching system. |

---

### 3.7 Lecture Processing Pipeline

**File:** `packages/api/src/lecturelink_api/pipeline/lecture_processor.py`

The pipeline processes uploaded lectures through 7 stages:

```
Stage 1: Input Router
  └─ Classify files, determine processing path

Stage 2: Content Processing (parallel)
  ├─ Audio Transcriber (if audio present)
  └─ Slide Analyzer (if slides present)

Stage 3: Content Alignment
  └─ Sync transcript timestamps to slide pages

Stage 4: Title Generation
  └─ AI-generate lecture title

Stage 5: Concept Extraction
  └─ Extract concepts, definitions, theorems

Stage 6: Chunking & Embedding
  └─ Segment text (~200 tokens), generate 2000-dim vectors

Stage 7: Concept Linking + Assessment Mapping
  ├─ Link concepts to source chunks
  └─ Map concepts to syllabus assessments
```

**Progress tracking:** The pipeline reports progress at each stage (5% → 15% → 20% → 25% → 30% → 95% → 100%).

**Retry logic:** Max 3 attempts with exponential backoff. Marks lecture as "failed" after all retries exhausted.

**Output:** `lecture_id`, `chunks_stored`, `concepts_stored`, `concept_links_created`, `processing_path`, `duration_seconds`.

---

### 3.8 Background Worker

**File:** `packages/api/src/lecturelink_api/worker.py`

The arq worker runs as a separate Cloud Run service using the same Docker image as the API, with a different entrypoint command.

**Configuration:** `max_jobs=10`, `job_timeout=600s` (10 minutes)

**Task functions:**
- `task_process_lecture` — runs the 7-stage lecture processing pipeline
- `task_generate_quiz` — generates quiz via generator-critic loop
- `task_process_syllabus` — extracts syllabus data
- `task_refresh_user` — refreshes study action recommendations
- `task_send_notification` — delivers notifications

**Lifecycle:** `on_startup` creates a Supabase client; `on_shutdown` cleans up.

---

### 3.9 Data Models

Pydantic models in `packages/api/src/lecturelink_api/models/`:

**`api_models.py`** — REST request/response models for courses, syllabi, assessments, lectures, quizzes, concepts, and search.

**`lecture_models.py`** — Pipeline intermediate models: `TranscriptSegment` (timing, text, speaker), `RouteResult` (processing path), `SlideAnalysis` (content, visuals), `ExtractedConcept` (with embedding), `LectureChunk` (with timing and embedding).

**`tutor_models.py`** — Tutor session requests/responses: `TutorSessionStartRequest`, `TutorAnswerRequest`, `TutorSessionResponse`, `TutorSessionSummaryResponse`, `GradingResultResponse`, `DiagnosticResultResponse`.

**`gamification.py`** — `XPEvent`, `StreakInfo`, `LevelInfo`, `BadgeEarned`, `GamificationState`, `AssessmentReadiness`, `CourseReadinessSummary`, `GradeProjection`, `WeeklyProgress`.

**`learn.py`** — Learn mode session models: `StartSessionRequest/Response`, `FlashReviewAnswerRequest`, `SessionCompleteResponse`.

**`syllabus_models.py`** — Extraction models: `ExtractedField` (value, confidence, source_text), `AssessmentExtraction`, `GradeComponent`, `SyllabusExtraction`, `WeeklyScheduleEntry`.

**`google_calendar.py`** — OAuth token models.

---

## 4. Frontend Web App

### 4.1 Pages & Routes

The frontend uses the Next.js App Router. All `/dashboard` routes are protected by auth middleware.

```
/                                           Landing page
/login                                      Email/password + Google login
/signup                                     Account creation
/auth/callback                              Supabase OAuth callback (stores Google tokens)

/dashboard                                  Study Hub home
/dashboard/courses/new                      Create course form
/dashboard/courses/[courseId]                Course detail (tabbed)
/dashboard/courses/[courseId]/onboarding     Multi-step onboarding wizard
/dashboard/courses/[courseId]/lectures       Lecture list
/dashboard/courses/[courseId]/lectures/new   Upload lecture
/dashboard/courses/[courseId]/lectures/[id]  Lecture detail (transcript, slides, concepts)
/dashboard/courses/[courseId]/quizzes        Quiz list
/dashboard/courses/[courseId]/quiz/[id]      Quiz taking interface
/dashboard/courses/[courseId]/quiz/[id]/results  Quiz results
/dashboard/courses/[courseId]/tutor          AI Tutor mode selector
/dashboard/courses/[courseId]/tutor/history  Tutor session history
/dashboard/courses/[courseId]/tutor/session/[id]  Active tutor session
/dashboard/courses/[courseId]/learn          Gamified learn mode session
/dashboard/courses/[courseId]/readiness      Assessment readiness dashboard
/dashboard/courses/[courseId]/syllabus/review  Syllabus review & editing
/dashboard/courses/[courseId]/search         Semantic search within lectures
/dashboard/calendar                         Assessment calendar (all courses)
/dashboard/record                           Live lecture recording
/dashboard/badges                           Badge collection
/dashboard/settings                         Google Calendar integration settings
```

**Middleware** (`packages/web/middleware.ts`): Refreshes Supabase session, redirects unauthenticated users to `/login`, and redirects authenticated users away from auth pages.

---

### 4.2 API Client

**File:** `packages/web/lib/api.ts` (~1,178 lines)

Centralized API client with:

- **`fetchWithAuth(url, options)`** — attaches JWT Bearer token, 15-second timeout, auto-refreshes on 401
- **Error classes:** `ApiError`, `AuthError`, `RateLimitError`, `NotFoundError`
- **Course CRUD** goes directly to Supabase (no backend roundtrip)
- **All other calls** go through the FastAPI backend

Exports functions for every API endpoint: courses, syllabi, assessments, lectures, search, Q&A, quizzes, tutor, learn mode, gamification, study actions, onboarding, Google Calendar, and performance analytics.

---

### 4.3 Components

Components are organized into 13 feature groups in `packages/web/components/`:

#### UI Primitives (`components/ui/`)
shadcn/ui components: `badge`, `button`, `calendar`, `card`, `checkbox`, `collapsible`, `dialog`, `form`, `input`, `label`, `popover`, `progress`, `scroll-area`, `select`, `separator`, `sheet`, `skeleton`, `slider`, `sonner` (toasts), `table`, `tabs`, `tooltip`.

#### Dashboard Shell (`components/dashboard-shell.tsx`)
Main app layout with sidebar navigation, top bar, and responsive mobile menu.

#### Lectures (`components/lectures/`)
- `lecture-list.tsx` — table of lectures with processing status
- `lecture-detail-client.tsx` — full lecture view with tabbed interface
- `lecture-upload-form.tsx` — audio/slides upload form with drag-drop
- `lecture-recorder.tsx` — browser-based recording (MediaRecorder API)
- `transcript-viewer.tsx` — searchable transcript with timestamps
- `slide-viewer.tsx` — slide gallery with extracted text
- `concept-panel.tsx` — extracted concepts with linked assessments
- `audio-player-bar.tsx` — audio playback controls
- `processing-status.tsx` — processing progress indicator
- `qa-chat-button.tsx` — floating Q&A chat for lecture

#### Quizzes (`components/quiz/`)
- `QuizTakingClient.tsx` — main quiz interface
- `QuizList.tsx` / `QuizCard.tsx` — quiz list and card views
- `GenerateQuizDialog.tsx` — quiz generation form (difficulty, count, coding options)
- `QuestionView.tsx` — single question display
- `MCQOptions.tsx` / `TrueFalseOptions.tsx` / `ShortAnswerInput.tsx` — answer input types
- `CodeQuestion.tsx` / `CodeEditor.tsx` — Monaco editor for code challenges
- `QuizResults.tsx` / `ConceptPerformance.tsx` — results and analytics

#### AI Tutor (`components/tutor/`)
- `ModeSelector.tsx` — choose tutor mode (diagnostic, full lesson, custom topic)
- `AssessmentSelector.tsx` — target assessment picker
- `AssessmentConceptsPanel.tsx` — concept readiness for selected assessment
- `DiagnosticView.tsx` / `PreDiagnosticView.tsx` / `PostDiagnosticView.tsx` — diagnostic flow
- `TeachingBlock.tsx` — instructional content
- `CheckQuestion.tsx` — in-lesson quiz questions
- `FeedbackBlock.tsx` / `ReteachBlock.tsx` — grading feedback and reteaching
- `GradingFeedback.tsx` — grading accuracy feedback (accurate/inaccurate)
- `PracticeBlock.tsx` — practice exercises
- `TransitionBlock.tsx` — between-concept transitions
- `SummaryBlock.tsx` — session summary with mastery changes
- `SessionSummary.tsx` — final session results
- `ChatInput.tsx` / `ChatResponse.tsx` — chat during session
- `MarkdownContent.tsx` — render markdown in tutor responses
- `SessionProgressBar.tsx` / `LessonPlanOverview.tsx` — progress visualization

#### Learn Mode (`components/learn/`)
- `session/LearnSession.tsx` — main gamified session controller
- `session/DailyBriefing.tsx` — session intro
- `session/FlashReview.tsx` — flash card review
- `session/ConceptBriefCard.tsx` — concept explanation
- `session/PowerQuiz.tsx` — short assessment quiz
- `session/SessionProgressBar.tsx` — session progress visualization
- `session/SessionCelebration.tsx` — completion celebration
- `session/XPPopup.tsx` / `session/ComboDisplay.tsx` — XP and combo feedback
- `CourseReadinessCards.tsx` — readiness overview
- `ReadinessDetail.tsx` — individual course readiness detail
- `NextAssessmentCard.tsx` — next due assessment card
- `UpcomingAssessmentTimeline.tsx` — timeline of upcoming assessments
- `GradeProjection.tsx` — grade estimate display
- `StreakDisplay.tsx` — current streak counter
- `LevelBadge.tsx` — user level/mastery badge
- `BadgeCard.tsx` / `BadgeGrid.tsx` — badge collection
- `StartSessionButton.tsx` — CTA to start learn session
- `ActivityFeed.tsx` — recent activity log
- `WeeklyProgressSummary.tsx` — weekly activity

#### Onboarding (`components/onboarding/`)
- `OnboardingShell.tsx` — wrapper with step progress
- Step components for each of the 9 onboarding steps: `SyllabusUploadStep`, `ExtractionReviewStep`, `PathSelectionStep`, `PersonalizedMessageStep`, `StudyPlanStep`, `LectureCatchUpStep`, `PastResultsStep`, `MaterialUploadStep`, `PracticeModeIntroStep`
- `AssessmentTimeline.tsx` / `SemesterProgressBar.tsx` — progress visuals

#### Syllabus Review (`components/syllabus-review/`)
- `syllabus-review-client.tsx` — main review page
- `assessment-table.tsx` — editable table of extracted assessments
- `assessment-edit-dialog.tsx` — edit individual assessment
- `grade-breakdown.tsx` — grade component weights
- `course-info.tsx` — instructor info
- `confidence-indicator.tsx` — extraction confidence badge
- `action-bar.tsx` — review action controls

#### Study Coach (`components/study-coach/`)
- `StudyCoachTab.tsx` — coach interface
- `CoachChat.tsx` — chat component
- `PerformanceDashboard.tsx` — performance overview
- `WeakAreasPanel.tsx` — weak concept recommendations

#### Study Hub (`components/study-hub/`)
- `CourseActionBanner.tsx` — primary course CTA
- `HeroActionCard.tsx` — featured action card
- `SecondaryActions.tsx` — additional suggestions
- `StudyActionsLoader.tsx` — loading skeleton for study actions

#### Search (`components/search/`)
- `search-page-client.tsx` — search interface
- `search-result-item.tsx` — individual result with highlighting

#### Chat (`components/chat/`)
- `qa-chat.tsx` — full Q&A chat interface
- `qa-chat-button.tsx` / `floating-qa-button.tsx` — floating chat buttons

#### Settings (`components/settings/`)
- `google-calendar-section.tsx` — Google Calendar sync toggle

---

### 4.4 Hooks

Custom React hooks in `packages/web/components/lectures/hooks/`:

| Hook | File | Purpose |
|------|------|---------|
| `useAudioPlayer` | `hooks/use-audio-player.ts` | Audio playback state management (current time, playing, duration, seek, playback rate, volume, mute). Exposes `play()`, `pause()`, `toggle()`, `skip()`, `seek()`. Supports playback rates: 0.5, 0.75, 1, 1.25, 1.5, 1.75, 2. |
| `useTranscriptSync` | `hooks/use-transcript-sync.ts` | Syncs transcript highlight with audio playback position. Returns `activeSegmentIndex` and `activeSlideNumber`. |
| `useTranscriptSearch` | `hooks/use-transcript-search.ts` | Search and highlight within transcript text. Returns `query`, `setQuery`, `filteredIndices`, `clearSearch`, `isSearching`. |

---

### 4.5 Types

**File:** `packages/web/types/database.ts`

TypeScript interfaces matching the Supabase schema:

- **Core:** `Course`, `Syllabus`, `Assessment`, `Lecture`, `LectureDetail`, `LectureConcept`, `TranscriptSegment`
- **Quiz:** `Quiz`, `QuizQuestion`, `QuizAnswer`, `QuizSubmissionResult`, `CodeMetadata`
- **Tutor:** `TutorMode`, `TutorSession`, `TutorQuestion`, `GradingResult`, `ContentBlock`
- **Gamification:** `GamificationState`, `GamificationReadiness`, `CourseReadinessSummary`, `GradeProjection`
- **Learn Mode:** `LearnStartSessionResponse`, `ConceptBrief`, `PowerQuizQuestion`, `LearnSessionComplete`
- **Onboarding:** `OnboardingPath`, `OnboardingStatus`, `SemesterProgress`
- **Search:** `SearchResponse`, `QAResponse`
- **Coach:** `CoachResponse`

**Utilities:**
- `packages/web/lib/utils.ts` — `cn()` for Tailwind class merging (clsx + tailwind-merge)
- `packages/web/lib/format.ts` — `formatTimestamp()` (M:SS), `formatDuration()` (Xh Ym)
- `packages/web/lib/concept-colors.ts` — consistent color mapping for concepts
- `packages/web/lib/mock-api.ts` — mock data for development without backend

---

## 5. Database Schema

### 5.1 Tables

All tables use Row Level Security (RLS) for user data isolation. The database is hosted on Supabase (PostgreSQL with pgvector extension).

#### Core Tables

| Table | Key Columns | Purpose |
|-------|-------------|---------|
| `courses` | id, user_id, name, code, semester_start, semester_end, meeting_days, holidays, target_grade, mode, onboarding_path, onboarding_step, onboarding_completed_at | Course metadata and onboarding state |
| `syllabi` | id, course_id, user_id, file_url, status (processing/processed/error), raw_extraction (JSONB), grade_breakdown (JSONB), confidence | Uploaded syllabi with extraction data |
| `assessments` | id, course_id, user_id, title, type, due_date, weight_percent, topics, student_score, google_calendar_event_id | Assessment tracking with optional scores and calendar sync |
| `concepts` | id, course_id, lecture_id, user_id, title, category, difficulty_estimate, source_chunk_ids, embedding (2000-dim) | Extracted academic concepts |
| `concept_assessment_links` | concept_id, assessment_id, relevance_score | Links concepts to assessments |

#### Lecture Tables

| Table | Key Columns | Purpose |
|-------|-------------|---------|
| `lectures` | id, course_id, user_id, title, lecture_number, lecture_date, processing_status (pending/processing/completed/failed), processing_progress, processing_error, summary, duration_seconds, retry_count | Lecture metadata and processing state |
| `lecture_chunks` | id, lecture_id, user_id, content, start_time, end_time, slide_number, embedding (2000-dim vector), fts (tsvector) | Chunked lecture content with embeddings for semantic search and full-text search |

#### Quiz Tables

| Table | Key Columns | Purpose |
|-------|-------------|---------|
| `quizzes` | id, course_id, user_id, status (generating/ready/failed), difficulty, question_count | Quiz metadata |
| `quiz_questions` | id, quiz_id, user_id, type (mcq/true_false/short_answer/code_writing/code_fix/code_explain), question_text, options (JSONB), correct_answer, explanation, difficulty, code_metadata (JSONB) | Question data with optional code challenge metadata |
| `quiz_attempts` | id, quiz_id, question_id, user_id, answer, is_correct, time_spent_seconds, code_grading_result (JSONB), hints_used | Student answer records |

#### Tutor Tables

| Table | Key Columns | Purpose |
|-------|-------------|---------|
| `tutor_sessions` | id, course_id, user_id, mode (diagnostic/full_lesson/custom_topic), status, lesson_plan (JSONB), progress (JSONB) | Tutor session state |
| `tutor_session_events` | id, session_id, event_type, concept_id, grading_result (JSONB), misconception_type, reteach_triggered | Session event log |
| `grading_feedback` | id, event_id, user_id, feedback_type (accurate/inaccurate), feedback_text | Grading accuracy feedback |

#### Gamification Tables

| Table | Key Columns | Purpose |
|-------|-------------|---------|
| `xp_events` | id, user_id, xp_amount, source, created_at | Immutable XP event log |
| `user_streaks` | user_id (unique), current_streak, longest_streak, last_session_date, streak_freezes | Streak tracking |
| `user_levels` | user_id (unique), total_xp, current_level, xp_to_next_level | Level progression |
| `badges_earned` | user_id, badge_id (unique pair), earned_at, metadata (JSONB) | Badge collection |
| `learn_sessions` | id, course_id, user_id, time_budget_minutes, concepts_planned, concepts_completed, flash_review_results (JSONB), quiz_results (JSONB), xp_earned, combo_max | Learn mode session records |

#### Infrastructure Tables

| Table | Key Columns | Purpose |
|-------|-------------|---------|
| `rate_limit_events` | id, user_id, action, created_at | Rate limiting records |
| `user_onboarding` | user_id (unique), first_course_created | Global onboarding state |
| `adk_sessions` | id, user_id, agent_name, state (JSONB), expires_at | ADK agent session persistence |
| `user_google_tokens` | user_id (unique), access_token, refresh_token, token_expires_at, scopes, calendar_sync_enabled | Google OAuth tokens |
| `notification_log` | id, user_id, type, sent_at, opened_at, session_started_at | Notification tracking |

---

### 5.2 Functions & RPCs

| Function | Purpose |
|----------|---------|
| `hybrid_search(p_query_embedding, p_query_text, p_course_id, p_lecture_ids, p_limit, p_rrf_k)` | Combines pgvector cosine similarity with BM25 full-text search using Reciprocal Rank Fusion (RRF). Returns ranked chunks. |
| `get_study_priorities(p_course_id, p_user_id)` | Calculates study priority scores for assessments. Active mode: urgency (0.6) + weight (0.4). Review mode: mastery gap (0.6) + FSRS due dates (0.4). |
| `get_concept_mastery(p_user_id, p_course_id)` | Returns per-concept metrics: accuracy, trend, recent_accuracy. |
| `get_quiz_history_summary(p_user_id, p_course_id)` | Returns recent quiz history for a student. |
| `increment_retry_count(p_lecture_id)` | Atomically increments the retry counter on a lecture. |

---

### 5.3 Migrations

The primary migration directory is `packages/api/migrations/` (11 files). The root `migrations/` directory contains 2 additional files (`007_tutor.sql`, `008_quiz_questions_phase2.sql`).

#### `packages/api/migrations/`

| File | Phase | Description |
|------|-------|-------------|
| `001_phase1_schema.sql` | Phase 1 | Core tables: courses, syllabi, assessments, concepts, concept_assessment_links. Priority scoring function. RLS policies. |
| `002_phase2_lecture_processing.sql` | Phase 2 | Lectures, lecture_chunks (2000-dim vectors + fts tsvector), quizzes, quiz_questions, quiz_attempts, rate_limit_events. |
| `002b_hybrid_search.sql` | Phase 2 | `hybrid_search()` SQL function (vector + BM25 via RRF). |
| `003_phase3_study_coach.sql` | Phase 3 | `get_concept_mastery()` and `get_quiz_history_summary()` functions. |
| `004_phase4_production.sql` | Phase 4 | `adk_sessions` table for ADK agent persistence. |
| `005_coding_practice.sql` | Phase 4 | `code_metadata` JSONB on quiz_questions, `code_grading_result` on quiz_attempts, `hints_used`. |
| `005b_coding_question_types.sql` | Phase 4 | Extended question type enum: code_writing, code_fix, code_explain. |
| `006_onboarding.sql` | Phase 5 | Onboarding columns on courses, `student_score` on assessments, `user_onboarding` table. |
| `006b_review_mode_scoring.sql` | Phase 5 | Updated `get_study_priorities()` for review mode (mastery gap + FSRS). |
| `007_gamification_tables.sql` | Phase 6 | xp_events, user_streaks, user_levels, badges_earned, learn_sessions, notification_log. |
| `008_google_calendar.sql` | Phase 7 | user_google_tokens, google_calendar_event_id on assessments. |

#### `migrations/` (root)

| File | Phase | Description |
|------|-------|-------------|
| `007_tutor.sql` | Phase 6 | tutor_sessions, tutor_session_events, grading_feedback. |
| `008_quiz_questions_phase2.sql` | Phase 7 | Additional quiz_questions columns: source_chunk_ids, difficulty, review_status. |

---

## 6. Deployment

### 6.1 Architecture Diagram

```
lecturelink.ca          → Cloud Run: lecturelink-web-prod   (Next.js, 256Mi, 1-5 instances)
api.lecturelink.ca      → Cloud Run: lecturelink-api-prod   (FastAPI, 512Mi, 1-10 instances)
                          Cloud Run: lecturelink-worker-prod (arq, 512Mi, 1-3 instances, always-on)
                          Cloud Memorystore: Redis (1GB Basic, 10.139.150.251:6379)
                          Supabase: PostgreSQL + pgvector + Auth + Storage (external)
```

SSL certificates are auto-provisioned by Google via Cloud Run domain mappings.

---

### 6.2 CI/CD Pipelines

#### Production (`deploy.yml`) — triggered on push to `main`

```
lint-and-test
  ├→ build-and-push-api → deploy-api → deploy-worker ──→ notify
  └→ build-and-push-web → deploy-web ──────────────────↗
```

Each deploy uses a canary strategy:
1. Deploy with `--no-traffic` (no traffic to new revision)
2. Smoke test via `/health` endpoint
3. Shift 100% traffic to new revision

**Required GitHub Secrets:** `GCP_PROJECT_ID`, `WIF_PROVIDER`, `WIF_SERVICE_ACCOUNT`, `RUNTIME_SERVICE_ACCOUNT`, `NEXT_PUBLIC_SUPABASE_URL`, `NEXT_PUBLIC_SUPABASE_ANON_KEY`, `NEXT_PUBLIC_API_URL`, `MEMORYSTORE_IP`.

#### Staging (`deploy-staging.yml`) — triggered on push to `develop`

Same pipeline with:
- Service names suffixed with `-staging`
- `min-instances: 0` for cost optimization
- Uses `STAGING_*` secret variants
- `cancel-in-progress: true` for concurrent deployments

---

### 6.3 Infrastructure

#### Docker Images

**API Dockerfile** (`packages/api/Dockerfile`) — multi-stage:
1. **Builder:** `python:3.12-slim`, installs uv, syncs dependencies (frozen, no dev, no project)
2. **Runtime:** `python:3.12-slim`, installs `ffmpeg` and `libmagic1`, copies `.venv` from builder, copies source. Port 8080. Default: uvicorn. Override with `ENTRYPOINT_MODE=worker` for arq.

**Web Dockerfile** (`packages/web/Dockerfile`) — multi-stage:
1. **Deps:** `node:22-alpine`, `npm ci`
2. **Builder:** copies deps and source, `npm run build` with build-time args for Supabase URLs. Produces `.next/standalone`.
3. **Runner:** `node:22-alpine`, copies standalone + static. Port 3000. `node server.js`.

#### Infrastructure Scripts

**`infra/scheduler-setup.sh`** — creates a Cloud Scheduler job (`daily-study-refresh`) that runs at 06:00 UTC daily, hitting `/internal/daily-refresh` on the API with OIDC auth.

**`infra/setup-wif.sh`** — one-time setup for Workload Identity Federation: creates identity pool, OIDC provider, deployer service account, grants IAM roles, creates Artifact Registry repository. Outputs values for GitHub secrets.

#### Service Accounts

- **`github-deployer`** — used by GitHub Actions. Roles: `run.admin`, `artifactregistry.writer`, `iam.serviceAccountUser`, `secretmanager.secretAccessor`.
- **`lecturelink-runtime`** — used by Cloud Run services at runtime. Roles: `secretmanager.secretAccessor`, `aiplatform.user`, `logging.logWriter`.

#### Secrets Management

Production secrets are stored in Google Cloud Secret Manager and injected into Cloud Run services via `--set-secrets`:
- `SUPABASE_URL`, `SUPABASE_ANON_KEY`, `SUPABASE_SERVICE_ROLE_KEY`
- `GEMINI_API_KEY`, `INTERNAL_API_KEY`
- Optional: `SENTRY_DSN`, `POSTHOG_API_KEY`, `LANGFUSE_SECRET_KEY`, `RESEND_API_KEY`

---

### 6.4 Environment Variables

#### Backend (`env.example`)

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `SUPABASE_URL` | Yes | — | Supabase project URL |
| `SUPABASE_ANON_KEY` | Yes | — | Supabase public anon key |
| `SUPABASE_SERVICE_KEY` | No | — | Service role key (RLS bypass) |
| `GOOGLE_API_KEY` | No | — | Gemini API key (omit for Vertex AI) |
| `GOOGLE_CLOUD_PROJECT` | No | — | GCP project ID |
| `ENVIRONMENT` | No | `development` | `development` or `production` |
| `DATABASE_URL` | No | — | Direct Postgres connection |
| `REDIS_URL` | No | `redis://localhost:6379` | Redis URL for queue + cache |
| `INTERNAL_API_KEY` | No | — | Secret for internal endpoints |

#### Frontend (`packages/web/.env.local`)

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `NEXT_PUBLIC_SUPABASE_URL` | Yes | — | Supabase URL (build-time) |
| `NEXT_PUBLIC_SUPABASE_ANON_KEY` | Yes | — | Supabase anon key (build-time) |
| `NEXT_PUBLIC_API_URL` | No | `http://localhost:8000` | FastAPI backend URL |
| `NEXT_PUBLIC_USE_MOCKS` | No | `false` | Use mock API responses |

---

## 7. Development Guide

### 7.1 Prerequisites

- **Python 3.12+** and **uv** package manager
- **Node.js v24+** and **npm**
- **Git**
- A **Supabase** project (free tier works for development)
- A **Google Gemini API key** (from Google AI Studio)
- Optional: **Redis** (the app degrades gracefully without it)

### 7.2 Setup

```bash
# Clone the repo
git clone https://github.com/thivian17/LectureLink-2.0.git
cd LectureLink-2.0

# Install Python dependencies (MUST use --all-packages for workspace members)
uv sync --all-packages --dev

# Install Node dependencies
cd packages/web && npm install && cd ../..

# Configure environment
cp env.example .env
# Edit .env with your Supabase URL, anon key, and Gemini API key

# Configure frontend environment
cp packages/web/.env.local.example packages/web/.env.local
# Or create packages/web/.env.local with:
#   NEXT_PUBLIC_SUPABASE_URL=your-url
#   NEXT_PUBLIC_SUPABASE_ANON_KEY=your-key
#   NEXT_PUBLIC_API_URL=http://localhost:8000

# Run database migrations
# Apply each migration file in order via the Supabase SQL editor
```

### 7.3 Running Locally

```bash
# Start the API server (from repo root)
cd packages/api
uv run uvicorn lecturelink_api.main:app --reload --port 8000

# In a separate terminal, start the frontend
cd packages/web
npm run dev

# Optional: start the arq worker (requires Redis)
cd packages/api
uv run python -m arq lecturelink_api.worker.WorkerSettings
```

The frontend runs at `http://localhost:3000` and the API at `http://localhost:8000`.

### 7.4 Testing

```bash
# Run all tests (from the api directory)
cd packages/api
uv run pytest

# Run with verbose output
uv run pytest -v

# Run a specific test file
uv run pytest tests/test_api.py

# Run only unit tests (skip integration/live)
uv run pytest -m "not integration and not slow and not live"

# Run integration tests
uv run pytest -m integration
```

**Test suite:** 628 passing tests, 92 skipped (integration/live markers).

**Pytest configuration** (in `packages/api/pyproject.toml`):
- `asyncio_mode = "auto"` — async tests run without explicit markers
- `pythonpath = ["src", "tests"]` — both source and test helpers are importable
- Custom markers: `@pytest.mark.integration`, `@pytest.mark.slow`, `@pytest.mark.live`

**Testing note:** Tests must mock `get_settings()` when testing code that calls it, since no `.env` file is available in the test environment.

---

## Appendix: Key Technical Decisions

1. **Monorepo with uv workspace** — `packages/api` and `packages/web` in a single repo with separate dependency management
2. **Supabase over self-hosted PostgreSQL** — managed database, auth, and storage with built-in RLS
3. **pgvector for embeddings** — 2000-dimensional vectors stored directly in PostgreSQL, enabling hybrid search without a separate vector database
4. **arq over Celery** — lightweight async task queue that fits the Python asyncio model
5. **Google Gemini over OpenAI** — used for transcription, concept extraction, quiz generation, tutoring, and RAG
6. **Google ADK for syllabus extraction** — three-agent parallel extraction pipeline
7. **Hybrid search (vector + BM25)** — Reciprocal Rank Fusion combines semantic and keyword search for better retrieval
8. **Cloud Run for deployment** — serverless containers with auto-scaling, no Kubernetes management
9. **Workload Identity Federation** — GitHub Actions authenticates to GCP without long-lived service account keys
10. **Canary deploys** — new revisions are smoke-tested before receiving traffic
