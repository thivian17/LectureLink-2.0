-- Enable pgvector (for future use in Phase 2)
CREATE EXTENSION IF NOT EXISTS vector;

-- Courses table (stores semester context for date resolution)
CREATE TABLE courses (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES auth.users(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    code TEXT,
    semester_start DATE NOT NULL,
    semester_end DATE NOT NULL,
    meeting_days TEXT[] DEFAULT '{}',
    meeting_time TEXT,
    holidays JSONB DEFAULT '[]',
    target_grade FLOAT DEFAULT 0.80,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

ALTER TABLE courses ENABLE ROW LEVEL SECURITY;
CREATE POLICY courses_user_policy ON courses
    USING (user_id = auth.uid());

-- Syllabi table (one per course)
CREATE TABLE syllabi (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    course_id UUID REFERENCES courses(id) ON DELETE CASCADE,
    user_id UUID REFERENCES auth.users(id),
    file_url TEXT,
    file_name TEXT,
    raw_extraction JSONB,
    grade_breakdown JSONB NOT NULL DEFAULT '[]',
    extraction_confidence FLOAT,
    needs_review BOOLEAN DEFAULT true,
    status TEXT DEFAULT 'pending',
    reviewed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT now()
);

ALTER TABLE syllabi ENABLE ROW LEVEL SECURITY;
CREATE POLICY syllabi_user_policy ON syllabi
    USING (user_id = auth.uid());

-- Assessments table (heart of the scheduling oracle)
CREATE TABLE assessments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    course_id UUID REFERENCES courses(id) ON DELETE CASCADE,
    syllabus_id UUID REFERENCES syllabi(id),
    title TEXT NOT NULL,
    type TEXT NOT NULL,
    due_date DATE,
    due_date_raw TEXT,
    is_date_ambiguous BOOLEAN DEFAULT false,
    weight_percent FLOAT,
    topics TEXT[],
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_assessments_course_due ON assessments(course_id, due_date);
CREATE INDEX idx_assessments_type ON assessments(course_id, type);

ALTER TABLE assessments ENABLE ROW LEVEL SECURITY;
CREATE POLICY assessments_user_policy ON assessments
    USING (course_id IN (
        SELECT id FROM courses WHERE user_id = auth.uid()
    ));

-- Concepts table (populated in Phase 2, but created now)
CREATE TABLE concepts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    course_id UUID REFERENCES courses(id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    description TEXT,
    created_at TIMESTAMPTZ DEFAULT now()
);

-- Concept-Assessment links (populated by Concept Mapper in Phase 2)
CREATE TABLE concept_assessment_links (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    concept_id UUID REFERENCES concepts(id) ON DELETE CASCADE,
    assessment_id UUID REFERENCES assessments(id) ON DELETE CASCADE,
    relevance_score FLOAT DEFAULT 1.0,
    UNIQUE(concept_id, assessment_id)
);

-- Priority scoring function (Phase 1: deadline urgency + grade impact only)
-- Formula: priority_score = (weight_factor * 0.4) + (urgency_factor * 0.6)
--   weight_factor = weight_percent / 100.0
--   urgency_factor = 1.0 / (1.0 + days_until_due) for future, 0.9 for past
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
        (
            COALESCE(a.weight_percent, 0.0) / 100.0 * 0.4
            + CASE
                WHEN a.due_date < CURRENT_DATE THEN 0.9
                ELSE 1.0 / (1.0 + (a.due_date - CURRENT_DATE))
              END * 0.6
        ) AS priority_score
    FROM assessments a
    WHERE a.course_id = p_course_id
      AND a.due_date IS NOT NULL
    ORDER BY priority_score DESC;
$$;
