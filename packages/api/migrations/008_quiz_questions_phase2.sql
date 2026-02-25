-- 008_quiz_questions_phase2.sql
-- Add Phase 2 columns to quiz_questions for full quiz pipeline support.

ALTER TABLE quiz_questions ADD COLUMN IF NOT EXISTS quiz_id UUID REFERENCES quizzes(id) ON DELETE CASCADE;
ALTER TABLE quiz_questions ADD COLUMN IF NOT EXISTS source_chunk_ids UUID[] DEFAULT '{}';
ALTER TABLE quiz_questions ADD COLUMN IF NOT EXISTS user_id UUID REFERENCES auth.users(id) ON DELETE CASCADE;
ALTER TABLE quiz_questions ADD COLUMN IF NOT EXISTS difficulty TEXT DEFAULT 'medium';
ALTER TABLE quiz_questions ADD COLUMN IF NOT EXISTS question_index INT;
ALTER TABLE quiz_questions ADD COLUMN IF NOT EXISTS review_status TEXT DEFAULT 'pending'
    CHECK (review_status IN ('pending', 'approved', 'rejected'));
ALTER TABLE quiz_questions ADD COLUMN IF NOT EXISTS reviewer_notes TEXT;

-- Indexes
CREATE INDEX IF NOT EXISTS idx_quiz_questions_quiz ON quiz_questions(quiz_id, question_index);
CREATE INDEX IF NOT EXISTS idx_quiz_questions_user ON quiz_questions(user_id);
CREATE INDEX IF NOT EXISTS idx_quiz_questions_review ON quiz_questions(review_status);

-- RLS
ALTER TABLE quiz_questions ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS quiz_questions_policy ON quiz_questions;
CREATE POLICY quiz_questions_policy ON quiz_questions FOR ALL USING (user_id = auth.uid());
