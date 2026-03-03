# LectureLink 2.0 — Agentic Workflows Reference

> A complete map of every AI-powered pipeline, what data it consumes, what it produces, and how workflows connect.

---

## Architecture at a Glance

```
                              ┌─────────────────────────────────────────┐
                              │            User Actions                 │
                              │  Upload Syllabus · Upload Lecture ·     │
                              │  Start Quiz · Start Tutor · Chat ·     │
                              │  Learn Mode · Search · Onboarding      │
                              └──────┬──────────────┬──────────────┬────┘
                                     │              │              │
                    ┌────────────────┘              │              └────────────────┐
                    ▼                               ▼                              ▼
        ┌───────────────────┐          ┌────────────────────┐          ┌──────────────────┐
        │  WF 1: Syllabus   │          │  WF 2: Lecture     │          │  WF 9: Onboarding│
        │  Processing       │          │  Processing        │          │  Flow             │
        │  (3 parallel      │          │  (7-stage pipeline)│          │                   │
        │   ADK agents)     │          │                    │          │                   │
        └───────┬───────────┘          └────────┬───────────┘          └──────────────────┘
                │                               │
                ▼                               ▼
        ┌──────────────┐               ┌──────────────────┐
        │  assessments │               │  concepts         │
        │  syllabi     │               │  lecture_chunks   │
        └──────┬───────┘               │  concept_assess-  │
               │                       │  ment_links       │
               │                       └────────┬──────────┘
               │                                │
               └──────────┬─────────────────────┘
                          │
          ┌───────────────┼───────────────┬──────────────────┐
          ▼               ▼               ▼                  ▼
  ┌──────────────┐ ┌─────────────┐ ┌───────────┐   ┌───────────────┐
  │ WF 3: Quiz   │ │ WF 4: Tutor │ │ WF 5:     │   │ WF 6: RAG     │
  │ Generation   │ │ System      │ │ Coach     │   │ Search & Q&A  │
  │ (gen-critic  │ │ (adaptive   │ │ Chat      │   │               │
  │  loop)       │ │  lessons)   │ │           │   │               │
  └──────┬───────┘ └─────┬───────┘ └─────┬─────┘   └───────────────┘
         │               │               │
         ▼               ▼               │
  ┌──────────────────────────────┐       │
  │  quiz_attempts → mastery     │◄──────┘
  └──────────────┬───────────────┘
                 │
     ┌───────────┼────────────┬──────────────────┐
     ▼           ▼            ▼                  ▼
 ┌─────────┐ ┌──────────┐ ┌────────────┐ ┌──────────────┐
 │ WF 7:   │ │ WF 8:    │ │ WF 10:     │ │ WF 11:       │
 │ Learn   │ │ Study    │ │ Gamifi-    │ │ Readiness &  │
 │ Mode    │ │ Actions  │ │ cation     │ │ Grade Proj.  │
 └─────────┘ └──────────┘ └────────────┘ └──────────────┘
```

---

## AI Models Used

| Model | Role | Where |
|-------|------|-------|
| **Gemini 2.5 Pro** | Concept extraction (highest quality) | `agents/concept_extractor.py` |
| **Gemini 2.5 Flash** | Everything else: transcription, slide analysis, alignment, mapping, quiz gen/critique, tutoring, coaching, RAG, learn mode, onboarding, study actions | All other agent/service files |
| **gemini-embedding-001** | 2000-dim embeddings (chunks, concepts, queries) | `agents/chunker.py`, `services/embedding.py` |

---

## Workflow 1 — Syllabus Processing

```
Trigger:  POST /api/syllabi/upload  (PDF or DOCX)
```

### Pipeline

