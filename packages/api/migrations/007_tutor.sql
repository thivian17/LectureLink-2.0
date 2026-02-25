-- 007_tutor.sql
-- Study Tutor: interactive AI teaching sessions with grading and progress tracking.

-- Tutor sessions — one per study session
CREATE TABLE IF NOT EXISTS tutor_sessions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES auth.users(id) ON DELETE CASCADE,
    course_id UUID REFERENCES courses(id) ON DELETE CASCADE,
    target_assessment_id UUID REFERENCES assessments(id) ON DELETE SET NULL,
    mode TEXT NOT NULL CHECK (mode IN ('diagnostic', 'full_lesson', 'custom_topic')),
    custom_topic TEXT,
    status TEXT NOT NULL DEFAULT 'active'
        CHECK (status IN ('active', 'paused', 'completed', 'abandoned')),
    lesson_plan JSONB,
    current_concept_index INT DEFAULT 0,
    current_step_index INT DEFAULT 0,
    concepts_planned INT DEFAULT 0,
    concepts_completed INT DEFAULT 0,
    questions_asked INT DEFAULT 0,
    questions_correct INT DEFAULT 0,
    duration_seconds INT DEFAULT 0,
    suggested_duration_minutes INT DEFAULT 25,
    started_at TIMESTAMPTZ DEFAULT timezone('utc', now()),
    paused_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    summary TEXT,
    created_at TIMESTAMPTZ DEFAULT timezone('utc', now())
);

CREATE INDEX IF NOT EXISTS idx_tutor_sessions_user ON tutor_sessions(user_id, course_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_tutor_sessions_active ON tutor_sessions(user_id, course_id) WHERE status = 'active';

ALTER TABLE tutor_sessions ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tutor_sessions_policy ON tutor_sessions;
CREATE POLICY tutor_sessions_policy ON tutor_sessions FOR ALL USING (user_id = auth.uid());

-- Session events — every interaction within a session
CREATE TABLE IF NOT EXISTS tutor_session_events (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    session_id UUID REFERENCES tutor_sessions(id) ON DELETE CASCADE,
    user_id UUID NOT NULL,
    course_id UUID NOT NULL,
    event_type TEXT NOT NULL,
    concept_id UUID,
    concept_title TEXT,
    question_type TEXT,
    question_text TEXT,
    student_answer TEXT,
    is_correct BOOLEAN,
    grading_result JSONB,
    grading_confidence FLOAT,
    misconception_type TEXT,
    reteach_triggered BOOLEAN DEFAULT false,
    time_spent_seconds INT,
    block_type TEXT,
    created_at TIMESTAMPTZ DEFAULT timezone('utc', now())
);

CREATE INDEX IF NOT EXISTS idx_session_events_session ON tutor_session_events(session_id, created_at);
CREATE INDEX IF NOT EXISTS idx_session_events_concept ON tutor_session_events(user_id, concept_id, created_at DESC);

ALTER TABLE tutor_session_events ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tutor_events_policy ON tutor_session_events;
CREATE POLICY tutor_events_policy ON tutor_session_events FOR ALL USING (user_id = auth.uid());

-- Grading feedback — for beta long-answer accuracy tracking
CREATE TABLE IF NOT EXISTS grading_feedback (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    event_id UUID REFERENCES tutor_session_events(id) ON DELETE CASCADE,
    user_id UUID NOT NULL,
    feedback_type TEXT NOT NULL CHECK (feedback_type IN ('accurate', 'inaccurate')),
    feedback_text TEXT,
    created_at TIMESTAMPTZ DEFAULT timezone('utc', now())
);

ALTER TABLE grading_feedback ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS grading_feedback_policy ON grading_feedback;
CREATE POLICY grading_feedback_policy ON grading_feedback FOR ALL USING (user_id = auth.uid());
