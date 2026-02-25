"use client";

import { useState } from "react";
import { Check, X, ChevronDown, ChevronUp } from "lucide-react";
import { cn } from "@/lib/utils";
import { GradingFeedback } from "@/components/tutor/GradingFeedback";
import type { GradingResult } from "@/types/database";

interface FeedbackBlockProps {
  result: GradingResult;
  sessionId: string;
  eventId: string;
}

export function FeedbackBlock({
  result,
  sessionId,
  eventId,
}: FeedbackBlockProps) {
  const [showModel, setShowModel] = useState(false);

  return (
    <div
      className={cn(
        "rounded-lg border-l-4 p-4 space-y-3",
        result.is_correct
          ? "border-l-green-500 bg-green-50 dark:bg-green-950/20"
          : "border-l-orange-500 bg-orange-50 dark:bg-orange-950/20",
      )}
    >
      <div className="flex items-start gap-3">
        <div
          className={cn(
            "mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full",
            result.is_correct
              ? "bg-green-500 text-white"
              : "bg-orange-500 text-white",
          )}
        >
          {result.is_correct ? (
            <Check className="h-3 w-3" />
          ) : (
            <X className="h-3 w-3" />
          )}
        </div>
        <div className="space-y-1 min-w-0">
          <p className="text-sm font-medium">
            {result.is_correct ? "Correct!" : "Not quite"}
          </p>
          <p className="text-sm text-muted-foreground leading-relaxed">
            {result.feedback}
          </p>
        </div>
      </div>

      {result.model_answer && (
        <div>
          <button
            onClick={() => setShowModel(!showModel)}
            className="flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground transition-colors"
          >
            {showModel ? (
              <ChevronUp className="h-3 w-3" />
            ) : (
              <ChevronDown className="h-3 w-3" />
            )}
            See model answer
          </button>
          {showModel && (
            <div className="mt-2 rounded-md bg-muted/50 p-3 text-sm leading-relaxed">
              {result.model_answer}
            </div>
          )}
        </div>
      )}

      {result.grading_confidence < 0.7 && (
        <p className="text-xs text-muted-foreground italic">
          AI assessment — let me know if this seems off
        </p>
      )}

      {result.grading_confidence < 1.0 && (
        <GradingFeedback sessionId={sessionId} eventId={eventId} />
      )}
    </div>
  );
}
