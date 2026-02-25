"use client";

import { useState } from "react";
import { ThumbsUp, ThumbsDown, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { toast } from "sonner";
import { submitGradingFeedback } from "@/lib/api";

interface GradingFeedbackProps {
  sessionId: string;
  eventId: string;
}

export function GradingFeedback({ sessionId, eventId }: GradingFeedbackProps) {
  const [submitted, setSubmitted] = useState<"accurate" | "inaccurate" | null>(
    null,
  );
  const [showTextInput, setShowTextInput] = useState(false);
  const [feedbackText, setFeedbackText] = useState("");
  const [submitting, setSubmitting] = useState(false);

  async function handleFeedback(type: "accurate" | "inaccurate") {
    setSubmitting(true);
    try {
      await submitGradingFeedback(sessionId, {
        event_id: eventId,
        feedback_type: type,
        feedback_text: type === "inaccurate" && feedbackText ? feedbackText : undefined,
      });
      setSubmitted(type);
      if (type === "inaccurate" && !showTextInput) {
        setShowTextInput(true);
        setSubmitting(false);
        return;
      }
      toast.success("Thanks for the feedback!");
    } catch {
      toast.error("Failed to submit feedback");
    } finally {
      setSubmitting(false);
    }
  }

  if (submitted === "accurate") {
    return (
      <p className="text-xs text-muted-foreground">Thanks for confirming!</p>
    );
  }

  if (submitted === "inaccurate" && !showTextInput) {
    return (
      <p className="text-xs text-muted-foreground">
        Thanks — we&apos;ll improve.
      </p>
    );
  }

  return (
    <div className="space-y-2">
      <div className="flex items-center gap-2">
        <span className="text-xs text-muted-foreground">
          Was this grading accurate?
        </span>
        <Button
          variant="ghost"
          size="xs"
          onClick={() => handleFeedback("accurate")}
          disabled={submitting}
        >
          <ThumbsUp className="h-3 w-3" />
        </Button>
        <Button
          variant="ghost"
          size="xs"
          onClick={() => {
            if (!showTextInput) {
              setShowTextInput(true);
            } else {
              handleFeedback("inaccurate");
            }
          }}
          disabled={submitting}
        >
          {submitting ? (
            <Loader2 className="h-3 w-3 animate-spin" />
          ) : (
            <ThumbsDown className="h-3 w-3" />
          )}
        </Button>
      </div>
      {showTextInput && !submitted && (
        <div className="flex items-center gap-2">
          <input
            type="text"
            value={feedbackText}
            onChange={(e) => setFeedbackText(e.target.value)}
            placeholder="What was wrong? (optional)"
            className="flex-1 rounded-md border bg-background px-2 py-1 text-xs"
          />
          <Button
            variant="outline"
            size="xs"
            onClick={() => handleFeedback("inaccurate")}
            disabled={submitting}
          >
            Send
          </Button>
        </div>
      )}
    </div>
  );
}
