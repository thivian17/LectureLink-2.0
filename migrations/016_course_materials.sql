-- ============================================================
-- Migration 016: Course Materials Support
-- Adds course_materials + material_chunks tables, extends
-- hybrid_search RPC to search across both lecture and material
-- chunks using Reciprocal Rank Fusion.
-- ============================================================

-- -------------------------------------------------------
-- Table 1: course_materials
-- -------------------------------------------------------
CREATE TABLE IF NOT EXISTS course_materials (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    course_id UUID REFERENCES courses(id) ON DELETE CASCADE,
    user_id UUID REFERENCES auth.users(id) ON DELETE CASCADE,

    -- Metadata
    title TEXT NOT NULL,
    material_type TEXT NOT NULL CHECK (material_type IN (
        'reading', 'homework', 'practice_exam', 'assignment_outline',
        'lab_manual', 'study_guide', 'problem_set', 'other'
    )),
    file_url TEXT NOT NULL,
    file_name TEXT,
    file_size_bytes BIGINT,
    page_count INT,

    -- Optional associations
    linked_assessment_id UUID REFERENCES assessments(id) ON DELETE SET NULL,
    linked_lecture_id UUID REFERENCES lectures(id) ON DELETE SET NULL,
    week_number INT,
    relevant_date DATE,

    -- Processing state (mirrors lecture pattern)
    processing_status TEXT DEFAULT 'pending'
        CHECK (processing_status IN ('pending', 'processing', 'completed', 'failed')),
    processing_stage TEXT,
    processing_progress FLOAT DEFAULT 0.0,
    processing_error TEXT,
    retry_count INT DEFAULT 0,

    -- Extraction results
    extracted_text_preview TEXT,
    concept_count INT DEFAULT 0,
    chunk_count INT DEFAULT 0,

    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_materials_course ON course_materials(course_id, user_id);
CREATE INDEX idx_materials_type ON course_materials(course_id, material_type);
CREATE INDEX idx_materials_status ON course_materials(processing_status);

ALTER TABLE course_materials ENABLE ROW LEVEL SECURITY;
CREATE POLICY materials_user_policy ON course_materials
    USING (user_id = auth.uid());

-- -------------------------------------------------------
-- Table 2: material_chunks
-- -------------------------------------------------------
CREATE TABLE IF NOT EXISTS material_chunks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    material_id UUID REFERENCES course_materials(id) ON DELETE CASCADE,
    course_id UUID REFERENCES courses(id) ON DELETE CASCADE,
    user_id UUID REFERENCES auth.users(id),

    chunk_index INT NOT NULL,
    content TEXT NOT NULL,
    page_number INT,
    section_title TEXT,

    embedding vector(2000),
    metadata JSONB DEFAULT '{}',
    fts tsvector,

    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_material_chunks_material ON material_chunks(material_id);
CREATE INDEX idx_material_chunks_course ON material_chunks(course_id);
CREATE INDEX idx_material_chunks_user ON material_chunks(user_id);
CREATE INDEX idx_material_chunks_embedding
    ON material_chunks USING hnsw (embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 64);
CREATE INDEX idx_material_chunks_fts ON material_chunks USING GIN(fts);

ALTER TABLE material_chunks ENABLE ROW LEVEL SECURITY;
CREATE POLICY material_chunks_user_policy ON material_chunks
    USING (user_id = auth.uid());

-- -------------------------------------------------------
-- Extend concepts table to optionally link to materials
-- -------------------------------------------------------
ALTER TABLE concepts
    ADD COLUMN IF NOT EXISTS material_id UUID REFERENCES course_materials(id) ON DELETE CASCADE;
CREATE INDEX IF NOT EXISTS idx_concepts_material ON concepts(material_id);

-- -------------------------------------------------------
-- Increment RPC for material retry
-- -------------------------------------------------------
CREATE OR REPLACE FUNCTION increment_material_retry_count(p_material_id UUID)
RETURNS void AS $$
BEGIN
    UPDATE course_materials
    SET retry_count = retry_count + 1,
        updated_at = now()
    WHERE id = p_material_id;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- ============================================================
-- Extended hybrid_search: searches lecture_chunks AND
-- material_chunks, returns source_type + material_id columns.
-- Fully backward-compatible — existing callers get the same
-- results they always did (source_type='lecture', material_id=NULL)
-- when material_chunks is empty.
-- ============================================================
CREATE OR REPLACE FUNCTION hybrid_search(
    p_query_embedding vector(2000),
    p_query_text TEXT,
    p_course_id UUID,
    p_lecture_ids UUID[] DEFAULT NULL,
    p_limit INT DEFAULT 10,
    p_rrf_k INT DEFAULT 60,
    p_material_ids UUID[] DEFAULT NULL
)
RETURNS TABLE (
    chunk_id UUID,
    lecture_id UUID,
    content TEXT,
    start_time FLOAT,
    end_time FLOAT,
    slide_number INT,
    combined_score FLOAT,
    source_type TEXT,
    material_id UUID
) AS $$
WITH
-- ── Vector search: lecture_chunks ──
lc_vector AS (
    SELECT
        lc.id,
        lc.lecture_id,
        lc.content,
        lc.start_time,
        lc.end_time,
        lc.slide_number,
        'lecture'::TEXT AS source_type,
        NULL::UUID AS material_id,
        ROW_NUMBER() OVER (ORDER BY lc.embedding <=> p_query_embedding) AS rank
    FROM lecture_chunks lc
    JOIN lectures l ON l.id = lc.lecture_id
    WHERE l.course_id = p_course_id
      AND l.processing_status = 'completed'
      AND (p_lecture_ids IS NULL OR lc.lecture_id = ANY(p_lecture_ids))
    ORDER BY lc.embedding <=> p_query_embedding
    LIMIT p_limit * 3
),
-- ── Vector search: material_chunks ──
mc_vector AS (
    SELECT
        mc.id,
        NULL::UUID AS lecture_id,
        mc.content,
        NULL::FLOAT AS start_time,
        NULL::FLOAT AS end_time,
        mc.page_number AS slide_number,
        'material'::TEXT AS source_type,
        mc.material_id,
        ROW_NUMBER() OVER (ORDER BY mc.embedding <=> p_query_embedding) AS rank
    FROM material_chunks mc
    JOIN course_materials cm ON cm.id = mc.material_id
    WHERE cm.course_id = p_course_id
      AND cm.processing_status = 'completed'
      AND (p_material_ids IS NULL OR mc.material_id = ANY(p_material_ids))
    ORDER BY mc.embedding <=> p_query_embedding
    LIMIT p_limit * 3
),
-- ── Combined vector results with unified ranking ──
vector_results AS (
    SELECT id, lecture_id, content, start_time, end_time, slide_number,
           source_type, material_id,
           ROW_NUMBER() OVER (ORDER BY rank, source_type) AS rank
    FROM (
        SELECT *, rank AS orig_rank FROM lc_vector
        UNION ALL
        SELECT *, rank AS orig_rank FROM mc_vector
    ) combined
    ORDER BY orig_rank
    LIMIT p_limit * 3
),
-- ── FTS search: lecture_chunks ──
lc_fts AS (
    SELECT
        lc.id,
        lc.lecture_id,
        lc.content,
        lc.start_time,
        lc.end_time,
        lc.slide_number,
        'lecture'::TEXT AS source_type,
        NULL::UUID AS material_id,
        ts_rank(lc.fts, websearch_to_tsquery('english', p_query_text)) AS fts_rank
    FROM lecture_chunks lc
    JOIN lectures l ON l.id = lc.lecture_id
    WHERE l.course_id = p_course_id
      AND l.processing_status = 'completed'
      AND (p_lecture_ids IS NULL OR lc.lecture_id = ANY(p_lecture_ids))
      AND lc.fts @@ websearch_to_tsquery('english', p_query_text)
),
mc_fts AS (
    SELECT
        mc.id,
        NULL::UUID AS lecture_id,
        mc.content,
        NULL::FLOAT AS start_time,
        NULL::FLOAT AS end_time,
        mc.page_number AS slide_number,
        'material'::TEXT AS source_type,
        mc.material_id,
        ts_rank(mc.fts, websearch_to_tsquery('english', p_query_text)) AS fts_rank
    FROM material_chunks mc
    JOIN course_materials cm ON cm.id = mc.material_id
    WHERE cm.course_id = p_course_id
      AND cm.processing_status = 'completed'
      AND (p_material_ids IS NULL OR mc.material_id = ANY(p_material_ids))
      AND mc.fts @@ websearch_to_tsquery('english', p_query_text)
),
-- ── Combined FTS with unified ranking ──
fts_results AS (
    SELECT id, lecture_id, content, start_time, end_time, slide_number,
           source_type, material_id,
           ROW_NUMBER() OVER (ORDER BY fts_rank DESC) AS rank
    FROM (
        SELECT * FROM lc_fts
        UNION ALL
        SELECT * FROM mc_fts
    ) combined
    ORDER BY fts_rank DESC
    LIMIT p_limit * 3
)
-- ── RRF fusion across vector + FTS ──
SELECT
    COALESCE(v.id, f.id) AS chunk_id,
    COALESCE(v.lecture_id, f.lecture_id) AS lecture_id,
    COALESCE(v.content, f.content) AS content,
    COALESCE(v.start_time, f.start_time) AS start_time,
    COALESCE(v.end_time, f.end_time) AS end_time,
    COALESCE(v.slide_number, f.slide_number) AS slide_number,
    (COALESCE(1.0 / (p_rrf_k + v.rank), 0.0) +
     COALESCE(1.0 / (p_rrf_k + f.rank), 0.0)) AS combined_score,
    COALESCE(v.source_type, f.source_type) AS source_type,
    COALESCE(v.material_id, f.material_id) AS material_id
FROM vector_results v
FULL OUTER JOIN fts_results f ON v.id = f.id
ORDER BY combined_score DESC
LIMIT p_limit;
$$ LANGUAGE sql STABLE;
