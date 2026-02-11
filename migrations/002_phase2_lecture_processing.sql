BEGIN;

-- Enable pgvector if not already enabled
CREATE EXTENSION IF NOT EXISTS vector;

-- ============================================================
-- Table 1: lectures
-- ============================================================
CREATE TABLE IF NOT EXISTS lectures (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    course_id UUID REFERENCES courses(id) ON DELETE CASCADE,
    user_id UUID REFERENCES auth.users(id),
    title TEXT NOT NULL,
    lecture_number INT,
    lecture_date DATE,
    audio_url TEXT,
    slides_url TEXT,
    transcript JSONB,
    summary TEXT,
    processing_status TEXT DEFAULT 'pending'
        CHECK (processing_status IN ('pending', 'processing', 'completed', 'failed')),
    processing_stage TEXT,
    processing_progress FLOAT DEFAULT 0.0,
    processing_error TEXT,
    retry_count INT DEFAULT 0,
    last_error_at TIMESTAMPTZ,
    duration_seconds INT,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_lectures_course ON lectures(course_id, lecture_number);
CREATE INDEX IF NOT EXISTS idx_lectures_status ON lectures(processing_status);
CREATE INDEX IF NOT EXISTS idx_lectures_user ON lectures(user_id);

-- ============================================================
-- Table 2: lecture_chunks
-- ============================================================
CREATE TABLE IF NOT EXISTS lecture_chunks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    lecture_id UUID REFERENCES lectures(id) ON DELETE CASCADE,
    user_id UUID REFERENCES auth.users(id),
    chunk_index INT NOT NULL,
    content TEXT NOT NULL,
    start_time FLOAT,
    end_time FLOAT,
    slide_number INT,
    embedding vector(2000),
    metadata JSONB DEFAULT '{}',
    fts tsvector GENERATED ALWAYS AS (to_tsvector('english', content)) STORED,
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_chunks_lecture ON lecture_chunks(lecture_id, chunk_index);
CREATE INDEX IF NOT EXISTS idx_chunks_user ON lecture_chunks(user_id);
CREATE INDEX IF NOT EXISTS idx_chunks_embedding ON lecture_chunks USING hnsw (embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 64);
CREATE INDEX IF NOT EXISTS idx_chunks_fts ON lecture_chunks USING GIN(fts);

-- ============================================================
-- Table 3: concepts (exists from Phase 1)
-- ============================================================
CREATE TABLE IF NOT EXISTS concepts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    course_id UUID REFERENCES courses(id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    description TEXT,
    created_at TIMESTAMPTZ DEFAULT now()
);

ALTER TABLE concepts ADD COLUMN IF NOT EXISTS lecture_id UUID REFERENCES lectures(id) ON DELETE CASCADE;
ALTER TABLE concepts ADD COLUMN IF NOT EXISTS user_id UUID REFERENCES auth.users(id);
ALTER TABLE concepts ADD COLUMN IF NOT EXISTS category TEXT;
ALTER TABLE concepts ADD COLUMN IF NOT EXISTS difficulty_estimate FLOAT DEFAULT 0.5;
ALTER TABLE concepts ADD COLUMN IF NOT EXISTS source_chunk_ids UUID[];
ALTER TABLE concepts ADD COLUMN IF NOT EXISTS embedding vector(2000);

CREATE INDEX IF NOT EXISTS idx_concepts_course ON concepts(course_id);
CREATE INDEX IF NOT EXISTS idx_concepts_lecture ON concepts(lecture_id);
CREATE INDEX IF NOT EXISTS idx_concepts_user ON concepts(user_id);

-- ============================================================
-- Table 4: concept_assessment_links (exists from Phase 1)
-- ============================================================
CREATE TABLE IF NOT EXISTS concept_assessment_links (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    concept_id UUID REFERENCES concepts(id) ON DELETE CASCADE,
    assessment_id UUID REFERENCES assessments(id) ON DELETE CASCADE,
    relevance_score FLOAT NOT NULL CHECK (relevance_score BETWEEN 0 AND 1),
    created_at TIMESTAMPTZ DEFAULT now(),
    UNIQUE(concept_id, assessment_id)
);

ALTER TABLE concept_assessment_links ADD COLUMN IF NOT EXISTS user_id UUID REFERENCES auth.users(id);
ALTER TABLE concept_assessment_links ADD COLUMN IF NOT EXISTS mapping_confidence FLOAT DEFAULT 0.8;

CREATE INDEX IF NOT EXISTS idx_cal_concept ON concept_assessment_links(concept_id);
CREATE INDEX IF NOT EXISTS idx_cal_assessment ON concept_assessment_links(assessment_id);
CREATE INDEX IF NOT EXISTS idx_cal_user ON concept_assessment_links(user_id);

-- ============================================================
-- Table 5: quizzes
-- ============================================================
CREATE TABLE IF NOT EXISTS quizzes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    course_id UUID REFERENCES courses(id) ON DELETE CASCADE,
    user_id UUID REFERENCES auth.users(id),
    title TEXT NOT NULL,
    target_assessment_id UUID REFERENCES assessments(id) ON DELETE SET NULL,
    difficulty TEXT DEFAULT 'medium'
        CHECK (difficulty IN ('easy', 'medium', 'hard', 'adaptive')),
    status TEXT DEFAULT 'pending'
        CHECK (status IN ('pending', 'generating', 'ready', 'failed')),
    best_score FLOAT,
    attempt_count INT DEFAULT 0,
    last_attempted_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_quizzes_course ON quizzes(course_id, user_id);

-- ============================================================
-- Table 6: quiz_questions
-- ============================================================
CREATE TABLE IF NOT EXISTS quiz_questions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    quiz_id UUID REFERENCES quizzes(id) ON DELETE CASCADE,
    user_id UUID REFERENCES auth.users(id),
    question_index INT NOT NULL,
    question_type TEXT NOT NULL
        CHECK (question_type IN ('mcq', 'true_false', 'short_answer')),
    question_text TEXT NOT NULL,
    options JSONB,
    correct_answer TEXT NOT NULL,
    explanation TEXT NOT NULL,
    source_chunk_ids UUID[],
    concept_id UUID REFERENCES concepts(id) ON DELETE SET NULL,
    difficulty FLOAT DEFAULT 0.5,
    review_status TEXT DEFAULT 'accepted'
        CHECK (review_status IN ('accepted', 'flagged', 'rejected')),
    reviewer_notes TEXT,
    critic_log JSONB,
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_questions_quiz ON quiz_questions(quiz_id, question_index);
CREATE INDEX IF NOT EXISTS idx_questions_user ON quiz_questions(user_id);

-- ============================================================
-- Table 7: quiz_attempts
-- ============================================================
CREATE TABLE IF NOT EXISTS quiz_attempts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    quiz_id UUID REFERENCES quizzes(id) ON DELETE CASCADE,
    user_id UUID REFERENCES auth.users(id),
    question_id UUID REFERENCES quiz_questions(id) ON DELETE CASCADE,
    student_answer TEXT NOT NULL,
    is_correct BOOLEAN NOT NULL,
    time_spent_seconds INT,
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_attempts_quiz_user ON quiz_attempts(quiz_id, user_id);
CREATE INDEX IF NOT EXISTS idx_attempts_question ON quiz_attempts(question_id, user_id, created_at DESC);

-- ============================================================
-- Table 8: rate_limit_events
-- ============================================================
CREATE TABLE IF NOT EXISTS rate_limit_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES auth.users(id) ON DELETE CASCADE,
    action TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_rate_limit_user_action ON rate_limit_events(user_id, action, created_at DESC);

-- ============================================================
-- RLS Policies (drop all first to be fully idempotent)
-- ============================================================
ALTER TABLE lectures ENABLE ROW LEVEL SECURITY;
ALTER TABLE lecture_chunks ENABLE ROW LEVEL SECURITY;
ALTER TABLE concepts ENABLE ROW LEVEL SECURITY;
ALTER TABLE concept_assessment_links ENABLE ROW LEVEL SECURITY;
ALTER TABLE quizzes ENABLE ROW LEVEL SECURITY;
ALTER TABLE quiz_questions ENABLE ROW LEVEL SECURITY;
ALTER TABLE quiz_attempts ENABLE ROW LEVEL SECURITY;
ALTER TABLE rate_limit_events ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS lectures_user_policy ON lectures;
DROP POLICY IF EXISTS chunks_user_policy ON lecture_chunks;
DROP POLICY IF EXISTS concepts_user_policy ON concepts;
DROP POLICY IF EXISTS cal_user_policy ON concept_assessment_links;
DROP POLICY IF EXISTS quizzes_user_policy ON quizzes;
DROP POLICY IF EXISTS questions_user_policy ON quiz_questions;
DROP POLICY IF EXISTS attempts_user_policy ON quiz_attempts;
DROP POLICY IF EXISTS rate_limit_user_policy ON rate_limit_events;

CREATE POLICY lectures_user_policy ON lectures
    FOR ALL USING (user_id = auth.uid());
CREATE POLICY chunks_user_policy ON lecture_chunks
    FOR ALL USING (user_id = auth.uid());
CREATE POLICY concepts_user_policy ON concepts
    FOR ALL USING (user_id = auth.uid());
CREATE POLICY cal_user_policy ON concept_assessment_links
    FOR ALL USING (user_id = auth.uid());
CREATE POLICY quizzes_user_policy ON quizzes
    FOR ALL USING (user_id = auth.uid());
CREATE POLICY questions_user_policy ON quiz_questions
    FOR ALL USING (user_id = auth.uid());
CREATE POLICY attempts_user_policy ON quiz_attempts
    FOR ALL USING (user_id = auth.uid());
CREATE POLICY rate_limit_user_policy ON rate_limit_events
    FOR ALL USING (user_id = auth.uid());

-- ============================================================
-- Updated_at trigger for lectures table
-- ============================================================
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS lectures_updated_at ON lectures;
CREATE TRIGGER lectures_updated_at
    BEFORE UPDATE ON lectures
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

COMMIT;