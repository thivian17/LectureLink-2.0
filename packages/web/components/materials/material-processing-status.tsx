"use client";

import { useEffect, useRef, useState, useCallback } from "react";
import { useRouter } from "next/navigation";
import {
  Upload,
  FileText,
  Brain,
  Search,
  Target,
  CheckCircle,
  Loader2,
  Circle,
  AlertCircle,
  RotateCcw,
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
import {
  getMaterialStatus,
  retryMaterial,
  AuthError,
  RateLimitError,
} from "@/lib/api";
import type { MaterialStatus } from "@/types/database";

const PROCESSING_STAGES = [
  { key: "uploading", label: "Uploading file", icon: Upload },
  { key: "extracting_text", label: "Extracting text", icon: FileText },
  { key: "extracting_concepts", label: "Extracting concepts", icon: Brain },
  { key: "generating_embeddings", label: "Indexing for search", icon: Search },
  { key: "mapping_concepts", label: "Mapping to assessments", icon: Target },
  { key: "completed", label: "Processing complete!", icon: CheckCircle },
] as const;

function getStageIndex(stage: string | null): number {
  if (!stage) return -1;
  return PROCESSING_STAGES.findIndex((s) => s.key === stage);
}

interface MaterialProcessingStatusProps {
  materialId: string;
  courseId: string;
  initialStatus?: MaterialStatus;
}

export function MaterialProcessingStatus({
  materialId,
  courseId,
  initialStatus,
}: MaterialProcessingStatusProps) {
  const router = useRouter();
  const [status, setStatus] = useState<MaterialStatus>(
    initialStatus ?? {
      id: materialId,
      processing_status: "processing",
      processing_stage: "uploading",
      processing_progress: 0,
      processing_error: null,
    },
  );
  const [retrying, setRetrying] = useState(false);
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
        const result = await getMaterialStatus(materialId);
        if (completedRef.current) return;
        setStatus(result);

        if (
          result.processing_status === "completed" ||
          result.processing_status === "failed"
        ) {
          completedRef.current = true;
          stopPolling();
          if (result.processing_status === "completed") {
            toast.success("Material processing complete!");
          }
        }
      } catch {
        // Keep polling on transient errors
      }
    }, 2000);
  }, [materialId, stopPolling]);

  useEffect(() => {
    if (
      status.processing_status !== "processing" &&
      status.processing_status !== "pending"
    ) {
      return;
    }

    completedRef.current = false;
    startPolling();

    return () => stopPolling();
  }, [status.processing_status, startPolling, stopPolling]);

  useEffect(() => {
    function handleVisibility() {
      if (document.hidden) {
        stopPolling();
      } else if (
        !completedRef.current &&
        (status.processing_status === "processing" ||
          status.processing_status === "pending")
      ) {
        startPolling();
      }
    }
    document.addEventListener("visibilitychange", handleVisibility);
    return () =>
      document.removeEventListener("visibilitychange", handleVisibility);
  }, [status.processing_status, startPolling, stopPolling]);

  async function handleRetry() {
    setRetrying(true);
    try {
      await retryMaterial(materialId);
      setStatus({
        id: materialId,
        processing_status: "processing",
        processing_stage: "uploading",
        processing_progress: 0,
        processing_error: null,
      });
      completedRef.current = false;
      toast.success("Retrying material processing...");
    } catch (err) {
      if (err instanceof AuthError) {
        toast.error("Session expired. Please log in again.");
        router.push("/login");
        return;
      }
      if (err instanceof RateLimitError) {
        toast.error(
          `Rate limit reached. Try again in ${Math.ceil(err.retryAfterSeconds / 60)} min.`,
        );
        return;
      }
      toast.error(
        err instanceof Error ? err.message : "Failed to retry processing",
      );
    } finally {
      setRetrying(false);
    }
  }

  const currentStageIndex = getStageIndex(status.processing_stage);
  const isCompleted = status.processing_status === "completed";
  const isFailed = status.processing_status === "failed";
  const progressPercent = Math.round(status.processing_progress * 100);

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">
          {isCompleted
            ? "Your material is ready!"
            : isFailed
              ? "Processing Failed"
              : "Processing Material..."}
        </CardTitle>
        <CardDescription>
          {isCompleted
            ? "All processing stages completed successfully."
            : isFailed
              ? "An error occurred during processing."
              : `${progressPercent}% complete`}
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-6">
        {/* Progress bar */}
        <div className="h-2 w-full overflow-hidden rounded-full bg-muted">
          <div
            className={cn(
              "h-full rounded-full transition-all duration-500",
              isFailed ? "bg-destructive" : "bg-primary",
            )}
            style={{ width: `${progressPercent}%` }}
          />
        </div>

        {/* Vertical stepper */}
        <div className="space-y-0">
          {PROCESSING_STAGES.map((stage, i) => {
            let stageStatus: "complete" | "active" | "error" | "pending";
            if (isCompleted) {
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

            const isLast = i === PROCESSING_STAGES.length - 1;

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
                        i < currentStageIndex || isCompleted
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

        {/* Error state */}
        {isFailed && status.processing_error && (
          <div className="rounded-md border border-destructive/50 bg-destructive/10 px-4 py-3">
            <p className="text-sm text-destructive">
              {status.processing_error}
            </p>
          </div>
        )}

        {/* Action buttons */}
        <div className="flex gap-2">
          {isCompleted && (
            <Button
              onClick={() =>
                router.push(`/dashboard/courses/${courseId}/materials`)
              }
            >
              View Materials
            </Button>
          )}
          {isFailed && (
            <Button onClick={handleRetry} disabled={retrying}>
              <RotateCcw className="mr-2 h-4 w-4" />
              {retrying ? "Retrying..." : "Retry"}
            </Button>
          )}
          {(isCompleted || isFailed) && (
            <Button
              variant="outline"
              onClick={() =>
                router.push(`/dashboard/courses/${courseId}/materials`)
              }
            >
              <ArrowLeft className="mr-2 h-4 w-4" />
              Back to Materials
            </Button>
          )}
        </div>
      </CardContent>
    </Card>
  );
}
