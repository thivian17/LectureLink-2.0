"use client";

import { useState, useEffect } from "react";
import { X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { toast } from "sonner";
import { createClient } from "@/lib/supabase/client";
import { submitNPS } from "@/lib/feedback-api";

const NPS_STORAGE_KEY = "ll_nps_last_shown";
const NPS_COOLDOWN_DAYS = 30;
const NPS_SESSION_THRESHOLD = 3;

export function FeedbackWidget() {
  const [visible, setVisible] = useState(false);
  const [step, setStep] = useState<"rating" | "message" | "done">("rating");
  const [rating, setRating] = useState<number | null>(null);
  const [message, setMessage] = useState("");
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    async function checkShouldShow() {
      try {
        const lastShown = localStorage.getItem(NPS_STORAGE_KEY);
        if (lastShown) {
          const daysSince =
            (Date.now() - Number(lastShown)) / (1000 * 60 * 60 * 24);
          if (daysSince < NPS_COOLDOWN_DAYS) return;
        }
      } catch {
        return;
      }

      const supabase = createClient();
      const {
        data: { user },
      } = await supabase.auth.getUser();
      if (!user) return;

      const { count } = await supabase
        .from("learn_sessions")
        .select("id", { count: "exact", head: true })
        .eq("user_id", user.id)
        .eq("status", "completed");

      if ((count ?? 0) >= NPS_SESSION_THRESHOLD) {
        setVisible(true);
        try {
          localStorage.setItem(NPS_STORAGE_KEY, String(Date.now()));
        } catch {}
      }
    }
    void checkShouldShow();
  }, []);

  async function handleRating(score: number) {
    setRating(score);
    setStep("message");
  }

  async function handleSubmit() {
    if (!rating) return;
    setSubmitting(true);
    try {
      await submitNPS({ rating, message: message.trim() || undefined });
      setStep("done");
      toast.success("Thanks for the feedback!");
      setTimeout(() => setVisible(false), 2000);
    } catch {
      toast.error("Couldn't save your feedback");
    } finally {
      setSubmitting(false);
    }
  }

  if (!visible) return null;

  return (
    <div className="fixed bottom-6 right-6 z-50 w-80 rounded-xl border bg-card shadow-lg p-4 space-y-3">
      <div className="flex items-start justify-between">
        <p className="text-sm font-medium">
          {step === "rating" && "How likely are you to recommend LectureLink?"}
          {step === "message" && "Any thoughts to share?"}
          {step === "done" && "Thanks for your feedback!"}
        </p>
        <Button
          variant="ghost"
          size="icon"
          className="h-6 w-6 -mr-1 -mt-1"
          onClick={() => setVisible(false)}
        >
          <X className="h-3 w-3" />
        </Button>
      </div>

      {step === "rating" && (
        <>
          <div className="flex gap-1 flex-wrap">
            {[1, 2, 3, 4, 5, 6, 7, 8, 9, 10].map((n) => (
              <button
                key={n}
                onClick={() => handleRating(n)}
                className={`w-8 h-8 rounded text-xs font-medium transition-colors border hover:border-transparent
                  ${
                    n <= 6
                      ? "hover:bg-red-100 hover:text-red-700"
                      : n <= 8
                        ? "hover:bg-amber-100 hover:text-amber-700"
                        : "hover:bg-green-100 hover:text-green-700"
                  }`}
              >
                {n}
              </button>
            ))}
          </div>
          <div className="flex justify-between text-xs text-muted-foreground px-1">
            <span>Not at all likely</span>
            <span>Extremely likely</span>
          </div>
        </>
      )}

      {step === "message" && (
        <div className="space-y-2">
          <textarea
            className="w-full text-sm rounded-md border border-input bg-background px-3 py-2 min-h-[70px] placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            placeholder="What could make it better? (optional)"
            value={message}
            onChange={(e) => setMessage(e.target.value)}
            maxLength={500}
          />
          <Button
            size="sm"
            className="w-full"
            onClick={handleSubmit}
            disabled={submitting}
          >
            Send Feedback
          </Button>
        </div>
      )}
    </div>
  );
}
