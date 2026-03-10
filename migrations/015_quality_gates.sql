-- migrations/015_quality_gates.sql
-- Content quality gate flags on lectures and syllabi

-- Flag for lectures with suspiciously few concepts extracted
ALTER TABLE lectures
    ADD COLUMN IF NOT EXISTS low_concept_yield BOOLEAN NOT NULL DEFAULT FALSE;

COMMENT ON COLUMN lectures.low_concept_yield IS
    'Set to TRUE when concepts_stored < 3 after processing. Signals potential audio
     quality issue, short recording, or abstract content. Surfaced as a UI warning.';

-- Index for querying flagged lectures in admin view
CREATE INDEX IF NOT EXISTS idx_lectures_low_yield
    ON lectures (user_id, low_concept_yield)
    WHERE low_concept_yield = TRUE;

-- Add confidence display field to syllabi for frontend
-- (extraction_confidence already exists, but add a helper boolean)
ALTER TABLE syllabi
    ADD COLUMN IF NOT EXISTS low_confidence BOOLEAN
    GENERATED ALWAYS AS (
        CASE WHEN extraction_confidence IS NOT NULL AND extraction_confidence < 0.5
        THEN TRUE ELSE FALSE END
    ) STORED;

COMMENT ON COLUMN syllabi.low_confidence IS
    'Computed: TRUE when extraction_confidence < 0.5. Used by frontend to show warning banner.';
