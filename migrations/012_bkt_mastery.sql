-- migrations/012_bkt_mastery.sql
-- BKT mastery state table for Bayesian Knowledge Tracing

CREATE TABLE IF NOT EXISTS concept_bkt_state (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    concept_id      UUID NOT NULL REFERENCES concepts(id) ON DELETE CASCADE,
    p_mastery       FLOAT NOT NULL DEFAULT 0.3,   -- Initial prior: 30% known
    p_transit       FLOAT NOT NULL DEFAULT 0.1,   -- Learning rate
    p_guess         FLOAT NOT NULL DEFAULT 0.25,  -- Guess probability
    p_slip          FLOAT NOT NULL DEFAULT 0.1,   -- Slip probability
    total_attempts  INTEGER NOT NULL DEFAULT 0,
    correct_attempts INTEGER NOT NULL DEFAULT 0,
    last_updated    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(user_id, concept_id)
);

-- Index for bulk fetch by user+course (performance page loads)
CREATE INDEX idx_concept_bkt_state_user ON concept_bkt_state (user_id);

-- Fast lookup for a specific concept's states
CREATE INDEX idx_concept_bkt_state_concept ON concept_bkt_state (concept_id);

-- RLS: users can only see their own mastery state
ALTER TABLE concept_bkt_state ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can read own BKT state"
    ON concept_bkt_state FOR SELECT
    USING (auth.uid() = user_id);

CREATE POLICY "Service role can manage all BKT state"
    ON concept_bkt_state FOR ALL
    USING (true)
    WITH CHECK (true);

-- Helper: get mastery summary per concept for a user+course
-- Returns concept_id, title, p_mastery, total_attempts, mastery_label
CREATE OR REPLACE FUNCTION get_bkt_mastery_summary(
    p_user_id UUID,
    p_course_id UUID
)
RETURNS TABLE (
    concept_id      UUID,
    concept_title   TEXT,
    p_mastery       FLOAT,
    total_attempts  INTEGER,
    mastery_label   TEXT  -- 'learning' | 'developing' | 'proficient' | 'mastered'
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        c.id AS concept_id,
        c.title AS concept_title,
        COALESCE(bkt.p_mastery, 0.3) AS p_mastery,
        COALESCE(bkt.total_attempts, 0) AS total_attempts,
        CASE
            WHEN COALESCE(bkt.p_mastery, 0.3) >= 0.85 THEN 'mastered'
            WHEN COALESCE(bkt.p_mastery, 0.3) >= 0.65 THEN 'proficient'
            WHEN COALESCE(bkt.p_mastery, 0.3) >= 0.40 THEN 'developing'
            ELSE 'learning'
        END AS mastery_label
    FROM concepts c
    LEFT JOIN concept_bkt_state bkt
        ON bkt.concept_id = c.id AND bkt.user_id = p_user_id
    WHERE c.course_id = p_course_id
    ORDER BY c.title;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;
