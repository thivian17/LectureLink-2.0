-- Migration 005b: Expand quiz_questions question_type constraint for coding questions.
-- The original constraint (001) only allowed 'mcq', 'true_false', 'short_answer'.
-- Migration 005 added coding question support but didn't update the constraint.

ALTER TABLE quiz_questions DROP CONSTRAINT IF EXISTS quiz_questions_question_type_check;

ALTER TABLE quiz_questions ADD CONSTRAINT quiz_questions_question_type_check
    CHECK (question_type IN ('mcq', 'true_false', 'short_answer', 'code_writing', 'code_fix', 'code_explain'));