```
 ┌──────────────────┐
 │ Upload to        │  Supabase Storage
 │ bucket "syllabi" │  bucket write
 └────────┬─────────┘
          ▼
 ┌──────────────────────┐
 │ Text extraction      │  PyMuPDF (PDF) or
 │ (deterministic)      │  python-docx (DOCX)
 └────────┬─────────────┘
          ▼
 ┌────────────────────────────────────────────────────────┐
 │         ADK ParallelAgent  (3 agents in parallel)      │
 │                                                        │
 │  ┌──────────────────┐  ┌────────────────┐  ┌────────┐ │
 │  │ ScheduleExtractor│  │ GradingExtractor│  │ Info   │ │
 │  │                  │  │                 │  │Extract.│ │
 │  │ weekly_schedule  │  │ grade_breakdown │  │ title  │ │
 │  │ important_dates  │  │ assessment_list │  │ code   │ │
 │  │ meeting_info     │  │                 │  │ instr. │ │
 │  └────────┬─────────┘  └───────┬─────────┘  └───┬────┘ │
 │           └─────────┬──────────┘                 │      │
 │                     ▼                            │      │
 │           merge_extraction_outputs() ◄───────────┘      │
 └────────────────────────┬────────────────────────────────┘
                          ▼
                post_process_extraction()
                  • validate grade weights (98-102%)
                  • validate date boundaries
                  • compute confidence score
                  • flag needs_review
                          │
              ┌───────────┴───────────┐
              ▼                       ▼
    ┌──────────────┐        ┌──────────────────┐
    │ syllabi table │        │ assessments table │
    │              │        │                  │
    │ raw_extraction│        │ title, type,     │
    │ grade_breakdn│        │ due_date, weight,│
    │ confidence   │        │ topics           │
    │ needs_review │        │                  │
    └──────────────┘        └──────────────────┘
```

### Data In / Out

| | Details |
|---|---|
| **Input** | Syllabus file (PDF/DOCX), semester context from `courses` table |
| **AI calls** | 3× Gemini 2.5 Flash (parallel), temperature 0.1 |
| **DB reads** | `courses` (semester_start, semester_end, meeting_days) |
| **DB writes** | `syllabi` (raw_extraction, grade_breakdown, confidence), `assessments` (bulk insert) |
| **Side effects** | Deletes old assessments & syllabi for the course before inserting |

**Key files:**
- `routers/syllabi.py` — endpoint
- `services/syllabus_service.py` — orchestrator
- `agents/syllabus_processor.py` — ADK ParallelAgent definition

---

## Workflow 2 — Lecture Processing Pipeline

```
Trigger:  POST /api/lectures/upload  (audio + slides)
          POST /api/lectures/{id}/retry
          POST /api/lectures/{id}/reprocess
          POST /internal/process-lecture
```

### 7-Stage Pipeline

```
 ┌─────────────────────────────────────────────────┐
 │  Upload files → Supabase Storage "lectures"     │
 │  Create lecture record (status: "pending")       │
 │  Enqueue background job                         │
 └──────────────────────┬──────────────────────────┘
                        ▼
 ┌──────────────────────────────────────────────────┐
 │  STAGE 1: Input Router (deterministic)           │
 │  Classify files → audio+slides / audio_only /    │
 │                    slides_only                    │
 └──────────────────────┬──────────────────────────┘
                        ▼
 ┌──────────────────────────────────────────────────┐
 │  STAGE 2: Content Processing (parallel)          │
 │                                                  │
 │  ┌─────────────────────┐ ┌────────────────────┐  │
 │  │ Audio Transcriber   │ │ Slide Analyzer     │  │
 │  │                     │ │                    │  │
 │  │ Gemini 2.5 Flash    │ │ Gemini 2.5 Flash   │  │
 │  │ (multimodal audio)  │ │ (multimodal vision)│  │
 │  │                     │ │                    │  │
 │  │ OUT: [{start, end,  │ │ OUT: [{slide_num,  │  │
 │  │  text, speaker}]    │ │  title, text,      │  │
 │  │                     │ │  visual_desc, ...}]│  │
 │  └────────┬────────────┘ └──────────┬─────────┘  │
 └───────────┼─────────────────────────┼────────────┘
             └──────────┬──────────────┘
                        ▼
 ┌──────────────────────────────────────────────────┐
 │  STAGE 3: Content Alignment                      │
 │  • audio+slides: Gemini assigns slide_number     │
 │    to each transcript segment                    │
 │  • audio_only: passthrough                       │
 │  • slides_only: convert slides → segment format  │
 └──────────────────────┬──────────────────────────┘
                        ▼
              Title Generation (non-fatal)
              Gemini 2.5 Flash, temp 0.3
              First ~3000 chars → 5-10 word title
                        │
                        ▼
 ┌──────────────────────────────────────────────────┐
 │  STAGE 4: Concept Extraction                     │
 │  ★ Gemini 2.5 PRO (only Pro usage)              │
 │                                                  │
 │  Input: aligned segments (≤50k chars)            │
 │  Output: 8-15 parent concepts, each with:        │
 │    title, description, category, difficulty,     │
 │    related_concepts, subconcepts[]               │
 │  Categories: definition | theorem | process |    │
 │              concept | example | formula         │
 │  Post-process: dedup via normalized title match  │
 └──────────────────────┬──────────────────────────┘
                        ▼
 ┌──────────────────────────────────────────────────┐
 │  STAGE 5: Chunking + Embedding                   │
 │                                                  │
 │  chunk_content():                                │
 │    ~400 tok target, 500 max, 100 min             │
 │    2-segment overlap between chunks              │
 │                                                  │
 │  embed_chunks() + embed_concepts():              │
 │    gemini-embedding-001, 2000-dim                │
 │    task_type=RETRIEVAL_DOCUMENT                  │
 │    batches of 100                                │
 └──────────────────────┬──────────────────────────┘
                        ▼
 ┌──────────────────────────────────────────────────┐
 │  STAGE 6: Concept-Chunk Linking + Storage        │
 │                                                  │
 │  link_concepts_to_chunks():                      │
 │    cosine similarity (numpy), top-5 chunks       │
 │    per concept → populates source_chunk_ids      │
 │                                                  │
 │  store_chunks() → lecture_chunks table           │
 │  store_concepts() → concepts table               │
 └──────────────────────┬──────────────────────────┘
                        ▼
 ┌──────────────────────────────────────────────────┐
 │  STAGE 7: Concept Mapping                        │
 │  Gemini 2.5 Flash                                │
 │                                                  │
 │  Links concepts ↔ assessments via 3 signals:     │
 │    schedule match   (50%)                        │
 │    semantic simil.  (30%)                        │
 │    explicit cover.  (20%)                        │
 │                                                  │
 │  Fallback: embedding-only similarity             │
 │  OUT → concept_assessment_links table            │
 └──────────────────────────────────────────────────┘
```

