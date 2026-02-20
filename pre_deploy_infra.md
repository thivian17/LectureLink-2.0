# Pre-Deploy Infrastructure Audit

**Date:** 2026-02-17
**Branch:** main (`ef5a1ef`)

---

## 1. Environment Variable Audit

### Backend (`packages/api/src/lecturelink_api/config.py`)

| Field                  | Required | Default         | Notes                                    |
|------------------------|----------|-----------------|------------------------------------------|
| `SUPABASE_URL`         | YES      | —               | Supabase project URL                     |
| `SUPABASE_ANON_KEY`    | YES      | —               | Supabase anonymous/public key            |
| `SUPABASE_SERVICE_KEY` | No       | `""`            | Admin key for RLS-bypass ops             |
| `GOOGLE_API_KEY`       | No       | `""`            | Gemini LLM API key                       |
| `GOOGLE_CLOUD_PROJECT` | No       | `""`            | GCP project ID (Vertex AI)               |
| `ENVIRONMENT`          | No       | `"development"` | Set to `"production"` in prod            |
| `DATABASE_URL`         | No       | `""`            | Direct Postgres connection string        |

### Frontend (`packages/web/`)

| Variable                       | Required | Default                  | Used In                            |
|--------------------------------|----------|--------------------------|------------------------------------|
| `NEXT_PUBLIC_SUPABASE_URL`     | YES      | —                        | client.ts, server.ts, middleware.ts |
| `NEXT_PUBLIC_SUPABASE_ANON_KEY`| YES      | —                        | client.ts, server.ts, middleware.ts |
| `NEXT_PUBLIC_API_URL`          | No       | `http://localhost:8000`  | api.ts                             |
| `NEXT_PUBLIC_USE_MOCKS`        | No       | (falsy)                  | mock-api.ts                        |

### Result: PASS
- All required fields documented
- `env.example` created at repo root with all vars + comments

---

## 2. Database Migration Check

**4 migration files found** (tracked in git):

| File                               | Phase | Description                         |
|------------------------------------|-------|-------------------------------------|
| `001_phase1_schema.sql`            | 1     | Core tables (courses, syllabi, assessments, concepts) |
| `002_phase2_lecture_processing.sql` | 2     | Lecture processing tables + pgvector |
| `002b_hybrid_search.sql`           | 2     | hybrid_search() SQL function         |
| `003_phase3_study_coach.sql`       | 3     | Study coach analytics SQL functions  |

### Result: PASS
- Sequential numbering with clear phase labels
- All migrations present and readable

---

## 3. Docker Build Readiness

**No Dockerfiles found.** No `.dockerignore` files found.

This is expected — Dockerfiles are a Phase 4 deliverable and have not been created yet.

### Result: PASS (not yet applicable)
- Dockerfiles not yet created — Phase 4 Step 2 deliverable

---

## 4. Dependency Security Scan

### Backend (`pip-audit`)

| Package        | Version | CVE              | Severity     | Fix Version | Description                              |
|----------------|---------|------------------|--------------|-------------|------------------------------------------|
| `cryptography` | 46.0.4  | CVE-2026-26007   | HIGH         | 46.0.5      | Subgroup attack on SECT binary curves    |
| `pillow`       | 12.1.0  | CVE-2026-25990   | CRITICAL     | 12.1.1      | Out-of-bounds write on malformed PSD     |

**Action required:** Update `cryptography>=46.0.5` and `pillow>=12.1.1` before production deployment.

### Frontend (`npm audit --production`)

**0 vulnerabilities found.**

### Result: FAIL
- 2 backend vulnerabilities need patching (1 HIGH, 1 CRITICAL)

---

## 5. Git Cleanliness

### Uncommitted Changes: YES (dirty working tree)
- **48 modified files** (staged/unstaged) — mostly in `packages/api/`
- **2 untracked files:** `pre_deploy_backend.md`, `test-results.txt`

### Recent Commits

| Hash      | Message                                                        |
|-----------|----------------------------------------------------------------|
| `ef5a1ef` | Phase 3: Study coach, study actions, and performance tracking  |
| `e353712` | Fix quiz answer checking, UI bugs, and assessments tab         |
| `e2e32ab` | Fix event loop blocking and lecture detail API response         |
| `2400c97` | Phase 2: Lecture processing pipeline, quiz system, search/RAG  |
| `beda880` | Phase 1: Full syllabus extraction pipeline with E2E tests      |

### Result: FAIL
- Working tree is dirty — 48 modified files need to be committed or stashed before deploy

---

## Overall Verdict: PASS WITH NOTES

| Check              | Status             | Action Needed                                      |
|--------------------|--------------------|----------------------------------------------------|
| Env audit          | PASS               | `env.example` created                              |
| Migrations         | PASS               | 4 files, sequential, all readable                  |
| Dockerfiles        | PASS (N/A)         | Not yet created (Phase 4 deliverable)              |
| Security scan      | FAIL               | Bump `cryptography` to 46.0.5, `pillow` to 12.1.1 |
| Git cleanliness    | FAIL               | 48 uncommitted changes                             |

### Blockers Before Deploy
1. **Patch `cryptography` and `pillow`** — both have known HIGH/CRITICAL CVEs with available fixes
2. **Commit or stash all working tree changes** — 48 modified files currently uncommitted
3. **Create Dockerfiles** (Phase 4) — needed for containerized deployment
