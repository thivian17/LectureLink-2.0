-- 007: Gamification tables — XP, streaks, levels, badges, learn sessions, notifications
-- Safe to re-run: uses IF NOT EXISTS throughout.

-- ============================================================================
-- xp_events — Immutable event log for all XP awards
-- ============================================================================
CREATE TABLE IF NOT EXISTS xp_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES auth.users(id) ON DELETE CASCADE NOT NULL,
    amount INT NOT NULL,
    source TEXT NOT NULL,
    course_id UUID REFERENCES courses(id) ON DELETE SET NULL,
    session_id UUID,
    concept_id UUID REFERENCES concepts(id) ON DELETE SET NULL,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT now() NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_xp_events_user ON xp_events(user_id);
CREATE INDEX IF NOT EXISTS idx_xp_events_user_created ON xp_events(user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_xp_events_source ON xp_events(user_id, source);

-- ============================================================================
-- user_streaks — Denormalized for fast home screen rendering
-- ============================================================================
CREATE TABLE IF NOT EXISTS user_streaks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES auth.users(id) ON DELETE CASCADE NOT NULL UNIQUE,
    current_streak INT NOT NULL DEFAULT 0,
    longest_streak INT NOT NULL DEFAULT 0,
    last_session_date DATE,
    streak_freezes_available INT NOT NULL DEFAULT 1,
    streak_freezes_used INT NOT NULL DEFAULT 0,
    freeze_last_reset_at TIMESTAMPTZ DEFAULT now(),
    created_at TIMESTAMPTZ DEFAULT now() NOT NULL,
    updated_at TIMESTAMPTZ DEFAULT now() NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_streaks_user ON user_streaks(user_id);

-- ============================================================================
-- user_levels — XP totals and level tracking
-- ============================================================================
CREATE TABLE IF NOT EXISTS user_levels (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES auth.users(id) ON DELETE CASCADE NOT NULL UNIQUE,
    total_xp INT NOT NULL DEFAULT 0,
    current_level INT NOT NULL DEFAULT 1,
    xp_to_next_level INT NOT NULL DEFAULT 100,
    created_at TIMESTAMPTZ DEFAULT now() NOT NULL,
    updated_at TIMESTAMPTZ DEFAULT now() NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_levels_user ON user_levels(user_id);

-- ============================================================================
-- badges_earned — Which badges each student has earned
-- ============================================================================
CREATE TABLE IF NOT EXISTS badges_earned (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES auth.users(id) ON DELETE CASCADE NOT NULL,
    badge_id TEXT NOT NULL,
    earned_at TIMESTAMPTZ DEFAULT now() NOT NULL,
    metadata JSONB DEFAULT '{}',
    UNIQUE(user_id, badge_id)
);
CREATE INDEX IF NOT EXISTS idx_badges_user ON badges_earned(user_id);

-- ============================================================================
-- learn_sessions — Learn Mode session tracking
-- ============================================================================
CREATE TABLE IF NOT EXISTS learn_sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES auth.users(id) ON DELETE CASCADE NOT NULL,
    course_id UUID REFERENCES courses(id) ON DELETE CASCADE NOT NULL,
    status TEXT NOT NULL DEFAULT 'active',
    time_budget_minutes INT NOT NULL DEFAULT 15,
    concepts_planned JSONB DEFAULT '[]',
    concepts_completed JSONB DEFAULT '[]',
    session_data JSONB DEFAULT '{}',
    flash_review_results JSONB DEFAULT '[]',
    quiz_results JSONB DEFAULT '[]',
    xp_earned INT NOT NULL DEFAULT 0,
    combo_max INT NOT NULL DEFAULT 0,
    started_at TIMESTAMPTZ DEFAULT now() NOT NULL,
    completed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT now() NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_learn_sessions_user ON learn_sessions(user_id);
CREATE INDEX IF NOT EXISTS idx_learn_sessions_user_status ON learn_sessions(user_id, status);
CREATE INDEX IF NOT EXISTS idx_learn_sessions_user_date ON learn_sessions(user_id, created_at DESC);

-- ============================================================================
-- notification_log — Tracks notifications for analytics
-- ============================================================================
CREATE TABLE IF NOT EXISTS notification_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES auth.users(id) ON DELETE CASCADE NOT NULL,
    notification_type TEXT NOT NULL,
    title TEXT NOT NULL,
    body TEXT NOT NULL,
    metadata JSONB DEFAULT '{}',
    sent_at TIMESTAMPTZ DEFAULT now() NOT NULL,
    opened_at TIMESTAMPTZ,
    session_started_at TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS idx_notifications_user ON notification_log(user_id);
CREATE INDEX IF NOT EXISTS idx_notifications_type ON notification_log(user_id, notification_type);

-- ============================================================================
-- Row Level Security
-- ============================================================================

ALTER TABLE xp_events ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Users can read own xp_events" ON xp_events FOR SELECT USING (auth.uid() = user_id);
CREATE POLICY "Users can insert own xp_events" ON xp_events FOR INSERT WITH CHECK (auth.uid() = user_id);

ALTER TABLE user_streaks ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Users can manage own streaks" ON user_streaks FOR ALL USING (auth.uid() = user_id);

ALTER TABLE user_levels ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Users can manage own levels" ON user_levels FOR ALL USING (auth.uid() = user_id);

ALTER TABLE badges_earned ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Users can read own badges" ON badges_earned FOR SELECT USING (auth.uid() = user_id);
CREATE POLICY "Users can insert own badges" ON badges_earned FOR INSERT WITH CHECK (auth.uid() = user_id);

ALTER TABLE learn_sessions ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Users can manage own learn_sessions" ON learn_sessions FOR ALL USING (auth.uid() = user_id);

ALTER TABLE notification_log ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Users can manage own notifications" ON notification_log FOR ALL USING (auth.uid() = user_id);
