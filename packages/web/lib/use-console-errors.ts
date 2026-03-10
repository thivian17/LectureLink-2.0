"use client";

const MAX_ERRORS = 10;
const capturedErrors: string[] = [];

// Monkey-patch console.error once at module load time (browser only)
if (typeof window !== "undefined") {
  const original = console.error.bind(console);
  console.error = (...args: unknown[]) => {
    const msg = args
      .map((a) => (typeof a === "string" ? a : JSON.stringify(a)))
      .join(" ");
    capturedErrors.push(`${new Date().toISOString()} ${msg}`);
    if (capturedErrors.length > MAX_ERRORS) capturedErrors.shift();
    original(...args);
  };
}

export function useConsoleErrors(): () => string[] {
  return () => [...capturedErrors];
}
