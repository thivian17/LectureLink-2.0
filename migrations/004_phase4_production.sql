-- ============================================================
-- Phase 4: Production Infrastructure
-- ADK session persistence table
-- ============================================================

CREATE TABLE IF NOT EXISTS adk_sessions (
    id          UUID PRIMARY KEY,
    user_id     UUID NOT NULL,
    agent_name  TEXT NOT NULL,
    state       JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    expires_at  TIMESTAMPTZ NOT NULL DEFAULT (now() + interval '24 hours')
);

-- Index for list queries (user + agent, non-expired, ordered by recency)
CREATE INDEX IF NOT EXISTS idx_adk_sessions_user_agent
    ON adk_sessions (user_id, agent_name, updated_at DESC)
    WHERE expires_at > now();

-- Index for cleanup job
CREATE INDEX IF NOT EXISTS idx_adk_sessions_expires
    ON adk_sessions (expires_at)
    WHERE expires_at < now();

-- RLS: users can only access their own sessions
ALTER TABLE adk_sessions ENABLE ROW LEVEL SECURITY;

CREATE POLICY adk_sessions_user_policy ON adk_sessions
    FOR ALL
    USING (auth.uid() = user_id)
    WITH CHECK (auth.uid() = user_id);

-- Service role bypass for internal cleanup jobs
CREATE POLICY adk_sessions_service_policy ON adk_sessions
    FOR ALL
    USING (auth.role() = 'service_role');
