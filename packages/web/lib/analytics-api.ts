// packages/web/lib/analytics-api.ts
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

export interface AnalyticsEventPayload {
  event_type: string;
  event_category: "engagement" | "feature" | "navigation" | "performance" | "error";
  properties?: Record<string, unknown>;
  page_path?: string;
  device_type?: string;
}

export async function postAnalyticsEvents(
  events: AnalyticsEventPayload[],
  sessionId: string
): Promise<void> {
  const headers = await getAuthHeaders();
  await fetch(`${API_URL}/api/analytics/events`, {
    method: "POST",
    headers,
    body: JSON.stringify({ events, session_id: sessionId }),
    keepalive: true,
  });
  // Never throws — analytics must not crash the app
}