### Data In / Out

| | Details |
|---|---|
| **Input** | Audio file (mp3/wav/m4a/ogg/webm/flac, ≤500MB), Slides (PDF/PPTX, ≤50MB) |
| **AI calls** | 2× Gemini Flash (transcribe + slides, parallel), 1× Flash (alignment), 1× Flash (title), 1× **Gemini Pro** (concepts), 1× Flash (concept mapping), embedding-001 (chunks + concepts) |
| **DB reads** | `syllabi` (raw_extraction.weekly_schedule), `assessments`, `lectures` (existing for course) |
| **DB writes** | `lectures` (status, transcript, title, duration), `lecture_chunks` (bulk), `concepts` (bulk), `concept_assessment_links` (upsert) |
| **Storage** | Supabase Storage bucket `lectures` (audio + slides files) |
| **Error handling** | Max 3 retries, exponential backoff; marks `processing_status: "failed"` on exhaustion |

**Key files:**
- `routers/lectures.py` — endpoints
- `pipeline/lecture_processor.py` — orchestrator
- `pipeline/background.py` — background task entry
- `agents/input_router.py`, `agents/audio_transcriber.py`, `agents/slide_analyzer.py`, `agents/content_aligner.py`, `agents/concept_extractor.py`, `agents/chunker.py`, `agents/concept_chunk_linker.py`, `agents/concept_mapper.py`, `agents/title_generator.py`
- `services/lecture_storage.py` — DB persistence

---

## Workflow 3 — Quiz Generation

```
Trigger:  POST /api/quizzes/generate
Submit:   POST /api/quizzes/{id}/submit
```

### Generator-Critic Loop

```
 ┌──────────────────────────────────────────────┐
 │  Quiz Planning                               │
 │                                              │
 │  If target_assessment_id:                    │
 │    get concepts via concept_assessment_links  │
 │  Get mastery via get_concept_mastery RPC     │
 │    → prioritize weak concepts                │
 │  For each concept: top-3 grounding chunks    │
 │    via hybrid_search RPC                     │
 └─────────────────────┬────────────────────────┘
                       ▼
 ┌──────────────────────────────────────────────┐
 │  Generator-Critic Loop  (max 3 iterations)   │
 │                                              │
 │  ┌──────────┐     ┌──────────┐              │
 │  │ Generator│────▶│  Critic  │              │
 │  │ (Flash)  │     │  (Flash) │              │
 │  │          │     │          │              │
 │  │ questions│     │ verdicts:│              │
 │  │ from plan│     │ accept   │──▶ keep      │
 │  │          │     │ revise   │──▶ re-gen    │
 │  │          │     │ reject   │──▶ drop      │
 │  └──────────┘     └──────────┘              │
 │                                              │
 │  Faithfulness < 0.7 → reject                │
 │  Clarity < 0.8 → flag for revision          │
 └─────────────────────┬────────────────────────┘
                       ▼
         ┌─────────────────────────┐
         │  Code Questions         │  (optional)
         │  Gemini 2.5 Flash       │
         │                         │
         │  Types: code_writing,   │
         │    code_fix, code_explain│
         │  Includes: starter_code,│
         │    reference_solution,  │
         │    grading_rubric,      │
         │    hints, examples      │
         └────────────┬────────────┘
                      ▼
         ┌─────────────────────────┐
         │  quiz_questions table   │
         │  quizzes table          │
         └─────────────────────────┘
```

