"use client";

import React, { useState, useEffect, useRef, useCallback } from "react";
import { format } from "date-fns";
import { AlertTriangle, Clock, RotateCcw } from "lucide-react";
import { toast } from "sonner";

import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";
import { StatusBadge } from "@/components/lectures/status-badge";
import { formatDuration } from "@/lib/format";
import { retryLecture, getLectureStatus } from "@/lib/api";
import type { Lecture } from "@/types/database";

const STAGE_LABELS: Record<string, string> = {
  uploading: "Uploading files",
  transcribing: "Transcribing audio",
  analyzing_slides: "Analyzing slides",
  aligning: "Aligning content",
  extracting_concepts: "Extracting concepts",
  generating_embeddings: "Indexing for search",
  mapping_concepts: "Mapping to assessments",
};

function parseLocalDate(dateStr: string): Date {
  const [year, month, day] = dateStr.split("-").map(Number);
  return new Date(year, month - 1, day);
}

interface LectureCardProps {
  lecture: Lecture;
  courseId: string;
  onRetry?: () => void;
}

export const LectureCard = React.memo(function LectureCard({ lecture, courseId, onRetry }: LectureCardProps) {
  const [retrying, setRetrying] = useState(false);
  const [progress, setProgress] = useState(lecture.processing_progress);
  const [stage, setStage] = useState(lecture.processing_stage);
  const [status, setStatus] = useState(lecture.processing_status);
  const pollingRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const isActive = status === "processing" || status === "pending";

  const stopPolling = useCallback(() => {
    if (pollingRef.current) {
      clearInterval(pollingRef.current);
      pollingRef.current = null;
    }
  }, []);

  useEffect(() => {
    if (!isActive) return;

    pollingRef.current = setInterval(async () => {
      try {
        const result = await getLectureStatus(lecture.id);
        setProgress(result.processing_progress);
        setStage(result.processing_stage);
        setStatus(result.processing_status);

        if (result.processing_status === "completed" || result.processing_status === "failed") {
          stopPolling();
          if (result.processing_status === "completed") {
            onRetry?.(); // refresh list to show completed state
          }
        }
      } catch {
        // transient error, keep polling
      }
    }, 4000);

    return () => stopPolling();
  }, [isActive, lecture.id, stopPolling, onRetry]);

  async function handleRetry(e: React.MouseEvent) {
    e.preventDefault();
    e.stopPropagation();
    setRetrying(true);
    try {
      await retryLecture(lecture.id);
      toast.success("Lecture queued for retry");
      setStatus("processing");
      setProgress(0);
      setStage("uploading");
      onRetry?.();
    } catch {
      toast.error("Failed to retry lecture");
    } finally {
      setRetrying(false);
    }
  }

  const progressPercent = Math.round(progress * 100);
  const stageLabel = stage ? STAGE_LABELS[stage] ?? stage : "Queued";

  return (
    <div>
      <Card className="h-full">
        <CardHeader className="pb-3">
          <div className="flex items-start justify-between gap-2">
            <div className="min-w-0 flex-1">
              <CardTitle className="text-base leading-tight truncate">
                {lecture.title}
              </CardTitle>
              {lecture.lecture_date && (
                <CardDescription className="mt-1">
                  {format(parseLocalDate(lecture.lecture_date), "MMM d, yyyy")}
                </CardDescription>
              )}
            </div>
            {lecture.lecture_number != null && (
              <Badge variant="secondary" className="shrink-0 text-xs">
                Lec #{lecture.lecture_number}
              </Badge>
            )}
          </div>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="flex items-center gap-2">
            <StatusBadge status={status} />
            {status === "completed" &&
              lecture.duration_seconds != null && (
                <span className="flex items-center gap-1 text-xs text-muted-foreground">
                  <Clock className="h-3 w-3" />
                  {formatDuration(lecture.duration_seconds)}
                </span>
              )}
            {status === "failed" && (
              <Button
                variant="outline"
                size="sm"
                className="h-6 gap-1 text-xs"
                disabled={retrying}
                onClick={handleRetry}
              >
                <RotateCcw className={`h-3 w-3 ${retrying ? "animate-spin" : ""}`} />
                {retrying ? "Retrying…" : "Retry"}
              </Button>
            )}
          </div>
          {isActive && (
            <div className="space-y-1.5">
              <Progress value={progressPercent} className="h-1.5" />
              <p className="text-xs text-muted-foreground">
                {stageLabel} &middot; {progressPercent}%
              </p>
            </div>
          )}
          {status === "completed" && lecture.low_concept_yield && (
            <Badge
              variant="outline"
              className="gap-1 font-medium bg-amber-50 text-amber-700 border-amber-200"
            >
              <AlertTriangle className="h-3 w-3" />
              Few concepts found
            </Badge>
          )}
          {status === "completed" && lecture.summary && (
            <p className="text-sm text-muted-foreground line-clamp-2">
              {lecture.summary.length > 100
                ? lecture.summary.slice(0, 100) + "..."
                : lecture.summary}
            </p>
          )}
        </CardContent>
      </Card>
    </div>
  );
});
