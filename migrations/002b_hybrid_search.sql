CREATE OR REPLACE FUNCTION hybrid_search(
    p_query_embedding vector(2000),
    p_query_text TEXT,
    p_course_id UUID,
    p_lecture_ids UUID[] DEFAULT NULL,
    p_limit INT DEFAULT 10,
    p_rrf_k INT DEFAULT 60
)
RETURNS TABLE (
    chunk_id UUID,
    lecture_id UUID,
    content TEXT,
    start_time FLOAT,
    end_time FLOAT,
    slide_number INT,
    combined_score FLOAT
) AS $$
WITH vector_results AS (
    SELECT
        lc.id,
        lc.lecture_id,
        lc.content,
        lc.start_time,
        lc.end_time,
        lc.slide_number,
        ROW_NUMBER() OVER (ORDER BY lc.embedding <=> p_query_embedding) AS rank
    FROM lecture_chunks lc
    JOIN lectures l ON l.id = lc.lecture_id
    WHERE l.course_id = p_course_id
      AND l.processing_status = 'completed'
      AND (p_lecture_ids IS NULL OR lc.lecture_id = ANY(p_lecture_ids))
    ORDER BY lc.embedding <=> p_query_embedding
    LIMIT p_limit * 3
),
fts_results AS (
    SELECT
        lc.id,
        lc.lecture_id,
        lc.content,
        lc.start_time,
        lc.end_time,
        lc.slide_number,
        ROW_NUMBER() OVER (
            ORDER BY ts_rank(lc.fts, websearch_to_tsquery('english', p_query_text)) DESC
        ) AS rank
    FROM lecture_chunks lc
    JOIN lectures l ON l.id = lc.lecture_id
    WHERE l.course_id = p_course_id
      AND l.processing_status = 'completed'
      AND (p_lecture_ids IS NULL OR lc.lecture_id = ANY(p_lecture_ids))
      AND lc.fts @@ websearch_to_tsquery('english', p_query_text)
    ORDER BY ts_rank(lc.fts, websearch_to_tsquery('english', p_query_text)) DESC
    LIMIT p_limit * 3
)
SELECT
    COALESCE(v.id, f.id) AS chunk_id,
    COALESCE(v.lecture_id, f.lecture_id) AS lecture_id,
    COALESCE(v.content, f.content) AS content,
    COALESCE(v.start_time, f.start_time) AS start_time,
    COALESCE(v.end_time, f.end_time) AS end_time,
    COALESCE(v.slide_number, f.slide_number) AS slide_number,
    -- RRF fusion: gracefully handles when only one source has results
    (COALESCE(1.0 / (p_rrf_k + v.rank), 0.0) +
     COALESCE(1.0 / (p_rrf_k + f.rank), 0.0)) AS combined_score
FROM vector_results v
FULL OUTER JOIN fts_results f ON v.id = f.id
ORDER BY combined_score DESC
LIMIT p_limit;
$$ LANGUAGE sql STABLE;