# LectureLink V2 — Codebase Documentation

> Last updated: 2026-02-26 | ~62,000 lines of code | 37k Python, 22k TypeScript

LectureLink is an AI-powered study platform that processes lecture recordings and syllabi, extracts concepts, generates quizzes, tracks mastery, and provides personalized tutoring — all grounded in actual lecture content.

---

## Table of Contents

1. [Project Structure](#1-project-structure)
2. [Tech Stack](#2-tech-stack)
3. [Environment & Configuration](#3-environment--configuration)
4. [Database Schema](#4-database-schema)
5. [Backend Architecture](#5-backend-architecture)
6. [API Surface](#6-api-surface)
7. [Agent Systems](#7-agent-systems)
8. [Service Layer](#8-service-layer)
9. [Frontend Architecture](#9-frontend-architecture)
10. [Data Flow](#10-data-flow)
11. [Testing](#11-testing)

---

## 1. Project Structure

```
LectureLink-2.0/
├── pyproject.toml                    # Root workspace config (uv, ruff)
├── uv.lock                          # Python lockfile
├── env.example                      # Environment variable template
├── migrations/                      # SQL migration files (001-008)
│
├── packages/
│   ├── api/                         # FastAPI backend
│   │   ├── pyproject.toml           # Python deps, pytest config
│   │   ├── Dockerfile
│   │   ├── src/lecturelink_api/
│   │   │   ├── main.py              # FastAPI app entry point
│   │   │   ├── auth.py              # JWT auth (Supabase + Redis cache)
│   │   │   ├── worker.py            # arq background worker
│   │   │   ├── config/
│   │   │   │   └── settings.py      # Pydantic settings (@lru_cache)
│   │   │   ├── agents/              # 10 AI agent modules
│   │   │   ├── models/              # Pydantic request/response models
│   │   │   ├── middleware/           # Rate limiting
│   │   │   ├── pipeline/            # Lecture processing orchestration
│   │   │   ├── routers/             # 11 API routers
│   │   │   └── services/            # 25 service modules
│   │   └── tests/                   # 628 tests (unit + integration)
│   │
│   └── web/                         # Next.js frontend
│       ├── package.json
│       ├── app/                     # 18 page routes (App Router)
│       ├── components/              # 115+ React components
│       ├── lib/                     # API client, Supabase setup, mocks
│       └── types/                   # TypeScript type definitions
```

---

## 2. Tech Stack

### Backend
| Component | Technology |
|-----------|-----------|
| Framework | FastAPI 0.115+ |
| Python | 3.12+ (managed via uv) |
| Database | Supabase (PostgreSQL + pgvector) |
| AI/LLM | Google Gemini 2.5 Flash (primary), Gemini 2.5 Pro (concept extraction) |
| Embeddings | gemini-embedding-001 (2000-dimensional) |
| Agent Framework | Google ADK (Agent Development Kit) |
| Task Queue | arq (Redis-backed) with daemon thread fallback |
| Cache | Redis (optional, 60s TTL for auth/performance) |
| Auth | Supabase Auth (JWT Bearer tokens) |
| File Processing | python-docx, python-pptx |
| Validation | Pydantic v2, pydantic-settings |

### Frontend
| Component | Technology |
|-----------|-----------|
| Framework | Next.js 16.1.6 (App Router, Turbopack) |
| React | 19.2.3 |
| UI Library | Radix UI + shadcn/ui |
| Styling | Tailwind CSS v4 |
| Forms | react-hook-form + zod validation |
| Code Editor | Monaco Editor (@monaco-editor/react) |
| Auth | @supabase/ssr (cookie-based sessions) |
| Markdown | react-markdown |
| Notifications | Sonner |

### Infrastructure
| Component | Technology |
|-----------|-----------|
| Package Manager | uv (Python), npm (Node) |
| Linting | ruff (Python), ESLint (TypeScript) |
| Testing | pytest + pytest-asyncio |
| Deployment | Docker (Dockerfiles for api and web) |
| Secrets | Google Cloud Secret Manager (optional) |

---

## 3. Environment & Configuration

### Backend (.env at project root)
```env
# Required
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_ANON_KEY=your-anon-key

# Optional (have defaults)
SUPABASE_SERVICE_KEY=          # Admin/RLS-bypass operations
GOOGLE_API_KEY=                # Gemini LLM (falls back to Vertex AI ADC)
GOOGLE_CLOUD_PROJECT=          # GCP project for Vertex AI
ENVIRONMENT=development        # "development" | "production"
REDIS_URL=redis://localhost:6379
DATABASE_URL=                  # Direct Postgres (optional)
INTERNAL_API_KEY=              # For /internal endpoints
```

### Frontend (packages/web/.env.local)
```env
NEXT_PUBLIC_SUPABASE_URL=https://your-project.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=your-anon-key
NEXT_PUBLIC_API_URL=http://localhost:8000   # FastAPI backend
NEXT_PUBLIC_USE_MOCKS=false                 # Mock API for dev
```

### Settings (packages/api/src/lecturelink_api/config/settings.py)
```python
class Settings(BaseSettings):
    SUPABASE_URL: str
    SUPABASE_ANON_KEY: str
    SUPABASE_SERVICE_KEY: str = ""
    GOOGLE_API_KEY: str = ""
    GOOGLE_CLOUD_PROJECT: str = ""
    ENVIRONMENT: str = "development"
    DATABASE_URL: str = ""
    REDIS_URL: str = "redis://localhost:6379"
    # ... more optional keys
    model_config = {"env_file": ".env", "extra": "ignore"}

@lru_cache
def get_settings() -> Settings: ...
```

---

## 4. Database Schema

All tables are in Supabase (PostgreSQL + pgvector extension). Row-Level Security (RLS) enforced.

### Core Tables

#### courses
| Column | Type | Notes |
|--------|------|-------|
| id | UUID PK | |
| user_id | UUID FK | Owner |
| name | TEXT | Required |
| code | TEXT | e.g. "CS 101" |
| semester_start | DATE | |
| semester_end | DATE | |
| meeting_days | TEXT[] | e.g. ["Monday", "Wednesday"] |
| meeting_time | TEXT | e.g. "10:00 AM" |
| holidays | JSONB[] | e.g. [{name, date}] |
| target_grade | FLOAT | Default 0.8 |
| onboarding_path | TEXT | just_starting / mid_semester / course_complete |
| onboarding_step | TEXT | Current onboarding step |
| onboarding_completed_at | TIMESTAMPTZ | |
| mode | TEXT | "active" / "review" |

#### syllabi
| Column | Type | Notes |
|--------|------|-------|
| id | UUID PK | |
| course_id | UUID FK | |
| user_id | UUID FK | |
| file_url | TEXT | Supabase storage URL |
| raw_extraction | JSONB | Full extraction result |
| grade_breakdown | JSONB[] | [{component, weight, ...}] |
| extraction_confidence | FLOAT | 0-1 |
| needs_review | BOOLEAN | Human review flag |
| status | TEXT | processing / complete / error |

#### assessments
| Column | Type | Notes |
|--------|------|-------|
| id | UUID PK | |
| course_id | UUID FK | |
| syllabus_id | UUID FK | |
| title | TEXT | |
| type | TEXT | exam / quiz / assignment / project / ... |
| due_date | TIMESTAMPTZ | |
| due_date_raw | TEXT | Original text from syllabus |
| is_date_ambiguous | BOOLEAN | |
| weight_percent | FLOAT | Grade weight |
| topics | TEXT[] | Linked syllabus topics |
| student_score | FLOAT | Past score (onboarding) |

#### lectures
| Column | Type | Notes |
|--------|------|-------|
| id | UUID PK | |
| course_id | UUID FK | |
| user_id | UUID FK | |
| title | TEXT | |
| lecture_number | INT | |
| lecture_date | TEXT | |
| audio_url | TEXT | Supabase storage |
| slides_url | TEXT | Supabase storage |
| transcript | JSONB | Raw transcript segments |
| summary | TEXT | |
| processing_status | TEXT | pending / processing / completed / failed |
| processing_stage | TEXT | Current pipeline stage |
| processing_progress | FLOAT | 0-1 |
| processing_error | TEXT | |
| retry_count | INT | Max 3 |
| duration_seconds | INT | |

#### lecture_chunks
| Column | Type | Notes |
|--------|------|-------|
| id | UUID PK | |
| lecture_id | UUID FK | |
| user_id | UUID FK | |
| chunk_index | INT | |
| content | TEXT | Chunk text |
| start_time | FLOAT | Seconds |
| end_time | FLOAT | Seconds |
| slide_number | INT | |
| embedding | VECTOR(2000) | Gemini embedding |
| metadata | JSONB | |
| fts | TSVECTOR | Full-text search |
| **Indexes** | | HNSW (cosine), GIN (FTS) |

#### concepts
| Column | Type | Notes |
|--------|------|-------|
| id | UUID PK | |
| course_id | UUID FK | |
| lecture_id | UUID FK | |
| user_id | UUID FK | |
| title | TEXT | |
| description | TEXT | |
| category | TEXT | |
| difficulty_estimate | FLOAT | 0-1 |
| source_chunk_ids | UUID[] | Linked chunks |
| embedding | VECTOR(2000) | |

#### concept_assessment_links
| Column | Type | Notes |
|--------|------|-------|
| concept_id | UUID FK | |
| assessment_id | UUID FK | |
| relevance_score | FLOAT | 0.5-1.0 |
| mapping_confidence | FLOAT | |
| UNIQUE | | (concept_id, assessment_id) |

### Quiz Tables

#### quizzes
| Column | Type | Notes |
|--------|------|-------|
| id | UUID PK | |
| course_id | UUID FK | |
| user_id | UUID FK | |
| title | TEXT | |
| target_assessment_id | UUID FK | Optional |
| difficulty | TEXT | easy / medium / hard / adaptive |
| status | TEXT | pending / generating / ready / failed |
| question_count | INT | |
| best_score | FLOAT | |
| attempt_count | INT | |

#### quiz_questions
| Column | Type | Notes |
|--------|------|-------|
| id | UUID PK | |
| quiz_id | UUID FK | |
| user_id | UUID FK | |
| question_index | INT | |
| question_type | TEXT | mcq / true_false / short_answer / code_writing / code_fix / code_explain |
| question_text | TEXT | |
| options | JSONB | MCQ options |
| correct_answer | TEXT | |
| explanation | TEXT | |
| source_chunk_ids | UUID[] | Grounding sources |
| concept_id | UUID FK | |
| difficulty | FLOAT | |
| code_metadata | JSONB | For coding questions: language, starter_code, rubric, hints, etc. |
| review_status | TEXT | pending / approved / rejected |
| critic_log | JSONB | From critic agent |

#### quiz_attempts
| Column | Type | Notes |
|--------|------|-------|
| id | UUID PK | |
| quiz_id | UUID FK | |
| user_id | UUID FK | |
| question_id | UUID FK | |
| student_answer | TEXT | |
| is_correct | BOOLEAN | |
| time_spent_seconds | INT | |
| code_grading_result | JSONB | For coding: rubric_scores, line_feedback, etc. |
| hints_used | INT | |

### Tutor Tables

#### tutor_sessions
| Column | Type | Notes |
|--------|------|-------|
| id | UUID PK | |
| user_id | UUID FK | |
| course_id | UUID FK | |
| target_assessment_id | UUID FK | |
| mode | TEXT | diagnostic / full_lesson / custom_topic |
| status | TEXT | active / paused / completed / abandoned |
| lesson_plan | JSONB | Full plan with concepts, outline, content |
| current_concept_index | INT | |
| current_step_index | INT | |
| concepts_planned | INT | |
| concepts_completed | INT | |
| questions_asked | INT | |
| questions_correct | INT | |
| duration_seconds | INT | |
| summary | TEXT | AI-generated session summary |

#### tutor_session_events
| Column | Type | Notes |
|--------|------|-------|
| id | UUID PK | |
| session_id | UUID FK | |
| user_id | UUID FK | |
| event_type | TEXT | session_started / question_answer / reteach_triggered / chat_message / session_completed |
| concept_title | TEXT | |
| question_type | TEXT | |
| student_answer | TEXT | |
| is_correct | BOOLEAN | |
| grading_result | JSONB | Full grading data |
| misconception_type | TEXT | near_miss / fundamental / incomplete |
| reteach_triggered | BOOLEAN | |
| time_spent_seconds | INT | |

#### grading_feedback
| Column | Type | Notes |
|--------|------|-------|
| id | UUID PK | |
| event_id | UUID FK | |
| user_id | UUID FK | |
| feedback_type | TEXT | accurate / inaccurate |
| feedback_text | TEXT | |

### Other Tables

#### adk_sessions
Stores Google ADK agent conversation state with 24-hour expiration.

#### rate_limit_events
Sliding window rate limit tracking per user per action.

#### user_onboarding
Per-user onboarding state (has_seen_welcome, first_course_created_at).

### Key SQL Functions (RPCs)

| Function | Purpose |
|----------|---------|
| `get_study_priorities(course_id)` | Returns assessments ranked by urgency (active mode) or recency (review mode) |
| `hybrid_search(query_embedding, query_text, course_id, lecture_ids?, limit)` | Vector + FTS search with Reciprocal Rank Fusion |
| `get_concept_mastery(course_id, user_id)` | Per-concept accuracy, recent accuracy, trend (improving/declining/stable/new) |
| `get_quiz_history_summary(course_id, user_id)` | Latest 20 quizzes with scores and attempts |

---

## 5. Backend Architecture

### Application Lifecycle (main.py)

```python
app = FastAPI(title="LectureLink V2 API", lifespan=lifespan)
```

**Startup:**
1. Configure Vertex AI (if no GOOGLE_API_KEY, uses Application Default Credentials)
2. Load secrets from Google Cloud Secret Manager (non-fatal)
3. Initialize Redis connection pool (non-fatal — works without Redis in dev)
4. Mount Google ADK agent app at `/agents` (optional)

**Shutdown:**
1. Close Redis connection pool

**Middleware:**
- CORS (localhost:3000 + production origin)

**Routers mounted:** courses, syllabi, assessments, lectures, search, quizzes, coach, study_actions, onboarding, tutor, internal

### Authentication (auth.py)

```
Client Request (Bearer JWT)
    → Check Redis cache (60s TTL, key: jwt:{sha256[:16]})
    → Cache miss: Validate via supabase.auth.get_user(token)
    → Return {id, email, token}
    → Cache validated token in Redis
```

All protected endpoints use `Depends(get_current_user)`.

### Rate Limiting (middleware/rate_limit.py)

| Action | Limit | Window |
|--------|-------|--------|
| quiz_generate | 10 | 24 hours |
| qa_question | 50 | 1 hour |
| lecture_upload | 30 | 24 hours |
| study_coach | 30 | 1 hour |

Tracked via `rate_limit_events` table in Supabase.

### Task Queue (services/task_queue.py + worker.py)

**Primary:** arq worker with Redis backend
**Fallback:** Daemon threads when Redis unavailable (dev mode)

**Task functions:**
| Task | Timeout | Purpose |
|------|---------|---------|
| `task_process_lecture` | 600s | 7-stage lecture pipeline |
| `task_generate_quiz` | 600s | Plan → Generate → Critique loop |
| `task_process_syllabus` | 600s | Multi-agent extraction |
| `task_refresh_user` | 600s | Refresh study actions |
| `task_send_notification` | 600s | Send notification (placeholder) |

### GenAI Client Singleton (services/genai_client.py)

Thread-safe, event-loop-aware Gemini client. Detects when the event loop changes (e.g., arq worker vs main thread) and recreates the client to avoid `RuntimeError: Event loop is closed` from stale httpx connection pools.

---

## 6. API Surface

### Courses (`/api/courses`)
| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/courses` | Create course (returns onboarding flags) |
| GET | `/api/courses` | List user's courses |
| GET | `/api/courses/{id}` | Get course |
| PATCH | `/api/courses/{id}` | Update course |
| DELETE | `/api/courses/{id}` | Delete course |

### Syllabi (`/api/syllabi`)
| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/syllabi/upload` | Upload PDF/DOCX, enqueue extraction |
| GET | `/api/syllabi/{id}` | Get syllabus with extraction |
| GET | `/api/syllabi/{id}/status` | Poll processing status |
| PUT | `/api/syllabi/{id}/review` | Save user-reviewed extraction |

### Assessments (`/api`)
| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/courses/{id}/assessments` | List course assessments |
| GET | `/api/courses/{id}/assessments/priorities` | Study priorities (RPC) |
| PATCH | `/api/assessments/{id}` | Update assessment |
| DELETE | `/api/assessments/{id}` | Delete assessment |
| PUT | `/api/assessments/{id}/result` | Save student score |

### Lectures (`/api`)
| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/lectures/upload` | Upload audio/slides (500MB/50MB max) |
| GET | `/api/lectures/{id}` | Full detail (transcript, concepts, slides) |
| GET | `/api/lectures/{id}/status` | Processing status |
| GET | `/api/courses/{id}/lectures` | List course lectures |
| POST | `/api/lectures/{id}/retry` | Retry failed (max 3) |
| POST | `/api/lectures/{id}/reprocess` | Clean and reprocess |

### Search & Q&A (`/api`)
| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/search` | Hybrid vector + FTS search |
| POST | `/api/qa` | RAG-based question answering |

### Quizzes (`/api`)
| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/quizzes/generate` | Generate quiz (background) |
| GET | `/api/quizzes/{id}` | Get quiz with questions |
| GET | `/api/quizzes/{id}/status` | Generation status |
| GET | `/api/quizzes/{id}/questions` | Get questions |
| POST | `/api/quizzes/{id}/submit` | Submit answers, get score |
| GET | `/api/courses/{id}/quizzes` | List course quizzes |
| GET | `/api/courses/{id}/concepts` | List course concepts |
| POST | `/api/quizzes/{id}/questions/{qid}/hint` | Get coding hint |

### Study Coach (`/api`)
| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/courses/{id}/study-coach/chat` | Chat with AI coach |
| GET | `/api/courses/{id}/performance` | Performance analytics |

### Study Actions (`/api`)
| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/study-actions` | Deterministic actions (all courses) |
| GET | `/api/study-actions/enhanced` | LLM-enhanced actions |
| GET | `/api/courses/{id}/study-actions` | Course-specific actions |

### Onboarding (`/api/courses/{id}`)
| Method | Path | Description |
|--------|------|-------------|
| POST | `.../onboarding/start` | Initialize onboarding |
| GET | `.../onboarding/status` | Current step/path |
| PUT | `.../onboarding/step` | Advance step |
| GET | `.../onboarding/suggest-path` | AI-suggested path |
| POST | `.../onboarding/set-path` | Select path |
| POST | `.../onboarding/personalized-message` | Personalized welcome |
| GET | `.../onboarding/lecture-checklist` | Lecture schedule |
| GET | `.../semester-progress` | Semester progress |
| PUT | `.../onboarding/complete` | Mark complete |

### Tutor (`/api/tutor`)
| Method | Path | Description |
|--------|------|-------------|
| GET | `/{courseId}/entry` | Entry data (assessments, mastery) |
| POST | `/{courseId}/session/start` | Start session with lesson plan |
| GET | `/{courseId}/session/active` | Get active session |
| POST | `/session/{id}/answer` | Submit answer, get grading |
| PUT | `/session/{id}/pause` | Pause session |
| POST | `/session/{id}/resume` | Resume session |
| PUT | `/session/{id}/complete` | Complete, get summary |
| POST | `/session/{id}/grading-feedback` | Feedback on grading |
| GET | `/{courseId}/history` | Session history |
| GET | `/session/{id}/summary` | Session summary |
| POST | `/session/{id}/next-block` | Next teaching block |
| POST | `/session/{id}/generate-concept` | Pre-generate concept |
| POST | `/session/{id}/chat` | Chat within session |
| POST | `/session/{id}/diagnostic` | Start diagnostic |
| POST | `/{courseId}/diagnostic` | Diagnostic for assessment |
| POST | `/session/{id}/diagnostic/submit` | Submit diagnostic |
| GET | `/{courseId}/assessment/{aid}/readiness` | Assessment readiness |

### Internal (`/internal`) — Requires X-Internal-API-Key
| Method | Path | Description |
|--------|------|-------------|
| POST | `/internal/process-lecture` | Enqueue lecture processing |
| POST | `/internal/daily-refresh` | Fan out user refreshes |
| POST | `/internal/send-notification` | Placeholder notification |

### Health
| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Status + version |
| GET | `/health/ready` | Supabase connectivity |

---

## 7. Agent Systems

### 7.1 Lecture Processing Pipeline

**Entry:** `POST /api/lectures/upload` → `pipeline/lecture_processor.py:process_lecture()`
**Execution:** Background (arq or daemon thread), up to 3 retries with exponential backoff.

```
File Upload (audio/slides/both)
  │
  ▼
Stage 1: Input Router (deterministic)
  │ Classifies files → processing_path (audio+slides / audio_only / slides_only)
  │
  ├─────────────────────┐
  ▼                     ▼
Stage 2a: Audio         Stage 2b: Slide Analyzer
Transcriber             (gemini-2.5-flash, vision)
(gemini-2.5-flash)      Extracts text, diagrams,
→ timestamped segments   descriptions from PDF/PPTX
  │                     │
  └──────────┬──────────┘
             ▼
Stage 3: Content Aligner
  (gemini-2.5-flash + heuristic fallback)
  Maps transcript segments → slide numbers
             │
             ▼
Stage 4: Concept Extractor
  (gemini-2.5-PRO with thinking mode)
  Extracts 8-15 parent concepts + subconcepts
  Uses Bloom's taxonomy for categorization
             │
             ▼
Stage 5: Chunker + Embedder
  Deterministic chunking (400-token target)
  + gemini-embedding-001 (2000-dim vectors)
  Embeds both chunks AND concepts
             │
             ▼
Stage 6: Concept-Chunk Linker
  (cosine similarity, no LLM)
  Links each concept → top-5 source chunks
             │
             ▼
Stage 7: Concept Mapper
  (gemini-2.5-flash + embedding fallback)
  Maps concepts → upcoming assessments
  Scoring: schedule proximity + semantic similarity
             │
             ▼
Stored: lecture_chunks, concepts, concept_assessment_links
```

**Agent files:**
- `agents/input_router.py` — Deterministic file classification
- `agents/audio_transcriber.py` — Gemini multimodal transcription (gemini-2.5-flash)
- `agents/slide_analyzer.py` — Gemini vision slide analysis (gemini-2.5-flash)
- `agents/content_aligner.py` — LLM + heuristic alignment (gemini-2.5-flash)
- `agents/concept_extractor.py` — Concept extraction with thinking (gemini-2.5-pro)
- `agents/chunker.py` — Deterministic chunking + Gemini embeddings
- `agents/concept_chunk_linker.py` — Cosine similarity linking (numpy)
- `agents/concept_mapper.py` — Assessment mapping (gemini-2.5-flash + embeddings)

### 7.2 Syllabus Extraction Pipeline

**Entry:** `POST /api/syllabi/upload` → `services/syllabus_service.py:process_syllabus()`
**Framework:** Google ADK (Agent Development Kit)

```
PDF/DOCX Upload
  │
  ▼
Stage 1: Ingestion Agent (ADK LlmAgent)
  Tool: extract_document_text (deterministic, no LLM)
  │
  ├───────────────┬───────────────┐
  ▼               ▼               ▼
Schedule        Grading          Info
Extractor       Extractor        Extractor
(ADK Agent)     (ADK Agent)      (ADK Agent)
Weekly schedule  Grade breakdown   Course name,
+ dates          + assessments     instructor, policies
  │               │               │
  └───────────────┴───────────────┘
                  │
                  ▼
Stage 3: Merge + Validate (pure Python)
  Combines outputs, validates grades (98-102% sum),
  checks date boundaries, flags low confidence
                  │
                  ▼
Stored: syllabi, assessments
```

All 3 extraction agents run in parallel on gemini-2.5-flash (temperature=0.1).

**Agent file:** `agents/syllabus_processor.py`

### 7.3 Quiz Generation System

**Entry:** `POST /api/quizzes/generate` → `services/quiz.py`

```
Generate Request
  │
  ▼
Quiz Planner (services/quiz_planner.py)
  DB queries + RPC (no LLM)
  Selects concepts (adaptive: weak first, or by difficulty band)
  Retrieves grounding chunks per concept
  │
  ▼
Question Generator (services/quiz_generator.py)
  gemini-2.5-flash
  Creates MCQ / true-false / short-answer / coding questions
  Each grounded in source chunks
  │
  ▼
Question Critic (services/quiz_critic.py)
  gemini-2.5-flash
  Reviews: faithfulness (>0.7 required), clarity, difficulty
  Verdict: accept / revise / reject
  │
  ├─ Revisions needed → back to Generator with feedback
  └─ All pass → Store
  │
  ▼
Stored: quiz_questions (with source_chunk_ids)
```

### 7.4 Study Coach

**Entry:** `POST /api/courses/{id}/study-coach/chat`

```
Student message
  → Fetch: concept mastery + upcoming assessments + quiz history
  → Build compact JSON context
  → gemini-2.5-flash (system prompt: "You are a study coach...")
  → Structured JSON response:
    { message, recommendations[{concept, action, priority}], suggested_quiz }
```

### 7.5 Study Actions (Dual-Mode)

**Entry:** `GET /api/study-actions` (deterministic) or `GET /api/study-actions/enhanced` (LLM)

**Deterministic mode** (services/study_actions.py):
- Priority 1.0: No syllabus uploaded
- Priority 0.95: Syllabus needs review
- Priority 0.85+: Missing lectures (by gap count)
- Priority 0.70-0.85: Assessment prep (urgency x weight)
- Priority 0.40-0.70: Weak concept study

**LLM mode** (services/study_actions_llm.py):
- Gathers all course contexts → gemini-2.5-flash → personalized, cross-course prioritization

### 7.6 AI Tutor (Session-Based Teaching)

**Entry:** `POST /api/tutor/{courseId}/session/start`

```
Start Session
  │
  ▼
Tutor Planner (services/tutor_planner.py)
  Get priority concepts (mastery gap × difficulty × relevance)
  Get assessment context (title, days until, weight)
  Get student context (name, previous session summary)
  Generate lesson plan via Gemini (or deterministic fallback)
  Pre-generate first concept content
  │
  ▼
Teaching Loop (per concept):
  1. Teaching Block (services/tutor_content.py)
     Gemini generates explanation grounded in lecture chunks
  2. Check Question
     Gemini generates question + rubric
  3. Student Answer → Grade (services/tutor_grading.py)
     MCQ/TF/fill-in: deterministic
     Short/long answer: Gemini AI grading
  4. If wrong → Reteach (different angle)
  5. Transition to next concept
  │
  ▼
Session Complete
  AI-generated summary, mastery updates
```

**Grading tiers:**
| Question Type | Grading | Confidence |
|---|---|---|
| MCQ | Exact match (deterministic) | 1.0 |
| True/False | Boolean normalization (deterministic) | 1.0 |
| Fill-in-blank | Normalized string comparison (deterministic) | 1.0 |
| Ordering | List comparison (deterministic) | 1.0 |
| Short answer | Gemini AI with rubric | 0.0-1.0 |
| Long answer | Gemini AI with rubric | 0.0-1.0 |

---

## 8. Service Layer

### Core Services

| Service | File | Dependencies | Purpose |
|---------|------|-------------|---------|
| **Performance** | `services/performance.py` | Supabase RPC, Redis | Aggregates quiz attempts into concept mastery (60% historical + 40% recent) |
| **Embedding** | `services/embedding.py` | Gemini embedding-001 | Batch embedding (2000-dim) for indexing and search |
| **Search** | `services/search.py` | Gemini embeddings, Supabase RPC | Hybrid vector + BM25 search with snippet highlighting |
| **RAG** | `services/rag.py` | Gemini 2.5 Flash, search | RAG Q&A with source citations and follow-ups |
| **Lecture Storage** | `services/lecture_storage.py` | Supabase | Persists chunks and concepts with FK handling |

### Quiz Services

| Service | File | Dependencies | Purpose |
|---------|------|-------------|---------|
| **Quiz Orchestrator** | `services/quiz.py` | Gemini, Supabase | Full generation pipeline orchestration |
| **Quiz Planner** | `services/quiz_planner.py` | Supabase RPC, embeddings | Concept selection + chunk retrieval |
| **Quiz Generator** | `services/quiz_generator.py` | Gemini 2.5 Flash | Question creation from chunks |
| **Quiz Critic** | `services/quiz_critic.py` | Gemini 2.5 Flash | Quality review (faithfulness, clarity) |
| **Quiz Service** | `services/quiz_service.py` | Supabase | Persistence + deterministic scoring |
| **Code Grading** | `services/code_grading.py` | Gemini 2.5 Flash | AI-graded code with rubric scoring |
| **Code Questions** | `services/code_question_generator.py` | Gemini 2.5 Flash | Coding question generation |

### Tutor Services

| Service | File | Dependencies | Purpose |
|---------|------|-------------|---------|
| **Tutor CRUD** | `services/tutor.py` | Supabase | Session lifecycle (create/pause/resume/complete) |
| **Tutor Planner** | `services/tutor_planner.py` | Gemini, Supabase | Lesson plan generation, diagnostics, readiness |
| **Tutor Content** | `services/tutor_content.py` | Gemini, search | Teaching blocks, reteach, chat, practice |
| **Tutor Grading** | `services/tutor_grading.py` | Gemini | Multi-tier grading dispatcher |
| **Tutor Prompts** | `services/tutor_prompts.py` | None | Prompt templates for all tutor LLM calls |

### Other Services

| Service | File | Dependencies | Purpose |
|---------|------|-------------|---------|
| **Study Coach** | `services/coach.py` | Gemini, Supabase | Conversational study advice |
| **Study Actions** | `services/study_actions.py` | Supabase, performance | Deterministic action recommendations |
| **Study Actions LLM** | `services/study_actions_llm.py` | Gemini | LLM-enhanced recommendations |
| **Syllabus** | `services/syllabus_service.py` | Gemini ADK, Supabase | Multi-agent extraction orchestration |
| **Onboarding** | `services/onboarding.py` | Gemini, Supabase | Guided setup with path detection |
| **Session Service** | `services/session_service.py` | Supabase | ADK session persistence |
| **Redis Client** | `services/redis_client.py` | Redis | Connection pool + cache helpers |
| **Task Queue** | `services/task_queue.py` | Redis (arq) | Background job enqueueing |
| **GenAI Client** | `services/genai_client.py` | Gemini SDK | Loop-aware singleton |
| **Priority** | `services/priority.py` | None | Weight vectors for scoring modes |

---

## 9. Frontend Architecture

### Routing (Next.js App Router)

```
/                                    Landing page
/login                               Login
/signup                              Sign up
/dashboard                           Study Hub (action feed)
/dashboard/calendar                  Assessment calendar
/dashboard/courses/new               Create course
/dashboard/courses/[courseId]         Course detail
/dashboard/courses/[courseId]/lectures              Lecture list
/dashboard/courses/[courseId]/lectures/new           Upload lecture
/dashboard/courses/[courseId]/lectures/[lectureId]   Lecture viewer
/dashboard/courses/[courseId]/quizzes               Quiz list
/dashboard/courses/[courseId]/quiz/[quizId]         Take quiz
/dashboard/courses/[courseId]/quiz/[quizId]/results Quiz results
/dashboard/courses/[courseId]/syllabus/review       Review syllabus
/dashboard/courses/[courseId]/search                Search content
/dashboard/courses/[courseId]/onboarding            Onboarding flow
/dashboard/courses/[courseId]/tutor                 Tutor entry
/dashboard/courses/[courseId]/tutor/session/[sessionId]  Active session
/dashboard/courses/[courseId]/tutor/history         Session history
```

### Auth Flow

1. **Middleware** (`middleware.ts`) — Validates session cookies, redirects unauthenticated users to /login
2. **Dashboard Layout** (`app/dashboard/layout.tsx`) — Server-side auth check, wraps in DashboardShell
3. **API Client** (`lib/api.ts`) — `fetchWithAuth()` auto-refreshes on 401

### Supabase Client Setup

- **Browser:** `lib/supabase/client.ts` — `@supabase/ssr` with cookie handling
- **Server:** `lib/supabase/server.ts` — Uses `cookies()` from `next/headers`
- **Middleware:** `lib/supabase/middleware.ts` — Session refresh + route protection

### Component Organization (115+ components)

```
components/
├── ui/                    22 shadcn/ui primitives (button, card, dialog, etc.)
├── lectures/              14 components (upload, viewer, transcript, concepts, etc.)
├── quiz/                  18 components (generator, question types, results, code editor)
├── tutor/                 20 components (teaching blocks, chat, grading, progress)
├── onboarding/            12 components (multi-step flow, path selection, progress)
├── study-coach/           4 components (chat, performance dashboard, weak areas)
├── study-hub/             4 components (action cards, banners, loaders)
├── chat/                  3 components (floating Q&A button, chat interface)
├── search/                2 components (search page, result items)
├── syllabus-review/       7 components (grade breakdown, assessment table, confidence)
└── [top-level]            ~10 components (course detail, form, dashboard shell, etc.)
```

### API Client (lib/api.ts)

80+ functions organized by feature. All use `fetchWithAuth()` which:
- Gets Supabase auth token from session
- Adds Bearer token header
- Auto-retries on 401 (refreshes session)
- Handles 429 (RateLimitError), 404 (NotFoundError)

**Direct Supabase calls:** courses (CRUD), some assessments
**Backend API calls:** Everything else (lectures, quizzes, search, tutor, etc.)

### Mock API (lib/mock-api.ts)

Controlled via `NEXT_PUBLIC_USE_MOCKS=true`. Provides mock data for lectures, quizzes, search, Q&A. Simulates processing stage progression. Uses `withMocks(mockFn, realFn)` HOF pattern.

---

## 10. Data Flow

```
┌─────────────────────────────────────────────────────────────┐
│                    USER UPLOADS CONTENT                      │
└─────────────┬───────────────────────────┬───────────────────┘
              │                           │
        ┌─────┴─────┐              ┌──────┴──────┐
        ▼           │              ▼             │
    LECTURES        │          SYLLABUS          │
        │           │              │             │
        ▼           │              ▼             │
  7-Stage Pipeline  │   3-Agent Extraction       │
  (agents/)         │   (ADK pipeline)           │
        │           │              │             │
        ▼           │              ▼             │
  lecture_chunks    │        assessments         │
  concepts          │        syllabi             │
  concept_assessment_links                       │
        │                          │             │
        └──────────────────────────┘             │
                    │                            │
         ┌──────────┼──────────┐                 │
         ▼          ▼          ▼                 │
    QUIZ SYSTEM  SEARCH/RAG  PERFORMANCE         │
    (plan →      (hybrid     (mastery            │
     generate →   search)     scoring)           │
     critique)                                   │
         │          │          │                 │
         └──────────┼──────────┘                 │
                    ▼                            │
         ┌──────────────────────┐                │
         │    STUDY COACH       │                │
         │    STUDY ACTIONS     │                │
         │    AI TUTOR          │                │
         └──────────────────────┘                │
                    │                            │
                    ▼                            │
            PERSONALIZED LEARNING                │
            (recommendations,                    │
             tutoring sessions,                  │
             mastery tracking)                   │
                                                 │
         ┌───────────────────────────────────────┘
         │           ONBOARDING
         │    (path detection, lecture checklist,
         │     mastery seeding, personalized welcome)
         └───────────────────────────────────────
```

### Key Design Patterns

1. **Layered LLM calls:** Deterministic extraction first → LLM reasoning second → Deterministic validation third
2. **Fallback chains:** Every LLM call has a deterministic fallback (heuristic alignment, embedding-only mapping, template plans)
3. **Embedding-based linking:** Concepts ↔ chunks (cosine similarity), concepts ↔ assessments (embeddings + semantic + schedule)
4. **Background execution:** arq task queue (Redis) with daemon thread fallback for dev
5. **Model selection:** Gemini 2.5 Pro for concept extraction (hardest reasoning), Gemini 2.5 Flash for everything else (speed/cost)
6. **Structured outputs:** JSON mode (`response_mime_type: "application/json"`) with Pydantic validation
7. **Context management:** Services gather raw data, build compact JSON context for LLMs; LLMs focus on synthesis/reasoning

---

## 11. Testing

**Test count:** 628 passing, 92 skipped (integration/live markers)

### Configuration (packages/api/pyproject.toml)
```toml
[tool.pytest.ini_options]
asyncio_mode = "auto"
pythonpath = ["src", "tests"]
markers = [
    "integration: Integration tests requiring mocked or real Supabase",
    "slow: Tests that take more than 10 seconds",
    "live: Tests requiring real Gemini API and real Supabase (opt-in)",
]
```

### Running Tests
```bash
cd packages/api && uv run pytest           # All unit tests
cd packages/api && uv run pytest -m integration  # Integration only
cd packages/api && uv run pytest -m live         # Live API tests (opt-in)
```

### Test Patterns
- **Mocking:** All tests mock `get_settings()` (no .env in test env)
- **Fixtures:** `tests/fixtures/` and `tests/conftest.py`
- **Coverage:** Every agent, service, router, and model has tests
- **Integration tests:** `tests/integration/` — E2E pipelines, quiz lifecycle, syllabus pipeline

### Key Test Files
| File | Tests |
|------|-------|
| `test_api.py` | Core API endpoint tests |
| `test_chunker.py` | Chunking + embedding tests |
| `test_concept_extractor.py` | Concept extraction tests |
| `test_quiz_routes.py` | Quiz generation/submission |
| `test_tutor.py` | Tutor session lifecycle |
| `test_tutor_content.py` | Tutor content generation |
| `test_code_grading.py` | Code grading tests |
| `test_onboarding.py` | Onboarding flow tests |
| `test_study_actions.py` | Study action generation |
| `integration/test_full_e2e.py` | Full pipeline E2E |
