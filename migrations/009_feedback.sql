-- Feedback submissions table
CREATE TABLE IF NOT EXISTS feedback (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID REFERENCES auth.users(id) ON DELETE SET NULL,
  type TEXT NOT NULL CHECK (type IN ('bug', 'feature', 'ux', 'praise')),
  description TEXT NOT NULL,
  page_url TEXT NOT NULL,
  page_title TEXT,
  screenshot_url TEXT,
  annotation_bounds JSONB,
  browser_info JSONB,
  console_errors JSONB,
  github_issue_url TEXT,
  status TEXT NOT NULL DEFAULT 'open' CHECK (status IN ('open', 'triaging', 'resolved')),
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX feedback_status_created ON feedback(status, created_at DESC);
CREATE INDEX feedback_user_id ON feedback(user_id);

ALTER TABLE feedback ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can insert feedback"
  ON feedback FOR INSERT
  TO authenticated
  WITH CHECK (auth.uid() = user_id OR user_id IS NULL);

CREATE POLICY "Users can view own feedback"
  ON feedback FOR SELECT
  TO authenticated
  USING (auth.uid() = user_id);

-- Storage bucket for screenshots
INSERT INTO storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
VALUES (
  'feedback-screenshots',
  'feedback-screenshots',
  false,
  5242880,
  ARRAY['image/png', 'image/jpeg', 'image/webp']
) ON CONFLICT (id) DO NOTHING;

CREATE POLICY "Authenticated users can upload screenshots"
  ON storage.objects FOR INSERT
  TO authenticated
  WITH CHECK (bucket_id = 'feedback-screenshots');

CREATE POLICY "Service role can read screenshots"
  ON storage.objects FOR SELECT
  TO service_role
  USING (bucket_id = 'feedback-screenshots');
