import { createClient } from "@/lib/supabase/client";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

async function getAuthHeaders(): Promise<HeadersInit> {
  const supabase = createClient();
  const { data } = await supabase.auth.getSession();
  const token = data.session?.access_token;
  return token
    ? { "Content-Type": "application/json", Authorization: `Bearer ${token}` }
    : { "Content-Type": "application/json" };
}

export async function submitBugReport(payload: {
  title: string;
  description: string;
  severity: "critical" | "high" | "medium" | "low";
  browserInfo?: Record<string, unknown>;
  consoleErrors?: string[];
}): Promise<{ id: string }> {
  const headers = await getAuthHeaders();
  const res = await fetch(`${API_URL}/api/analytics/bug-report`, {
    method: "POST",
    headers,
    body: JSON.stringify({
      title: payload.title,
      description: payload.description,
      severity: payload.severity,
      page_path:
        typeof window !== "undefined" ? window.location.pathname : undefined,
      browser_info: payload.browserInfo ?? {},
      console_errors: payload.consoleErrors ?? [],
    }),
  });
  if (!res.ok) throw new Error("Failed to submit bug report");
  return res.json();
}

export async function submitNPS(payload: {
  rating: number;
  message?: string;
  featureTag?: "tutor" | "quiz" | "coach" | "learn" | "general";
}): Promise<{ id: string }> {
  const headers = await getAuthHeaders();
  const res = await fetch(`${API_URL}/api/analytics/feedback`, {
    method: "POST",
    headers,
    body: JSON.stringify({
      feedback_type: "nps",
      rating: payload.rating,
      message: payload.message,
      feature_tag: payload.featureTag ?? "general",
    }),
  });
  if (!res.ok) throw new Error("Failed to submit feedback");
  return res.json();
}

export function collectBrowserInfo(): Record<string, unknown> {
  if (typeof window === "undefined") return {};
  return {
    user_agent: navigator.userAgent,
    screen_width: window.screen.width,
    screen_height: window.screen.height,
    viewport_width: window.innerWidth,
    viewport_height: window.innerHeight,
    timezone: Intl.DateTimeFormat().resolvedOptions().timeZone,
    language: navigator.language,
    platform: navigator.platform,
  };
}
