// packages/web/lib/analytics.ts
import { postAnalyticsEvents, type AnalyticsEventPayload } from "./analytics-api";

const BATCH_SIZE = 10;
const FLUSH_INTERVAL_MS = 5000;

function getDeviceType(): "desktop" | "mobile" | "tablet" {
  if (typeof window === "undefined") return "desktop";
  const w = window.innerWidth;
  if (w < 768) return "mobile";
  if (w < 1024) return "tablet";
  return "desktop";
}

class AnalyticsClient {
  private queue: AnalyticsEventPayload[] = [];
  private sessionId: string;
  private timer: ReturnType<typeof setTimeout> | null = null;

  constructor() {
    this.sessionId = this.getOrCreateSessionId();
    if (typeof window !== "undefined") {
      window.addEventListener("beforeunload", () => this.flush());
      window.addEventListener("visibilitychange", () => {
        if (document.visibilityState === "hidden") this.flush();
      });
    }
  }

  track(
    eventType: string,
    category: AnalyticsEventPayload["event_category"],
    properties: Record<string, unknown> = {},
    pagePath?: string
  ) {
    this.queue.push({
      event_type: eventType,
      event_category: category,
      properties,
      page_path: pagePath ?? (typeof window !== "undefined" ? window.location.pathname : undefined),
      device_type: getDeviceType(),
    });
    if (this.queue.length >= BATCH_SIZE) {
      void this.flush();
    } else {
      this.scheduleFlush();
    }
  }

  private scheduleFlush() {
    if (this.timer) return;
    this.timer = setTimeout(() => void this.flush(), FLUSH_INTERVAL_MS);
  }

  async flush() {
    if (this.timer) { clearTimeout(this.timer); this.timer = null; }
    if (!this.queue.length) return;
    const batch = this.queue.splice(0);
    try {
      await postAnalyticsEvents(batch, this.sessionId);
    } catch {
      // Silently discard — analytics must never crash the app
    }
  }

  private getOrCreateSessionId(): string {
    if (typeof window === "undefined") return "ssr";
    try {
      let id = sessionStorage.getItem("ll_analytics_session");
      if (!id) {
        id = crypto.randomUUID();
        sessionStorage.setItem("ll_analytics_session", id);
      }
      return id;
    } catch {
      return "unknown";
    }
  }
}

export const analytics = new AnalyticsClient();

// Typed event helpers — import and call these throughout the app
export const trackEvent = {
  pageView: (path: string) =>
    analytics.track("page_view", "navigation", { path }, path),
  quizStarted: (courseId: string, quizId: string) =>
    analytics.track("quiz_started", "engagement", { course_id: courseId, quiz_id: quizId }),
  quizCompleted: (courseId: string, score: number, totalQuestions: number) =>
    analytics.track("quiz_completed", "engagement", { course_id: courseId, score, total_questions: totalQuestions }),
  tutorSessionStarted: (courseId: string, mode: string) =>
    analytics.track("tutor_session_started", "engagement", { course_id: courseId, mode }),
  tutorSessionEnded: (courseId: string, durationSeconds: number) =>
    analytics.track("tutor_session_ended", "engagement", { course_id: courseId, duration_seconds: durationSeconds }),
  learnSessionStarted: (courseId: string, timeBudgetMinutes: number) =>
    analytics.track("learn_session_started", "engagement", { course_id: courseId, time_budget_minutes: timeBudgetMinutes }),
  learnSessionCompleted: (courseId: string, xpEarned: number) =>
    analytics.track("learn_session_completed", "engagement", { course_id: courseId, xp_earned: xpEarned }),
  flashReviewCompleted: (conceptId: string, correct: boolean) =>
    analytics.track("flash_review_completed", "engagement", { concept_id: conceptId, correct }),
  coachMessageSent: (courseId: string) =>
    analytics.track("coach_message_sent", "feature", { course_id: courseId }),
  syllabusUploaded: (courseId: string) =>
    analytics.track("syllabus_uploaded", "feature", { course_id: courseId }),
  lectureUploaded: (courseId: string) =>
    analytics.track("lecture_uploaded", "feature", { course_id: courseId }),
  courseCreated: () =>
    analytics.track("course_created", "feature", {}),
  errorCaught: (errorMessage: string, componentStack?: string) =>
    analytics.track("error_caught", "error", {
      error_message: errorMessage,
      component_stack: componentStack?.slice(0, 500),
    }),
};
