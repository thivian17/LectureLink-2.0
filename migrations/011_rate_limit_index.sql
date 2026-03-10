-- migrations/011_rate_limit_index.sql
-- Add compound index for sliding window rate limit queries
-- and a cleanup function for old rate limit records

-- The sliding window query pattern is:
--   WHERE user_id = $1 AND action = $2 AND created_at > (now() - interval '24 hours')
-- This index makes that O(log n) instead of O(n)

CREATE INDEX IF NOT EXISTS idx_rate_limit_events_user_action_time
    ON rate_limit_events (user_id, action, created_at DESC);

-- Cleanup function: remove records older than 25 hours (sliding window max is 24h)
-- Called by Cloud Scheduler or can be run manually
CREATE OR REPLACE FUNCTION cleanup_old_rate_limit_events()
RETURNS INTEGER AS $$
DECLARE
    deleted_count INTEGER;
BEGIN
    DELETE FROM rate_limit_events
    WHERE created_at < NOW() - INTERVAL '25 hours';

    GET DIAGNOSTICS deleted_count = ROW_COUNT;
    RETURN deleted_count;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

COMMENT ON FUNCTION cleanup_old_rate_limit_events() IS
    'Remove rate limit records older than 25 hours. Safe to run daily via scheduler.';
