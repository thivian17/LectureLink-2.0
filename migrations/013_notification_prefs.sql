-- migrations/013_notification_prefs.sql
-- Add email notification preferences to user_onboarding
-- and create assessment_deadline_notifications tracking table

-- Add notification preference columns to user_onboarding
ALTER TABLE user_onboarding
    ADD COLUMN IF NOT EXISTS email_notifications_enabled BOOLEAN NOT NULL DEFAULT TRUE,
    ADD COLUMN IF NOT EXISTS digest_last_sent_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS timezone TEXT DEFAULT 'UTC';

COMMENT ON COLUMN user_onboarding.email_notifications_enabled IS
    'User opt-out for all email notifications. Default: opted in.';

-- Track which deadline reminders have been sent to avoid duplicates
CREATE TABLE IF NOT EXISTS assessment_reminder_log (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    assessment_id   UUID NOT NULL REFERENCES assessments(id) ON DELETE CASCADE,
    reminder_type   TEXT NOT NULL CHECK (reminder_type IN ('48h', '24h')),
    sent_at         TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(user_id, assessment_id, reminder_type)
);

CREATE INDEX idx_reminder_log_user ON assessment_reminder_log (user_id, sent_at DESC);

ALTER TABLE assessment_reminder_log ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Users read own reminder log"
    ON assessment_reminder_log FOR SELECT
    USING (auth.uid() = user_id);
CREATE POLICY "Service role manages reminder log"
    ON assessment_reminder_log FOR ALL USING (true) WITH CHECK (true);
