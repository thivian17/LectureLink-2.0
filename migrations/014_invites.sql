-- migrations/014_invites.sql
-- Invite and referral system for beta sharing

-- Invite links
CREATE TABLE IF NOT EXISTS user_invites (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    inviter_user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    invite_code     TEXT NOT NULL UNIQUE,  -- short random string e.g. "abc12"
    email           TEXT,                  -- optional: specific invitee email
    max_uses        INTEGER NOT NULL DEFAULT 10,
    use_count       INTEGER NOT NULL DEFAULT 0,
    accepted_at     TIMESTAMPTZ,
    expires_at      TIMESTAMPTZ NOT NULL DEFAULT (NOW() + INTERVAL '30 days'),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_user_invites_code ON user_invites (invite_code);
CREATE INDEX idx_user_invites_inviter ON user_invites (inviter_user_id);

ALTER TABLE user_invites ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Inviters see own invites"
    ON user_invites FOR SELECT USING (auth.uid() = inviter_user_id);
CREATE POLICY "Anyone can validate invite codes (public read for code lookup)"
    ON user_invites FOR SELECT USING (true);
CREATE POLICY "Service role manages invites"
    ON user_invites FOR ALL USING (true) WITH CHECK (true);

-- Track who referred whom
ALTER TABLE user_onboarding
    ADD COLUMN IF NOT EXISTS invited_by_user_id UUID REFERENCES auth.users(id),
    ADD COLUMN IF NOT EXISTS invite_code_used TEXT;

-- Course share tokens (read-only preview for non-registered users)
CREATE TABLE IF NOT EXISTS course_share_tokens (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    course_id   UUID NOT NULL REFERENCES courses(id) ON DELETE CASCADE,
    user_id     UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    token       TEXT NOT NULL UNIQUE,
    expires_at  TIMESTAMPTZ NOT NULL DEFAULT (NOW() + INTERVAL '7 days'),
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(course_id, user_id)  -- one active share per course per user
);

CREATE INDEX idx_course_share_tokens_token ON course_share_tokens (token);

ALTER TABLE course_share_tokens ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Course owners manage share tokens"
    ON course_share_tokens FOR ALL USING (auth.uid() = user_id);
CREATE POLICY "Public token validation"
    ON course_share_tokens FOR SELECT USING (true);
