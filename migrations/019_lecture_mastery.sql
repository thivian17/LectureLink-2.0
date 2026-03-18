-- Migration 019: Lecture Mastery & Spaced Repetition support
--
-- Phase 1: RPC function for efficient per-lecture mastery aggregation
-- Phase 2: HNSW index on concepts.embedding for assessment prep similarity search
-- Phase 3: RPC function for priority study concepts

-- ============================================================================
-- Phase 1: Per-lecture mastery summary
-- ============================================================================

CREATE OR REPLACE FUNCTION get_lecture_mastery_summary(
    p_user_id UUID,
    p_course_id UUID
)
RETURNS TABLE (
    lecture_id UUID,
    title TEXT,
    lecture_number INT,
    lecture_date DATE,
    concept_count BIGINT,
    mastered BIGINT,
    developing BIGINT,
    unstarted BIGINT,
    avg_mastery DOUBLE PRECISION
)
LANGUAGE sql
STABLE
AS $$
    SELECT
        l.id AS lecture_id,
        l.title,
        l.lecture_number,
        l.lecture_date,
        COUNT(c.id) AS concept_count,
        COUNT(CASE WHEN bkt.p_mastery >= 0.85 THEN 1 END) AS mastered,
        COUNT(CASE WHEN bkt.p_mastery IS NOT NULL AND bkt.p_mastery < 0.85 THEN 1 END) AS developing,
        COUNT(CASE WHEN bkt.p_mastery IS NULL THEN 1 END) AS unstarted,
        COALESCE(AVG(COALESCE(bkt.p_mastery, 0.3)), 0.3) AS avg_mastery
    FROM lectures l
    JOIN concepts c ON c.lecture_id = l.id
    LEFT JOIN concept_bkt_state bkt
        ON bkt.concept_id = c.id AND bkt.user_id = p_user_id
    WHERE l.course_id = p_course_id
      AND l.processing_status = 'completed'
    GROUP BY l.id, l.title, l.lecture_number, l.lecture_date
    ORDER BY l.lecture_number;
$$;


-- ============================================================================
-- Phase 2: HNSW index for embedding similarity search
-- ============================================================================

-- Only create if not already present (idempotent)
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_indexes
        WHERE indexname = 'idx_concepts_embedding_hnsw'
    ) THEN
        CREATE INDEX idx_concepts_embedding_hnsw
            ON concepts USING hnsw (embedding vector_cosine_ops);
    END IF;
END
$$;


-- ============================================================================
-- Phase 3: Priority study concepts via BKT + recency
-- ============================================================================

CREATE OR REPLACE FUNCTION get_priority_study_concepts(
    p_user_id UUID,
    p_course_id UUID,
    p_limit INT DEFAULT 10
)
RETURNS TABLE (
    concept_id UUID,
    concept_title TEXT,
    p_mastery DOUBLE PRECISION,
    total_attempts INT,
    days_since_review INT,
    priority_score DOUBLE PRECISION
)
LANGUAGE sql
STABLE
AS $$
    SELECT
        c.id AS concept_id,
        c.title AS concept_title,
        COALESCE(bkt.p_mastery, 0.3) AS p_mastery,
        COALESCE(bkt.total_attempts, 0) AS total_attempts,
        COALESCE(
            EXTRACT(DAY FROM NOW() - bkt.last_updated)::INT,
            999
        ) AS days_since_review,
        -- Priority: (1 - mastery) * 0.6 + days_decay * 0.4
        (1.0 - COALESCE(bkt.p_mastery, 0.3)) * 0.6
        + LEAST(1.0, COALESCE(
            EXTRACT(DAY FROM NOW() - bkt.last_updated)::DOUBLE PRECISION / 7.0,
            1.0
        )) * 0.4
        AS priority_score
    FROM concepts c
    LEFT JOIN concept_bkt_state bkt
        ON bkt.concept_id = c.id AND bkt.user_id = p_user_id
    WHERE c.course_id = p_course_id
      -- Exclude mastered concepts unless stale (14+ days)
      AND (
          bkt.p_mastery IS NULL
          OR bkt.p_mastery < 0.85
          OR EXTRACT(DAY FROM NOW() - bkt.last_updated) >= 14
      )
    ORDER BY priority_score DESC
    LIMIT p_limit;
$$;
