"use client";

import { useState, useEffect, useCallback, useRef } from "react";
import { Loader2 } from "lucide-react";
import { getCourses, getLectures } from "@/lib/api";
import type { Lecture } from "@/types/database";

/**
 * Banner shown on the dashboard when any lectures are still processing.
 * Polls every 15 seconds and auto-hides when all lectures complete.
 */
export function ProcessingBanner() {
  const [processingLectures, setProcessingLectures] = useState<Lecture[]>([]);
  const [checked, setChecked] = useState(false);
  const pollingRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const checkProcessing = useCallback(async () => {
    try {
      const courses = await getCourses();
      if (courses.length === 0) {
        setProcessingLectures([]);
        setChecked(true);
        return;
      }

      const allLectures = await Promise.all(
        courses.map((c) => getLectures(c.id).catch(() => [] as Lecture[])),
      );

      const active = allLectures
        .flat()
        .filter(
          (l) =>
            l.processing_status === "processing" ||
            l.processing_status === "pending",
        );

      setProcessingLectures(active);
      setChecked(true);
    } catch {
      setChecked(true);
    }
  }, []);

  useEffect(() => {
    checkProcessing();
    pollingRef.current = setInterval(checkProcessing, 15000);
    return () => {
      if (pollingRef.current) clearInterval(pollingRef.current);
    };
  }, [checkProcessing]);

  if (!checked || processingLectures.length === 0) return null;

  const count = processingLectures.length;
  const noun = count === 1 ? "lecture is" : "lectures are";

  return (
    <div className="flex items-start gap-3 rounded-lg border border-blue-200 bg-blue-50 px-4 py-3 dark:border-blue-800 dark:bg-blue-950/50">
      <Loader2 className="mt-0.5 h-4 w-4 shrink-0 animate-spin text-blue-600 dark:text-blue-400" />
      <p className="text-sm text-blue-800 dark:text-blue-200">
        <strong>{count} {noun} still being processed.</strong>{" "}
        Wait for full processing to get up-to-date study actions and readiness scores.
      </p>
    </div>
  );
}
