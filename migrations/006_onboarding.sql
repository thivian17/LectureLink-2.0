-- 006_onboarding.sql
-- Track onboarding state per course and user-level welcome flag.

-- Onboarding path: 'just_starting', 'mid_semester', 'course_complete', NULL = not started
ALTER TABLE courses ADD COLUMN IF NOT EXISTS onboarding_path TEXT DEFAULT NULL;

-- Current step in the onboarding flow. NULL = completed or not started.
-- Values vary by path: 'syllabus_upload', 'review_extraction', 'path_selection',
-- 'personalized_message', 'lecture_catchup', 'past_results', 'study_plan',
-- 'material_upload', 'practice_intro'
ALTER TABLE courses ADD COLUMN IF NOT EXISTS onboarding_step TEXT DEFAULT NULL;

ALTER TABLE courses ADD COLUMN IF NOT EXISTS onboarding_completed_at TIMESTAMPTZ DEFAULT NULL;

-- 'active' = normal deadline-aware mode, 'review' = no deadline pressure (Path 3)
ALTER TABLE courses ADD COLUMN IF NOT EXISTS mode TEXT NOT NULL DEFAULT 'active';

-- Cached LLM-generated personalized message
ALTER TABLE courses ADD COLUMN IF NOT EXISTS onboarding_welcome JSONB DEFAULT NULL;

-- Past assessment results for mid-semester catch-up (Path 2)
ALTER TABLE assessments ADD COLUMN IF NOT EXISTS student_score FLOAT DEFAULT NULL;

-- Track whether user has completed first-time global onboarding
CREATE TABLE IF NOT EXISTS user_onboarding (
    user_id UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
    has_seen_welcome BOOLEAN DEFAULT false,
    first_course_created_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT now()
);

ALTER TABLE user_onboarding ENABLE ROW LEVEL SECURITY;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_policies
        WHERE tablename = 'user_onboarding' AND policyname = 'user_onboarding_policy'
    ) THEN
        CREATE POLICY user_onboarding_policy ON user_onboarding
            FOR ALL USING (user_id = auth.uid());
    END IF;
END
$$;
