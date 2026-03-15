-- Migration 010: Readiness V2 — optimize signal queries

-- Index for freshness: latest interaction per concept per user
CREATE INDEX IF NOT EXISTS idx_learning_events_freshness
    ON learning_events(user_id, concept_id, created_at DESC);

-- Index for coverage: distinct concepts interacted with
CREATE INDEX IF NOT EXISTS idx_learning_events_coverage
    ON learning_events(user_id, course_id, concept_id);

-- Index for quiz_attempts by user + concept for practice signal
CREATE INDEX IF NOT EXISTS idx_quiz_attempts_user_concept
    ON quiz_attempts(user_id)
    INCLUDE (is_correct);

-- Index for learn_sessions effort signal: completed sessions per course
CREATE INDEX IF NOT EXISTS idx_learn_sessions_effort
    ON learn_sessions(user_id, course_id, status, completed_at DESC);

-- Index for tutor_sessions effort signal
CREATE INDEX IF NOT EXISTS idx_tutor_sessions_effort
    ON tutor_sessions(user_id, course_id, status, completed_at DESC);
