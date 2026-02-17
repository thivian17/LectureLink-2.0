-- ============================================================
-- Phase 3: Adaptive Study Coach
-- SQL functions for performance analytics (no new tables)
-- ============================================================

-- ============================================================
-- Function 1: get_concept_mastery
-- Returns per-concept performance metrics for a student
-- ============================================================
CREATE OR REPLACE FUNCTION get_concept_mastery(
    p_course_id UUID,
    p_user_id UUID
)
RETURNS TABLE (
    concept_id UUID,
    concept_title TEXT,
    concept_description TEXT,
    concept_category TEXT,
    difficulty_estimate FLOAT,
    lecture_id UUID,
    total_attempts INT,
    correct_attempts INT,
    accuracy FLOAT,
    avg_time_seconds FLOAT,
    recent_accuracy FLOAT,
    trend TEXT
) AS $$
BEGIN
    RETURN QUERY
    WITH attempt_data AS (
        SELECT
            qq.concept_id AS cid,
            qa.is_correct,
            qa.time_spent_seconds,
            qa.created_at,
            ROW_NUMBER() OVER (
                PARTITION BY qq.concept_id
                ORDER BY qa.created_at DESC
            ) AS attempt_rank
        FROM quiz_attempts qa
        JOIN quiz_questions qq ON qa.question_id = qq.id
        WHERE qa.user_id = p_user_id
          AND qq.concept_id IS NOT NULL
    ),
    aggregated AS (
        SELECT
            ad.cid,
            COUNT(*)::INT AS total_attempts,
            SUM(CASE WHEN ad.is_correct THEN 1 ELSE 0 END)::INT AS correct_attempts,
            CASE WHEN COUNT(*) > 0
                 THEN SUM(CASE WHEN ad.is_correct THEN 1.0 ELSE 0.0 END) / COUNT(*)
                 ELSE 0.0
            END AS accuracy,
            COALESCE(AVG(ad.time_spent_seconds)::FLOAT, 0.0) AS avg_time_seconds,
            CASE WHEN COUNT(*) FILTER (WHERE ad.attempt_rank <= 5) > 0
                 THEN SUM(CASE WHEN ad.is_correct AND ad.attempt_rank <= 5 THEN 1.0 ELSE 0.0 END)
                      / GREATEST(COUNT(*) FILTER (WHERE ad.attempt_rank <= 5), 1)
                 ELSE 0.0
            END AS recent_accuracy,
            CASE WHEN COUNT(*) FILTER (WHERE ad.attempt_rank > 5 AND ad.attempt_rank <= 10) > 0
                 THEN SUM(CASE WHEN ad.is_correct AND ad.attempt_rank > 5 AND ad.attempt_rank <= 10 THEN 1.0 ELSE 0.0 END)
                      / GREATEST(COUNT(*) FILTER (WHERE ad.attempt_rank > 5 AND ad.attempt_rank <= 10), 1)
                 ELSE NULL
            END AS older_accuracy
        FROM attempt_data ad
        GROUP BY ad.cid
    )
    SELECT
        c.id,
        c.title,
        c.description,
        c.category,
        COALESCE(c.difficulty_estimate, 0.5)::FLOAT,
        c.lecture_id,
        COALESCE(a.total_attempts, 0)::INT,
        COALESCE(a.correct_attempts, 0)::INT,
        COALESCE(a.accuracy, 0.0)::FLOAT,
        COALESCE(a.avg_time_seconds, 0.0)::FLOAT,
        COALESCE(a.recent_accuracy, 0.0)::FLOAT,
        CASE
            WHEN a.total_attempts IS NULL OR a.total_attempts = 0 THEN 'new'
            WHEN a.older_accuracy IS NULL THEN 'stable'
            WHEN a.recent_accuracy > a.older_accuracy + 0.15 THEN 'improving'
            WHEN a.recent_accuracy < a.older_accuracy - 0.15 THEN 'declining'
            ELSE 'stable'
        END
    FROM concepts c
    LEFT JOIN aggregated a ON a.cid = c.id
    WHERE c.course_id = p_course_id
      AND c.user_id = p_user_id
    ORDER BY COALESCE(a.accuracy, 0.0) ASC, COALESCE(c.difficulty_estimate, 0.5) DESC;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;


-- ============================================================
-- Function 2: get_quiz_history_summary
-- Returns recent quiz history for a student in a course
-- ============================================================
CREATE OR REPLACE FUNCTION get_quiz_history_summary(
    p_course_id UUID,
    p_user_id UUID
)
RETURNS TABLE (
    quiz_id UUID,
    quiz_title TEXT,
    difficulty TEXT,
    best_score FLOAT,
    attempt_count INT,
    question_count INT,
    created_at TIMESTAMPTZ
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        q.id,
        q.title,
        q.difficulty,
        q.best_score,
        q.attempt_count,
        q.question_count,
        q.created_at
    FROM quizzes q
    WHERE q.course_id = p_course_id
      AND q.user_id = p_user_id
      AND q.status = 'ready'
    ORDER BY q.created_at DESC
    LIMIT 20;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;
