"use client";

import { CheckCircle, XCircle, BookOpen } from "lucide-react";
import { cn } from "@/lib/utils";

function formatTimestamp(seconds: number): string {
  const m = Math.floor(seconds / 60);
  const s = seconds % 60;
  return `${m}:${String(s).padStart(2, "0")}`;
}

interface QuestionFeedbackProps {
  isCorrect: boolean;
  explanation: string;
  sourceLectureId: string | null;
  sourceLectureTitle: string | null;
  sourceTimestampSeconds: number | null;
  courseId: string;
}

export function QuestionFeedback({
  isCorrect,
  explanation,
  sourceLectureId,
  sourceLectureTitle,
  sourceTimestampSeconds,
  courseId,
}: QuestionFeedbackProps) {
  return (
    <div
      className={cn(
        "mt-4 rounded-lg border p-4 space-y-2 animate-in fade-in duration-300",
        isCorrect
          ? "border-green-200 bg-green-50"
          : "border-red-200 bg-red-50",
      )}
    >
      <div className="flex items-center gap-2">
        {isCorrect ? (
          <>
            <CheckCircle className="h-5 w-5 text-green-600" />
            <span className="font-semibold text-green-700">Correct!</span>
          </>
        ) : (
          <>
            <XCircle className="h-5 w-5 text-red-600" />
            <span className="font-semibold text-red-700">Incorrect</span>
          </>
        )}
      </div>
      <p className="text-sm text-foreground/80">{explanation}</p>
      {sourceLectureId && sourceLectureTitle && (
        <a
          href={`/dashboard/courses/${courseId}/lectures/${sourceLectureId}${
            sourceTimestampSeconds != null
              ? `?t=${sourceTimestampSeconds}`
              : ""
          }`}
          className="inline-flex items-center gap-1 text-xs text-primary hover:underline"
        >
          <BookOpen className="h-3 w-3" />
          See in {sourceLectureTitle}
          {sourceTimestampSeconds != null &&
            ` at ${formatTimestamp(sourceTimestampSeconds)}`}
        </a>
      )}
    </div>
  );
}
