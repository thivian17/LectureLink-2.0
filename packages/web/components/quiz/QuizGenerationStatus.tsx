"use client";

import { useEffect, useRef, useState, useCallback } from "react";
import { useRouter } from "next/navigation";
import {
  ClipboardList,
  MessageSquarePlus,
  ShieldCheck,
  CheckCircle,
  Loader2,
  Circle,
  AlertCircle,
  ArrowLeft,
} from "lucide-react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { cn } from "@/lib/utils";
import { getQuizGenerationStatus } from "@/lib/api";
import type { QuizGenerationStatus as QuizGenStatus } from "@/types/database";

const GENERATION_STAGES = [
  { key: "planning", label: "Planning practice test...", icon: ClipboardList },
  {
    key: "generating_questions",
    label: "Generating questions...",
    icon: MessageSquarePlus,
  },
  {
    key: "reviewing_quality",
    label: "Reviewing quality...",
    icon: ShieldCheck,
  },
  { key: "ready", label: "Ready!", icon: CheckCircle },
] as const;

function getStageIndex(stage: string | null): number {
  if (!stage) return -1;
  return GENERATION_STAGES.findIndex((s) => s.key === stage);
}

interface QuizGenerationStatusProps {
  quizId: string;
  courseId: string;
}

export function QuizGenerationStatus({
  quizId,
  courseId,
}: QuizGenerationStatusProps) {
  const router = useRouter();
  const [status, setStatus] = useState<QuizGenStatus>({
    quiz_id: quizId,
    status: "generating",
    stage: "planning",
    error_message: null,
  });
  const pollingRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const completedRef = useRef(false);

  const stopPolling = useCallback(() => {
    if (pollingRef.current) {
      clearInterval(pollingRef.current);
      pollingRef.current = null;
    }
  }, []);

  const startPolling = useCallback(() => {
    if (pollingRef.current || completedRef.current) return;
    pollingRef.current = setInterval(async () => {
      if (completedRef.current) return;
      try {
        const result = await getQuizGenerationStatus(quizId);
        if (completedRef.current) return;
        setStatus(result);

        if (result.status === "ready" || result.status === "failed") {
          completedRef.current = true;
          stopPolling();
          if (result.status === "ready") {
            toast.success("Practice test is ready!");
            router.push(
              `/dashboard/courses/${courseId}/quiz/${quizId}`,
            );
          }
        }
      } catch {
        // Keep polling on transient errors
      }
    }, 3000);
  }, [quizId, courseId, stopPolling, router]);

  useEffect(() => {
    if (status.status !== "generating" && status.status !== "pending") return;

    completedRef.current = false;
    startPolling();

    return () => stopPolling();
  }, [status.status, startPolling, stopPolling]);

  // Stop polling when tab is hidden, restart when visible
  useEffect(() => {
    function handleVisibility() {
      if (document.hidden) {
        stopPolling();
      } else if (
        !completedRef.current &&
        (status.status === "generating" || status.status === "pending")
      ) {
        startPolling();
      }
    }
    document.addEventListener("visibilitychange", handleVisibility);
    return () =>
      document.removeEventListener("visibilitychange", handleVisibility);
  }, [status.status, startPolling, stopPolling]);

  const currentStageIndex = getStageIndex(status.stage);
  const isReady = status.status === "ready";
  const isFailed = status.status === "failed";

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">
          {isReady
            ? "Your practice test is ready!"
            : isFailed
              ? "Generation Failed"
              : "Generating Practice Test..."}
        </CardTitle>
        <CardDescription>
          {isReady
            ? "All generation stages completed successfully."
            : isFailed
              ? "An error occurred during practice test generation."
              : "This usually takes about 30 seconds."}
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-6">
        <div className="space-y-0">
          {GENERATION_STAGES.map((stage, i) => {
            let stageStatus: "complete" | "active" | "error" | "pending";
            if (isReady) {
              stageStatus = "complete";
            } else if (isFailed && i === currentStageIndex) {
              stageStatus = "error";
            } else if (i < currentStageIndex) {
              stageStatus = "complete";
            } else if (i === currentStageIndex) {
              stageStatus = "active";
            } else {
              stageStatus = "pending";
            }

            const isLast = i === GENERATION_STAGES.length - 1;

            return (
              <div key={stage.key} className="flex gap-3">
                <div className="flex flex-col items-center">
                  <div
                    className={cn(
                      "flex h-8 w-8 shrink-0 items-center justify-center rounded-full border-2 transition-colors",
                      stageStatus === "complete" &&
                        "border-primary bg-primary text-primary-foreground",
                      stageStatus === "active" &&
                        "border-primary text-primary",
                      stageStatus === "error" &&
                        "border-destructive bg-destructive/10 text-destructive",
                      stageStatus === "pending" &&
                        "border-muted text-muted-foreground",
                    )}
                  >
                    {stageStatus === "complete" ? (
                      <CheckCircle className="h-4 w-4" />
                    ) : stageStatus === "active" ? (
                      <Loader2 className="h-4 w-4 animate-spin" />
                    ) : stageStatus === "error" ? (
                      <AlertCircle className="h-4 w-4" />
                    ) : (
                      <Circle className="h-4 w-4" />
                    )}
                  </div>
                  {!isLast && (
                    <div
                      className={cn(
                        "w-0.5 flex-1 min-h-4 transition-colors",
                        i < currentStageIndex || isReady
                          ? "bg-primary"
                          : "bg-border",
                      )}
                    />
                  )}
                </div>
                <div className={cn("pb-4", isLast && "pb-0")}>
                  <p
                    className={cn(
                      "pt-1 text-sm font-medium leading-none",
                      stageStatus === "complete" && "text-foreground",
                      stageStatus === "active" && "text-primary",
                      stageStatus === "error" && "text-destructive",
                      stageStatus === "pending" && "text-muted-foreground",
                    )}
                  >
                    {stage.label}
                  </p>
                </div>
              </div>
            );
          })}
        </div>

        {isFailed && status.error_message && (
          <div className="rounded-md border border-destructive/50 bg-destructive/10 px-4 py-3">
            <p className="text-sm text-destructive">{status.error_message}</p>
          </div>
        )}

        {(isReady || isFailed) && (
          <Button
            variant="outline"
            onClick={() =>
              router.push(`/dashboard/courses/${courseId}/quizzes`)
            }
          >
            <ArrowLeft className="mr-2 h-4 w-4" />
            Back to Practice Tests
          </Button>
        )}
      </CardContent>
    </Card>
  );
}