### Submission & Grading

```
 Student submits answers
         │
         ▼
 ┌───────────────────────────────────┐
 │  Scoring dispatcher               │
 │                                   │
 │  MCQ / true_false → deterministic │
 │  short_answer → string comparison │
 │  code → AI grading (Flash)        │
 │    evaluates: correctness,        │
 │    concept understanding,         │
 │    code quality, edge cases       │
 └───────────────────┬───────────────┘
                     ▼
           quiz_attempts table
           (feeds mastery RPCs)
```

### Data In / Out

| | Details |
|---|---|
| **Input** | course_id, optional target_assessment_id, optional lecture_ids |
| **AI calls** | Planning: 0 LLM. Generation: 1-3× Flash (gen) + 1-3× Flash (critic). Code: 1× Flash. Grading: 1× Flash per code question. |
| **DB reads** | `concepts`, `concept_assessment_links`, `lecture_chunks` (via hybrid_search RPC), mastery (via get_concept_mastery RPC) |
| **DB writes** | `quizzes`, `quiz_questions`, `quiz_attempts` |

**Key files:**
- `routers/quizzes.py` — endpoints
- `services/quiz.py` — orchestrator + scoring
- `services/quiz_planner.py` — adaptive planning
- `services/quiz_loop.py` — generator-critic loop
- `services/quiz_generator.py`, `services/quiz_critic.py` — LLM calls
- `services/code_question_generator.py` — code question generation
- `services/code_grading.py` — AI code grading

---

## Workflow 4 — Study Tutor

```
Trigger:  POST /api/tutor/{course_id}/session/start
```

### Session Lifecycle

```
 ┌──────────────────────────────────────────────┐
 │  Lesson Plan Generation                      │
 │  Gemini 2.5 Flash                            │
 │                                              │
 │  Inputs:                                     │
 │    • priority concepts (mastery + assessment  │
 │      links)                                  │
 │    • student context (quiz history)           │
 │                                              │
 │  Output: structured plan with per-concept     │
 │    outlines                                  │
 │  Pre-generates content for 1st concept       │
 └─────────────────────┬────────────────────────┘
                       ▼
 ┌──────────────────────────────────────────────┐
 │  Teaching Loop (per concept)                 │
 │                                              │
 │  Steps: activate → explain → check →         │
 │         practice → summary → transition      │
 │                                              │
 │  Each step: Gemini 2.5 Flash generates       │
 │    content block (markdown + optional         │
 │    interactive question)                     │
 │                                              │
 │  At ~75% through concept:                    │
 │    pre-generate next concept (background)    │
 └─────────────────────┬────────────────────────┘
                       ▼
 ┌──────────────────────────────────────────────┐
 │  Answer Grading (multi-tier)                 │
 │                                              │
 │  MCQ          → deterministic (index match)  │
 │  true_false   → deterministic                │
 │  fill_blank   → normalized string compare    │
 │  ordering     → list comparison              │
 │  short_answer → Gemini Flash AI grading      │
 │  long_answer  → Gemini Flash AI grading      │
 │                                              │
 │  Wrong answer → triggers reteach content     │
 │    (different-angle explanation via Flash)    │
 └─────────────────────┬────────────────────────┘
                       ▼
 ┌──────────────────────────────────────────────┐
 │  In-Session Chat                             │
 │  Gemini 2.5 Flash                            │
 │                                              │
 │  Classifies: on_topic / related / off_topic  │
 │  Responds in teaching context                │
 └──────────────────────────────────────────────┘
```

### Data In / Out

| | Details |
|---|---|
| **Input** | course_id, user_id, concept selection based on mastery |
| **AI calls** | Flash: lesson plan, content blocks (per step × per concept), grading (short/long answer), reteach, chat |
| **DB reads** | `concepts`, `concept_assessment_links`, mastery RPCs, quiz history |
| **DB writes** | `tutor_sessions` (CRUD, lesson_plan JSONB, progress), `tutor_session_events` (event log), `grading_feedback` |

