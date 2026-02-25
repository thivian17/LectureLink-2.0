-- Migration 005: Add coding practice question support
-- Adds columns for code question metadata, AI grading results, and hint tracking.

-- Add code_metadata JSONB column to quiz_questions
-- Only populated when question_type IN ('code_writing', 'code_fix', 'code_explain')
ALTER TABLE quiz_questions ADD COLUMN IF NOT EXISTS code_metadata JSONB DEFAULT NULL;

COMMENT ON COLUMN quiz_questions.code_metadata IS
'Coding question metadata: language, starter_code, reference_solution, grading_rubric, hints, etc.';

-- Add code_grading_result JSONB column to quiz_attempts
ALTER TABLE quiz_attempts ADD COLUMN IF NOT EXISTS code_grading_result JSONB DEFAULT NULL;

COMMENT ON COLUMN quiz_attempts.code_grading_result IS
'AI grading result for coding questions: rubric_scores, line_feedback, overall_feedback, suggested_improvement.';

-- Add hints_used column to quiz_attempts for tracking hint usage
ALTER TABLE quiz_attempts ADD COLUMN IF NOT EXISTS hints_used INTEGER DEFAULT 0;
