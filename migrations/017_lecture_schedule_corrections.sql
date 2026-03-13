-- Stores user corrections to the auto-generated lecture schedule.
-- Used to improve extraction accuracy over time.

CREATE TABLE IF NOT EXISTS lecture_schedule_corrections (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    course_id UUID NOT NULL REFERENCES courses(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,

    -- What was auto-generated
    original_lecture_number INT,
    original_title TEXT,
    original_date DATE,
    original_topic_hint TEXT,

    -- What the user corrected it to
    corrected_title TEXT,
    corrected_date DATE,
    corrected_description TEXT,

    -- Whether this was an added lecture (not in the original checklist)
    is_addition BOOLEAN NOT NULL DEFAULT FALSE,

    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_lecture_corrections_course
    ON lecture_schedule_corrections(course_id);

-- RLS
ALTER TABLE lecture_schedule_corrections ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users manage own corrections"
    ON lecture_schedule_corrections
    FOR ALL
    USING (user_id = auth.uid());