**Key files:**
- `routers/tutor.py` — 16 endpoints
- `services/tutor_planner.py` — lesson plan generation
- `services/tutor_content.py` — content generation, reteach, chat
- `services/tutor_grading.py` — multi-tier grading dispatcher
- `services/tutor_prompts.py` — all prompt templates

---

## Workflow 5 — Study Coach Chat

```
Trigger:  POST /api/courses/{course_id}/study-coach/chat
```

```
 ┌──────────────────────────────────────────────┐
 │  Gather Context                              │
 │                                              │
 │  • Performance data (get_performance)        │
 │    └ concept mastery via get_concept_mastery  │
 │    └ quiz history via get_quiz_history_summary│
 │  • Upcoming assessments from DB              │
 │  • Course name                               │
 │  • Redis cached (60s TTL)                    │
 └─────────────────────┬────────────────────────┘
                       ▼
 ┌──────────────────────────────────────────────┐
 │  Gemini 2.5 Flash (JSON mode)               │
 │                                              │
 │  System prompt: student context + data       │
 │  User message: student's question            │
 │                                              │
 │  Output:                                     │
 │    message: string                           │
 │    recommendations:                          │
 │      [{concept, action, priority}]           │
 │    suggested_quiz: object | null             │
 └──────────────────────────────────────────────┘
```

### Data In / Out

| | Details |
|---|---|
| **Input** | course_id, user message |
| **AI calls** | 1× Gemini Flash |
| **DB reads** | `courses`, `assessments`, mastery RPCs, quiz history RPC |
| **DB writes** | None |
| **Cache** | Performance data: Redis, 60s TTL |

**Key files:**
- `routers/coach.py` — endpoint
- `services/coach.py` — LLM chat
- `services/performance.py` — performance aggregation

---

## Workflow 6 — RAG Search & Q&A

```
Triggers:  POST /api/search   (hybrid search)
           POST /api/qa       (RAG question answering)
```

```
 ┌──────────────────────────────────────────────┐
 │  Search Flow                                 │
 │                                              │
 │  Query → hybrid_search RPC                   │
 │    • pgvector similarity (embedding)         │
 │    • BM25 full-text search (tsvector)        │
 │    • Reciprocal Rank Fusion                  │
 │  → enriched with lecture titles              │
 │  → <mark> highlighted terms                  │
 └──────────────────────────────────────────────┘

 ┌──────────────────────────────────────────────┐
 │  Q&A Flow                                    │
 │                                              │
 │  Query → embed (gemini-embedding-001,        │
 │           RETRIEVAL_QUERY)                   │
 │        → hybrid_search (top 8 chunks)        │
 │        → format as [Source N] context         │
 │        → Gemini 2.5 Flash (JSON mode)        │
 │                                              │
 │  Output:                                     │
 │    answer, confidence, source_chunks,        │
 │    follow_up_suggestions                     │
 └──────────────────────────────────────────────┘
```

### Data In / Out

| | Details |
|---|---|
| **Input** | Search query text, course_id |
| **AI calls** | Search: embedding only. Q&A: embedding + 1× Flash |
| **DB reads** | `lecture_chunks` (via hybrid_search RPC), `lectures` (titles) |
| **DB writes** | None |

**Key files:**
- `routers/search.py` — endpoints
- `services/search.py` — hybrid search
- `services/rag.py` — RAG Q&A
- `services/embedding.py` — query embedding

---

## Workflow 7 — Learn Mode

```
Trigger:  POST /api/learn/{course_id}/session/start
```

### Session Flow

