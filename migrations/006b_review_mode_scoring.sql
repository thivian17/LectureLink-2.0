-- Migration 006b: Update priority scoring to respect courses.mode
-- When mode = 'review': prioritize mastery gap and FSRS due dates (no deadline urgency)
-- When mode = 'active' (default): keep existing deadline + weight scoring
--
-- Depends on: 006_onboarding.sql (adds courses.mode column)

CREATE OR REPLACE FUNCTION get_study_priorities(p_course_id UUID)
RETURNS TABLE (
    assessment_id UUID,
    title TEXT,
    course_id UUID,
    due_date DATE,
    weight_percent FLOAT,
    priority_score FLOAT
)
LANGUAGE sql STABLE
SECURITY DEFINER
AS $$
    SELECT
        a.id AS assessment_id,
        a.title,
        a.course_id,
        a.due_date,
        a.weight_percent,
        CASE
            WHEN c.mode = 'review' THEN
                -- Review mode: no deadline urgency or grade impact,
                -- only mastery gap (0.6) + FSRS due (0.4).
                -- Since mastery/FSRS data may not exist yet, use weight as
                -- a proxy for importance and recency for FSRS-like ordering.
                (
                    COALESCE(a.weight_percent, 0.0) / 100.0 * 0.6
                    + CASE
                        WHEN a.due_date IS NULL THEN 0.5
                        ELSE GREATEST(0.0, 1.0 - (CURRENT_DATE - a.due_date)::FLOAT / 90.0)
                      END * 0.4
                )
            ELSE
                -- Active mode (default): original formula
                -- priority = weight_factor * 0.4 + urgency_factor * 0.6
                -- Past-due assessments get low urgency (0.05) so future ones rank higher
                (
                    COALESCE(a.weight_percent, 0.0) / 100.0 * 0.4
                    + CASE
                        WHEN a.due_date < CURRENT_DATE THEN 0.05
                        ELSE 1.0 / (1.0 + (a.due_date - CURRENT_DATE))
                      END * 0.6
                )
        END AS priority_score
    FROM assessments a
    JOIN courses c ON c.id = a.course_id
    WHERE a.course_id = p_course_id
      AND a.due_date IS NOT NULL
    ORDER BY priority_score DESC;
$$;
