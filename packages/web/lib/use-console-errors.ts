"use client";

import { useEffect } from "react";

const MAX_ERRORS = 10;
const capturedErrors: string[] = [];
let patched = false;

function safStringify(value: unknown): string {
  if (typeof value === "string") return value;
  try {
    return JSON.stringify(value);
  } catch {
    return String(value);
  }
}

function patchConsoleError() {
  if (patched) return;
  patched = true;
  const original = console.error.bind(console);
  console.error = (...args: unknown[]) => {
    const msg = args.map(safStringify).join(" ");
    capturedErrors.push(`${new Date().toISOString()} ${msg}`);
    if (capturedErrors.length > MAX_ERRORS) capturedErrors.shift();
    original(...args);
  };
}

export function useConsoleErrors(): () => string[] {
  useEffect(() => {
    patchConsoleError();
  }, []);
  return () => [...capturedErrors];
}