```
 ┌──────────────────────────────────────────────┐
 │  Session Start                               │
 │                                              │
 │  get_study_priorities RPC                    │
 │    → select concepts by time budget:         │
 │      10min=1, 15min=1, 20min=2, 25min=2     │
 │                                              │
 │  Generate Flash Review Cards:                │
 │    lowest mastery concepts → reuse existing  │
 │    quiz_questions or generate via Flash      │
 └─────────────────────┬────────────────────────┘
                       ▼
 ┌──────────────────────────────────────────────┐
 │  Phase 1: Flash Review                       │
 │  Recognition-based MCQ cards                 │
 │  Submit: POST /session/{id}/flash-review     │
 └─────────────────────┬────────────────────────┘
                       ▼
 ┌──────────────────────────────────────────────┐
 │  Phase 2: Concept Briefs (per concept)       │
 │  Gemini 2.5 Flash                            │
 │                                              │
 │  Mastery-calibrated sections:                │
 │    what_is_this, why_it_matters,             │
 │    key_relationship + gut_check MCQ          │
 │                                              │
 │  Wrong gut-check → expanded clarification    │
 │    (2-3 sentence correction via Flash)       │
 └─────────────────────┬────────────────────────┘
                       ▼
 ┌──────────────────────────────────────────────┐
 │  Phase 3: Power Quiz                         │
 │  Gemini 2.5 Flash                            │
 │                                              │
 │  Grounded in lecture chunks (hybrid search)  │
 │  Question count by budget:                   │
 │    10min=6, 15min=8, 20+=12                  │
 │                                              │
 │  Per-answer feedback with:                   │
 │    • Speed-run detection (<3s = no combo)    │
 │    • Combo multipliers: 3→2x, 5→3x, 8→4x   │
 │    • XP awarded per answer                   │
 └─────────────────────┬────────────────────────┘
                       ▼
 ┌──────────────────────────────────────────────┐
 │  Session Complete                            │
 │                                              │
 │  • Award session_complete XP (25 base)       │
 │  • Update streak                             │
 │  • Check & award badges                      │
 │  • Generate tomorrow preview                 │
 └──────────────────────────────────────────────┘
```

### Data In / Out

| | Details |
|---|---|
| **Input** | course_id, time_budget_minutes |
| **AI calls** | Flash: flash card gen (if needed), concept briefs (per concept), power quiz gen, gut-check clarifications |
| **DB reads** | study priorities RPC, `concepts`, `quiz_questions`, `lecture_chunks` (hybrid search) |
| **DB writes** | `learn_sessions` (session_data JSONB), XP/streak/badge writes via gamification |

**Key files:**
- `routers/learn.py` — 8 endpoints
- `services/learn_session.py` — orchestrator
- `services/flash_review.py` — flash card selection/generation
- `services/concept_brief.py` — mastery-calibrated briefs
- `services/gamification.py` — XP awards

---

## Workflow 8 — Study Actions

```
Triggers:  GET /api/study-actions            (fast, deterministic)
           GET /api/study-actions/enhanced   (LLM-enhanced)
           GET /api/courses/{id}/study-actions
```

```
 ┌──────────────────────────────────────────────┐
 │  Deterministic Engine (5-tier priority)      │
 │                                              │
 │  1. upload_syllabus    (1.0)  — no syllabus  │
 │  2. review_syllabus    (0.95) — needs review │
 │  3. upload_lectures    (var)  — gap detection │
 │     └ compute_lecture_gap(): expected vs      │
 │       actual, respecting holidays & breaks   │
 │  4. assessment_prep    (var)  — urgency +    │
 │     weight + weak concepts                   │
 │  5. take_quiz          (var)  — weak concepts│
 └─────────────────────┬────────────────────────┘
                       │
                       ▼ (enhanced endpoint only)
 ┌──────────────────────────────────────────────┐
 │  LLM Enhancement  (Gemini 2.5 Flash)        │
 │                                              │
 │  Same data → personalized language +         │
 │  smart prioritization                        │
 │  Validates: action_type whitelist,           │
 │    course_id verification, cta_url fix       │
 └──────────────────────────────────────────────┘
```

### Data In / Out

| | Details |
|---|---|
| **Input** | user_id (all courses) or course_id |
| **AI calls** | Deterministic: 0. Enhanced: 1× Flash |
| **DB reads** | `courses`, `syllabi`, `assessments`, `lectures`, mastery RPCs |
| **DB writes** | None |

**Key files:**
- `routers/study_actions.py` — endpoints
- `services/study_actions.py` — deterministic engine
- `services/study_actions_llm.py` — LLM-enhanced engine

---

## Workflow 9 — Onboarding

```
Trigger:  POST /api/courses/{course_id}/onboarding/start
```

