import { createClient } from "@/lib/supabase/client";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

async function adminFetch(path: string, options?: RequestInit) {
  const supabase = createClient();
  const { data } = await supabase.auth.getSession();
  const token = data.session?.access_token;
  if (!token) throw new Error("Not authenticated");
  const res = await fetch(`${API_URL}${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
      ...options?.headers,
    },
  });
  if (res.status === 403) throw new Error("Not authorized — admin access required");
  if (!res.ok) throw new Error(`Admin API error: ${res.status}`);
  return res.json();
}

export interface AdminOverview {
  dau: number; wau: number; mau: number;
  total_users: number;
  learn_sessions_week: number;
  quiz_attempts_week: number;
  bugs_open: number;
  feedback_unread: number;
}

export interface AdminUser {
  id: string; email: string; display_name?: string;
  created_at: string; last_active: string | null;
  session_count: number;
  level: { current_level: number; total_xp: number };
}

export interface BugReport {
  id: string; user_id: string; title: string; description: string;
  severity: "critical" | "high" | "medium" | "low";
  status: "open" | "in_progress" | "resolved" | "wont_fix";
  page_path?: string; browser_info?: Record<string, unknown>;
  admin_notes?: string; created_at: string; resolved_at?: string;
}

export interface UserFeedback {
  id: string; user_id: string;
  feedback_type: "nps" | "feature" | "general" | "churn";
  rating?: number; message?: string; feature_tag?: string;
  status: "unread" | "read" | "actioned";
  created_at: string;
}

export const adminApi = {
  getOverview: (): Promise<AdminOverview> =>
    adminFetch("/api/admin/overview"),

  getFeatureUsage: (days = 7): Promise<{ days: number; event_counts: Record<string, number> }> =>
    adminFetch(`/api/admin/feature-usage?days=${days}`),

  listUsers: (limit = 50, offset = 0): Promise<{ users: AdminUser[]; total: number }> =>
    adminFetch(`/api/admin/users?limit=${limit}&offset=${offset}`),

  listBugs: (params?: { status?: string; severity?: string; limit?: number }):
    Promise<{ bugs: BugReport[] }> => {
    const q = new URLSearchParams();
    if (params?.status) q.set("status", params.status);
    if (params?.severity) q.set("severity", params.severity);
    if (params?.limit) q.set("limit", String(params.limit));
    return adminFetch(`/api/admin/bugs?${q}`);
  },

  updateBug: (bugId: string, status?: string, adminNotes?: string): Promise<BugReport> => {
    const q = new URLSearchParams();
    if (status) q.set("status_update", status);
    if (adminNotes !== undefined) q.set("admin_notes", adminNotes);
    return adminFetch(`/api/admin/bugs/${bugId}?${q}`, { method: "PATCH" });
  },

  listFeedback: (params?: { feedback_type?: string; feature_tag?: string; status?: string }):
    Promise<{ feedback: UserFeedback[] }> => {
    const q = new URLSearchParams();
    if (params?.feedback_type) q.set("feedback_type", params.feedback_type);
    if (params?.feature_tag) q.set("feature_tag", params.feature_tag);
    if (params?.status) q.set("status", params.status);
    return adminFetch(`/api/admin/feedback?${q}`);
  },

  updateFeedbackStatus: (feedbackId: string, status: "unread" | "read" | "actioned"):
    Promise<UserFeedback> =>
    adminFetch(`/api/admin/feedback/${feedbackId}/status?new_status=${status}`, { method: "PATCH" }),
};
