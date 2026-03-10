-- Migration 009: Quiz unification — add source tracking and reuse columns
-- Enables Power Quiz question persistence and reuse across sessions.

-- Add source column to track where questions came from
ALTER TABLE quiz_questions ADD COLUMN IF NOT EXISTS source TEXT DEFAULT 'standalone'
    CHECK (source IN ('standalone', 'power_quiz', 'flash_review', 'tutor'));

-- Add reuse tracking columns
ALTER TABLE quiz_questions ADD COLUMN IF NOT EXISTS times_shown INT DEFAULT 0;
ALTER TABLE quiz_questions ADD COLUMN IF NOT EXISTS times_correct INT DEFAULT 0;
ALTER TABLE quiz_questions ADD COLUMN IF NOT EXISTS last_shown_at TIMESTAMPTZ;

-- Make quiz_id nullable so power_quiz questions don't need a parent quiz
ALTER TABLE quiz_questions ALTER COLUMN quiz_id DROP NOT NULL;

-- Index for efficient reuse queries
CREATE INDEX IF NOT EXISTS idx_quiz_questions_reuse
    ON quiz_questions(concept_id, question_type, source, times_shown);

-- Learning events table for unified event tracking across all study modes
CREATE TABLE IF NOT EXISTS learning_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES auth.users(id) NOT NULL,
    course_id UUID REFERENCES courses(id) ON DELETE CASCADE NOT NULL,
    concept_id UUID REFERENCES concepts(id) ON DELETE SET NULL,
    event_type TEXT NOT NULL
        CHECK (event_type IN (
            'flash_review', 'gut_check', 'power_quiz',
            'tutor_check', 'practice_test', 'coding_practice'
        )),
    is_correct BOOLEAN,
    student_answer TEXT,
    time_ms INT,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_learning_events_user_course
    ON learning_events(user_id, course_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_learning_events_concept
    ON learning_events(concept_id, created_at DESC);

ALTER TABLE learning_events ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS learning_events_user_policy ON learning_events;
CREATE POLICY learning_events_user_policy ON learning_events
    FOR ALL USING (user_id = auth.uid());

-- Helper function to increment question stats after an answer
CREATE OR REPLACE FUNCTION increment_question_correct(
    p_question_id UUID,
    p_is_correct BOOLEAN
) RETURNS VOID AS $$
BEGIN
    UPDATE quiz_questions
    SET times_shown = COALESCE(times_shown, 0) + 1,
        times_correct = CASE WHEN p_is_correct
            THEN COALESCE(times_correct, 0) + 1
            ELSE COALESCE(times_correct, 0)
        END,
        last_shown_at = now()
    WHERE id = p_question_id;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;
