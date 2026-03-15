-- ============================================================
-- Migration 013: Concept Registry Support
-- Adds cross-lecture concept deduplication infrastructure
-- ============================================================

-- Junction table: concepts can span multiple lectures
CREATE TABLE IF NOT EXISTS concept_lectures (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    concept_id UUID NOT NULL REFERENCES concepts(id) ON DELETE CASCADE,
    lecture_id UUID NOT NULL REFERENCES lectures(id) ON DELETE CASCADE,
    source_chunk_ids UUID[] DEFAULT '{}',
    confidence FLOAT DEFAULT 1.0,
    created_at TIMESTAMPTZ DEFAULT now(),
    UNIQUE(concept_id, lecture_id)
);

CREATE INDEX idx_concept_lectures_concept ON concept_lectures(concept_id);
CREATE INDEX idx_concept_lectures_lecture ON concept_lectures(lecture_id);

ALTER TABLE concept_lectures ENABLE ROW LEVEL SECURITY;
CREATE POLICY concept_lectures_user_policy ON concept_lectures
    USING (concept_id IN (
        SELECT id FROM concepts WHERE user_id = auth.uid()
    ));

-- Service role can manage all concept_lectures
CREATE POLICY concept_lectures_service_policy ON concept_lectures
    FOR ALL USING (true) WITH CHECK (true);

-- Make lecture_id nullable (concepts can now span multiple lectures)
ALTER TABLE concepts ALTER COLUMN lecture_id DROP NOT NULL;

-- Track raw titles that merged into this concept
ALTER TABLE concepts ADD COLUMN IF NOT EXISTS merged_titles TEXT[] DEFAULT '{}';

-- Parent-child relationship (optional, for future grouping)
ALTER TABLE concepts ADD COLUMN IF NOT EXISTS parent_id UUID
    REFERENCES concepts(id) ON DELETE SET NULL;

-- Fast registry lookups by course + title
CREATE INDEX IF NOT EXISTS idx_concepts_course_title
    ON concepts(course_id, title);
CREATE INDEX IF NOT EXISTS idx_concepts_parent
    ON concepts(parent_id) WHERE parent_id IS NOT NULL;

-- Populate junction table from existing single-lecture concepts
INSERT INTO concept_lectures (concept_id, lecture_id, source_chunk_ids)
SELECT id, lecture_id, COALESCE(source_chunk_ids, '{}')
FROM concepts
WHERE lecture_id IS NOT NULL
ON CONFLICT (concept_id, lecture_id) DO NOTHING;

-- Returns concepts linked ONLY to the given lecture (safe to delete on reprocess)
CREATE OR REPLACE FUNCTION get_orphan_concepts_for_lecture(p_lecture_id UUID)
RETURNS TABLE (id UUID) AS $$
BEGIN
    RETURN QUERY
    SELECT c.id
    FROM concepts c
    WHERE c.id IN (
        SELECT cl.concept_id FROM concept_lectures cl
        WHERE cl.lecture_id = p_lecture_id
    )
    AND NOT EXISTS (
        SELECT 1 FROM concept_lectures cl2
        WHERE cl2.concept_id = c.id
        AND cl2.lecture_id != p_lecture_id
    );
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;
