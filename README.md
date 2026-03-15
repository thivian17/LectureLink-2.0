# LectureLink V2

An AI-powered study platform that transforms lecture recordings, slides, and syllabi into personalized learning experiences — with AI tutoring, adaptive quizzes, concept mastery tracking, and an academic command center dashboard.

**Live at [lecturelink.ca](https://lecturelink.ca)**

## Architecture

```
lecturelink.ca          -> Cloud Run: Next.js 16 frontend
api.lecturelink.ca      -> Cloud Run: FastAPI backend
                           Cloud Run: arq worker (async jobs)
                           Cloud Memorystore: Redis (queue + cache)
                           Supabase: PostgreSQL + pgvector + Auth + Storage
                           Google Gemini API: LLM for all AI features
```

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend | Next.js 16, React 19, TypeScript, Tailwind CSS 4, shadcn/ui, Radix UI |
| Backend | FastAPI, Python 3.12+, Pydantic, arq (job queue) |
| Database | Supabase (PostgreSQL + pgvector for vector search) |
| AI/LLM | Google Gemini 2.5 Pro/Flash via google-genai SDK |
| Auth | Supabase Auth (email/password, OAuth) |
| Storage | Supabase Storage (audio, slides, documents) |
| Deployment | Google Cloud Run, Artifact Registry, GitHub Actions CI/CD |
| Observability | Sentry, PostHog, Langfuse |

## Features

### Lecture Processing Pipeline

Upload a lecture recording (audio/video) and/or slides, and the pipeline automatically:

1. **Transcribes** audio via Gemini
2. **Analyzes** slides (OCR, structure extraction)
3. **Aligns** transcript segments with slides
4. **Extracts concepts** — flat, testable knowledge units with dedup awareness against existing course concepts
5. **Chunks & embeds** content for vector search (pgvector)
6. **Links concepts** to assessments via concept-assessment mapping

Supports audio-only, slides-only, or combined uploads. Bulk upload with automatic file-to-lecture matching via LLM.

### AI Tutoring

Interactive 1-on-1 tutoring sessions powered by Gemini:

- **Diagnostic mode** — identifies knowledge gaps before teaching
- **Full lesson mode** — structured teaching with explanations, checks, and practice
- **Custom topic mode** — student picks what to study
- Socratic questioning, hint system, misconception detection
- Grading with rubrics, partial credit, and reteach triggers

### Quiz System

- Auto-generates MCQ, true/false, short answer, and code questions from lecture content
- Adaptive difficulty based on student mastery (Bayesian Knowledge Tracing)
- Code questions with Monaco editor, auto-grading, and line-by-line feedback
- Quiz critic agent validates question quality before delivery
- Practice test mode targeting specific assessments

### Personalized Learning Sessions

"Learn Mode" — daily guided study sessions that:

- Prioritize concepts based on upcoming assessments and current mastery
- Present study cards (hooks, explanations, formulas, examples, interactive challenges)
- Include flash review of fading concepts
- Run power quizzes with combo multipliers and XP rewards
- Generate session summaries with mastery deltas

### Academic Command Center (Dashboard V2)

The redesigned dashboard provides situational awareness:

- **Stats Row** — streak, XP, study time, concepts practiced
- **14-Day Timeline** — scrollable calendar with color-coded dots (red/amber/green for exam readiness, blue for lecture reviews, gray for deadlines)
- **Best Next Actions** — 2-4 prioritized recommendations ranked by urgency
- **Course Intelligence Cards** — per-course readiness %, risk level, next assessment, recommended action
- **Assessment Readiness Cards** — expandable cards with 4-signal breakdown (coverage, practice, freshness, effort), weak concepts, and suggested preparation
- **Study Tools Library** — quick access to learn sessions, practice tests, assessment prep, tutor chat

### Readiness V2 (4-Signal Model)

Replaces the mastery-only readiness system with four observable signals:

| Signal | Weight | What It Measures |
|--------|--------|-----------------|
| Coverage | 35% | Fraction of linked concepts the student has interacted with |
| Practice | 30% | Average correctness across linked concepts |
| Freshness | 20% | Recency-decay score (today = 1.0, 15+ days = 0.1) |
| Effort | 15% | Completed study sessions targeting the assessment's concepts |

Urgency classification (critical/high/medium/low) based on days until due + readiness score.

### Concept Registry

Cross-lecture concept deduplication:

- `concept_lectures` junction table — concepts can span multiple lectures
- Merged titles tracking for dedup history
- Orphan cleanup function for safe lecture reprocessing
- Meta-concept filtering (removes "lecture overview", "homework reminder", etc.)
- Dedup-aware extraction prompt injects existing course concepts for the LLM

### Search & Q&A

- Vector similarity search across all lecture content (transcripts, slides, concepts)
- RAG-powered Q&A with source citations (lecture, timestamp, slide number)
- Cross-lecture search within a course

### Gamification

- XP system with level progression
- Daily streaks with freeze protection
- Achievement badges (milestone-based)
- BKT (Bayesian Knowledge Tracing) for concept mastery

### Syllabus Management

- Upload syllabus PDF → auto-extract schedule, assessments, grade breakdown
- Review and edit extracted data
- Assessment-concept linking for readiness scoring

### Course Materials

- Upload supplementary materials (readings, homework, practice exams, study guides)
- Auto-extraction and indexing for search/RAG

### Integrations

- Google Calendar sync (assessment deadlines)
- GitHub issue creation from in-app feedback
- Email notifications via Resend

## Project Structure

```
LectureLink-2.0/
  packages/
    api/                          # FastAPI backend
      src/lecturelink_api/
        agents/                   # AI processing agents (13 modules)
          concept_extractor.py    #   Concept extraction V1 + V2
          audio_transcriber.py    #   Speech-to-text
          slide_analyzer.py       #   Slide OCR + analysis
          content_aligner.py      #   Transcript-slide alignment
          chunker.py              #   Content chunking + embedding
          ...
        routers/                  # API endpoints (22 modules)
          courses.py, lectures.py, quizzes.py, tutor.py,
          learn.py, search.py, gamification.py, dashboard_v2.py, ...
        services/                 # Business logic (50+ modules)
          readiness_v2.py         #   4-signal readiness computation
          concept_registry.py     #   Cross-lecture concept dedup
          dashboard_actions.py    #   Suggested actions engine
          learn_session.py        #   Personalized session orchestrator
          mastery.py              #   BKT mastery tracking
          genai_client.py         #   Gemini API client
          ...
        models/                   # Pydantic schemas (11 modules)
        pipeline/                 # Processing orchestration
        config/                   # Settings (pydantic-settings)
      tests/                      # 1298 tests (92 files)
      migrations/                 # SQL migrations
    web/                          # Next.js frontend
      app/                        # 33 pages
        dashboard/
          page.tsx                #   Academic Command Center
          courses/[courseId]/      #   Course detail, learn, tutor, quiz, ...
      components/
        dashboard/                # 12 command center components
        quiz/                     # Quiz renderer
        tutor/                    # Tutor session UI
        learn/                    # Learn mode components
        ui/                       # shadcn/ui primitives
        ...                       # 173 component files total
      lib/api.ts                  # API client (typed, auth-aware)
      types/database.ts           # TypeScript interfaces
```

## Getting Started

### Prerequisites

- Python 3.12+ and [uv](https://docs.astral.sh/uv/)
- Node.js 22+
- A Supabase project
- A Google AI API key (for Gemini)
- Redis (optional for local dev — needed for job queue)

### Setup

1. **Clone and install dependencies:**

```bash
git clone https://github.com/thivian17/LectureLink-2.0.git
cd LectureLink-2.0

# Backend
uv sync --all-packages --dev

# Frontend
cd packages/web && npm install
```

2. **Configure environment:**

```bash
# Backend — create .env at project root
cp env.example .env
# Edit .env with your Supabase URL, anon key, and Google API key

# Frontend — create .env.local
cp env.example packages/web/.env.local
# Edit with NEXT_PUBLIC_SUPABASE_URL and NEXT_PUBLIC_SUPABASE_ANON_KEY
```

3. **Run development servers:**

```bash
# Backend (from project root)
cd packages/api && uv run uvicorn lecturelink_api.main:app --reload

# Frontend (separate terminal)
cd packages/web && npm run dev
```

### Running Tests

```bash
cd packages/api
uv run pytest                    # Run all unit tests
uv run pytest -m integration     # Run integration tests (requires live services)
uv run pytest -v --tb=short      # Verbose output with short tracebacks
```

1298 tests total, ~1200 passing in standard run (92 skipped — marked `integration`, `live`, or `slow`).

### Linting

```bash
# Backend
uv run ruff check packages/api/src/

# Frontend
cd packages/web && npx tsc --noEmit
```

## Deployment

Production deployment uses Google Cloud Run with GitHub Actions CI/CD. See [DEPLOY.md](DEPLOY.md) for the full step-by-step guide.

**Services:**
- **API** — 512Mi, 1 CPU, 1-10 instances
- **Worker** — 1Gi, 1 CPU, 1-5 instances (always-on, no CPU throttle)
- **Web** — 256Mi, 1 CPU, 1-5 instances

CI/CD triggers on push to `main` (production) and `develop` (staging) via GitHub Actions with Workload Identity Federation (keyless auth to GCP).

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `SUPABASE_URL` | Yes | Supabase project URL |
| `SUPABASE_ANON_KEY` | Yes | Supabase anonymous key |
| `SUPABASE_SERVICE_KEY` | No | Service role key for admin operations |
| `GOOGLE_API_KEY` | No | Gemini API key (required for AI features) |
| `GOOGLE_CLOUD_PROJECT` | No | GCP project ID (for Vertex AI) |
| `REDIS_URL` | No | Redis connection string (default: `redis://localhost:6379`) |
| `ENVIRONMENT` | No | `development` or `production` |
| `NEXT_PUBLIC_SUPABASE_URL` | Yes | Frontend Supabase URL |
| `NEXT_PUBLIC_SUPABASE_ANON_KEY` | Yes | Frontend Supabase anon key |
| `NEXT_PUBLIC_API_URL` | No | Backend URL (default: `http://localhost:8000`) |

## License

Private repository. All rights reserved.
