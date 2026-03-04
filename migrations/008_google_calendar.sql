-- Google Calendar integration: token storage + assessment event tracking

CREATE TABLE IF NOT EXISTS user_google_tokens (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES auth.users(id) ON DELETE CASCADE UNIQUE,
    access_token TEXT NOT NULL,
    refresh_token TEXT,
    token_expires_at TIMESTAMPTZ,
    scopes TEXT[] DEFAULT '{}',
    calendar_sync_enabled BOOLEAN DEFAULT false,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

-- RLS: deny all user-level access (backend uses service key only)
ALTER TABLE user_google_tokens ENABLE ROW LEVEL SECURITY;
-- No policies = all client-side access denied; only service_role key can read/write

ALTER TABLE assessments ADD COLUMN IF NOT EXISTS google_calendar_event_id TEXT;
