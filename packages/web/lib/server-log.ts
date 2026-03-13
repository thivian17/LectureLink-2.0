/**
 * Fire-and-forget client-side helper that sends a log entry to the
 * Next.js server so it appears in the server console / Cloud Run logs.
 */
export function serverLog(
  level: "warn" | "error",
  component: string,
  message: string,
  detail?: unknown,
) {
  fetch("/api/log", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ level, component, message, detail }),
  }).catch(() => {
    // logging should never break the app
  });
}