```
 ┌──────────────────────────────────────────────┐
 │  Path Detection (deterministic)              │
 │                                              │
 │  Based on semester dates:                    │
 │    just_starting / mid_semester /            │
 │    course_complete                           │
 └─────────────────────┬────────────────────────┘
                       ▼
 Steps (configurable per path):
   syllabus_upload → extraction_review →
   path_selection → personalized_message →
   lecture_catchup → past_results →
   study_plan → material_upload → practice_intro
                       │
                       ▼
 ┌──────────────────────────────────────────────┐
 │  Personalized Message (Gemini 2.5 Flash)    │
 │                                              │
 │  Generates study briefing referencing:       │
 │    assessments, weights, due dates           │
 └──────────────────────────────────────────────┘
                       │
                       ▼
 ┌──────────────────────────────────────────────┐
 │  Lecture Checklist (deterministic)           │
 │                                              │
 │  Expected slots: semester_start → today      │
 │  Respects holidays + break weeks             │
 └──────────────────────────────────────────────┘
                       │
                       ▼
 On completion (mid_semester path):
   seed_mastery_from_scores() →
     past assessment results → mastery_scores
```

### Data In / Out

| | Details |
|---|---|
| **Input** | course_id, semester context |
| **AI calls** | 1× Flash (personalized message only) |
| **DB reads** | `courses`, `syllabi`, `assessments` |
| **DB writes** | `courses` (onboarding fields), `user_onboarding`, `mastery_scores` (mid-semester seed) |

**Key files:**
- `routers/onboarding.py` — 9 endpoints
- `services/onboarding.py` — logic

---

## Workflow 10 — Gamification

```
Triggers:  Called internally by Learn Mode (WF 7)
           Exposed via GET /api/gamification/*
```

### XP System

```
 Source                    Base XP    Notes
 ──────────────────────────────────────────────
 flash_review_correct       5        Capped to 2 if mastery > 0.8
 flash_review_incorrect     2
 gut_check_correct         15
 quiz_correct              10
 quiz_combo_bonus          10        Disabled if answer < 3 seconds
 mastery_increase          50
 concept_mastered         100
 mastery_breakthrough     150
 session_complete          25
 misconception_resolved    75
 perfect_quiz             100
```

### Combo System

```
 Consecutive correct answers → multiplier
   3 correct → 2x
   5 correct → 3x
   8 correct → 4x
 Speed-run protection: < 3s answer → no combo
```

### Level Progression
Fibonacci-style thresholds: 100, 300, 600, 1100, 1900, ...

### Streak System
- Tracks consecutive study days
- Freeze: 1 per week (auto-resets weekly)
- Milestones: 3, 7, 14, 30, 60, 100 days

### Badge System (20 badges, 5 categories)

| Category | Badges | Trigger |
|----------|--------|---------|
| **Streak** | streak_3/7/14/30/60/100 | `session_complete` |
| **Mastery** | first_concept_mastered, concepts_5, course_expert, subject_scholar | `mastery_update` |
| **Assessment** | exam_ready, perfect_prep, clutch_player | `readiness_update` |
| **Behavior** | night_owl, early_bird, weekend_warrior, flash_master | `session_complete` |
| **Rare** | perfect_quiz, zero_to_hero, misconception_slayer | Various |

### Data In / Out

| | Details |
|---|---|
| **AI calls** | None (purely computational) |
| **DB reads** | `xp_events`, `user_levels`, `user_streaks`, `badges_earned`, mastery RPCs |
| **DB writes** | `xp_events`, `user_levels`, `user_streaks`, `badges_earned` |

**Key files:**
- `routers/gamification.py` — 9 endpoints
- `services/gamification.py` — XP, levels, streaks
- `services/badges.py` — 20 badge definitions + trigger-based checks

---

## Workflow 11 — Readiness & Grade Projection

```
Triggers:  GET /api/gamification/readiness
           GET /api/gamification/readiness/{id}
           GET /api/gamification/courses/{id}/grade-projection
```

```
 ┌──────────────────────────────────────────────┐
 │  Assessment Readiness (no LLM)              │
 │                                              │
 │  Weighted avg of concept mastery scores      │
 │  by relevance_score from                     │
 │  concept_assessment_links                    │
 │                                              │
 │  Mastery = accuracy × 0.6 +                 │
 │            recent_accuracy × 0.4             │
 │                                              │
 │  Bands: ready (≥80) | strong (≥60) |        │
 │         building (≥30) | danger (<30)        │
 └──────────────────────────────────────────────┘

 ┌──────────────────────────────────────────────┐
 │  Grade Projection (no LLM)                  │
 │                                              │
 │  Completed: actual student_score             │
 │  Upcoming: projected = readiness × 0.95      │
 │  Range: ±5 percentage points                │
 │  → letter grade (A/B/C/D/F)                 │
 └──────────────────────────────────────────────┘
```

### Data In / Out

| | Details |
|---|---|
| **AI calls** | None |
| **DB reads** | `concepts`, `concept_assessment_links`, `assessments`, mastery RPCs |
| **DB writes** | None |

**Key files:**
- `services/readiness.py` — readiness + grade projection

---

## Supabase RPC Functions

These PostgreSQL functions are called from Python via `supabase.rpc()`:

| Function | Purpose | Used By |
|----------|---------|---------|
| `hybrid_search` | Vector similarity + BM25 full-text via Reciprocal Rank Fusion | Search, RAG, Quiz Planner, Learn Mode |
| `get_concept_mastery` | Per-user concept mastery (accuracy, recent_accuracy, attempts) | Performance, Quiz Planner, Readiness, Badges, Tutor |
| `get_quiz_history_summary` | Quiz attempt aggregation | Performance, Coach |
| `get_study_priorities` | Prioritized study concepts for a course | Learn Mode, Study Actions |
| `increment_retry_count` | Increment lecture retry counter on failure | Lecture Pipeline |

---

## Database Tables at a Glance

### Content Tables (populated by Workflows 1-2)

| Table | Writers | Key Columns |
|-------|---------|-------------|
| `lectures` | WF 2 | processing_status, transcript (JSONB), title, duration_seconds |
| `lecture_chunks` | WF 2 | content, embedding (vector 2000), start_time, end_time, slide_number, fts |
| `concepts` | WF 2 | title, description, category, difficulty, embedding (vector), subconcepts, source_chunk_ids |
| `concept_assessment_links` | WF 2 | concept_id, assessment_id, relevance_score, mapping_confidence |
| `syllabi` | WF 1 | raw_extraction (JSONB), grade_breakdown, extraction_confidence, needs_review |
| `assessments` | WF 1 | title, type, due_date, weight_percent, topics, student_score |

### Interaction Tables (populated by Workflows 3-7)

| Table | Writers | Key Columns |
|-------|---------|-------------|
| `quizzes` | WF 3 | status, question_count, best_score, target_assessment_id |
| `quiz_questions` | WF 3 | question_type, question_text, options (JSONB), correct_answer, code_metadata |
| `quiz_attempts` | WF 3 | student_answer, is_correct, time_spent_seconds, code_grading_result |
| `tutor_sessions` | WF 4 | lesson_plan (JSONB), status, current_concept, questions_asked/correct |
| `tutor_session_events` | WF 4 | event_type, concept_title, is_correct |
| `learn_sessions` | WF 7 | session_data (JSONB), time_budget_minutes, status |

### Gamification Tables (populated by Workflow 10)

| Table | Writers | Key Columns |
|-------|---------|-------------|
| `xp_events` | WF 10 | amount, source, course_id, session_id |
| `user_levels` | WF 10 | total_xp, current_level, xp_to_next_level |
| `user_streaks` | WF 10 | current_streak, longest_streak, streak_freezes_available |
| `badges_earned` | WF 10 | badge_id, earned_at, metadata |
| `mastery_scores` | WF 9 | mastery_score, confidence, source |

---

## Shared Infrastructure

| Component | File | Purpose |
|-----------|------|---------|
| Gemini Client | `services/genai_client.py` | Loop-aware singleton, thread-safe, auto-recreates on event loop change |
| Redis Cache | `services/redis_client.py` | Async pool with `cache_get`/`cache_set`/`cache_delete`, JSON serialization |
| Task Queue | `services/task_queue.py` | arq (Redis-backed) with daemon thread fallback for background jobs |
| Settings | `config/settings.py` | pydantic-settings with `@lru_cache`, loaded from `.env` |

---

## Dependency Graph (what must exist before each workflow runs)

```
WF 1: Syllabus        → nothing (entry point)
WF 2: Lecture          → benefits from WF 1 (assessments for concept mapping)
WF 3: Quiz Gen         → requires WF 2 (concepts + chunks)
WF 4: Tutor            → requires WF 2 (concepts), benefits from WF 1
WF 5: Coach            → requires WF 2 (mastery), WF 3 (quiz history)
WF 6: RAG Search       → requires WF 2 (chunks with embeddings)
WF 7: Learn Mode       → requires WF 2 (concepts + chunks), integrates WF 10
WF 8: Study Actions    → requires WF 1 (syllabi), benefits from WF 2
WF 9: Onboarding       → benefits from WF 1 (syllabus for personalization)
WF 10: Gamification    → called by WF 7 (no standalone data deps)
WF 11: Readiness       → requires WF 2 (concept_assessment_links) + WF 3 (mastery)
```
