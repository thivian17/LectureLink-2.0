"use client";

import { useState, useEffect, useCallback } from "react";
import { toast } from "sonner";
import { Check } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { getSemesterProgress, saveAssessmentResult } from "@/lib/api";
import type { Assessment } from "@/types/database";
import { cn } from "@/lib/utils";

interface PastResultsStepProps {
  courseId: string;
  onContinue: () => void;
}

type ResultRow = Assessment & {
  score: string;
  saved: boolean;
  saving: boolean;
  skipped: boolean;
};

export function PastResultsStep({
  courseId,
  onContinue,
}: PastResultsStepProps) {
  const [rows, setRows] = useState<ResultRow[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function load() {
      try {
        const progress = await getSemesterProgress(courseId);
        setRows(
          progress.past_assessments.map((a) => ({
            ...a,
            score: "",
            saved: false,
            saving: false,
            skipped: false,
          })),
        );
      } catch {
        toast.error("Failed to load past assessments");
      } finally {
        setLoading(false);
      }
    }
    load();
  }, [courseId]);

  const handleSave = useCallback(
    async (assessmentId: string, scoreStr: string) => {
      const score = parseFloat(scoreStr);
      if (isNaN(score) || score < 0 || score > 100) return;

      setRows((prev) =>
        prev.map((r) =>
          r.id === assessmentId ? { ...r, saving: true } : r,
        ),
      );

      try {
        await saveAssessmentResult(assessmentId, score);
        setRows((prev) =>
          prev.map((r) =>
            r.id === assessmentId ? { ...r, saved: true, saving: false } : r,
          ),
        );
      } catch {
        setRows((prev) =>
          prev.map((r) =>
            r.id === assessmentId ? { ...r, saving: false } : r,
          ),
        );
        toast.error("Failed to save score");
      }
    },
    [],
  );

  const handleSkip = useCallback((assessmentId: string) => {
    setRows((prev) =>
      prev.map((r) =>
        r.id === assessmentId ? { ...r, skipped: true } : r,
      ),
    );
  }, []);

  if (loading) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-8 w-48" />
        {Array.from({ length: 3 }).map((_, i) => (
          <Skeleton key={i} className="h-16 w-full" />
        ))}
      </div>
    );
  }

  if (rows.length === 0) {
    return (
      <div className="space-y-6">
        <h2 className="text-xl font-semibold tracking-tight">Past Results</h2>
        <p className="text-muted-foreground">
          No past assessments found. Continue to the next step.
        </p>
        <div className="flex justify-end">
          <Button onClick={onContinue}>Continue &rarr;</Button>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="space-y-2">
        <h2 className="text-xl font-semibold tracking-tight">Past Results</h2>
        <p className="text-sm text-muted-foreground">
          These assessments have already passed. Adding your results helps me
          calibrate your study plan.
        </p>
      </div>

      <div className="space-y-2">
        {rows.map((row) => (
          <Card
            key={row.id}
            className={cn(row.skipped && "opacity-50")}
          >
            <CardContent className="flex items-center gap-4 pt-4 pb-4">
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2">
                  <span className="text-sm font-medium truncate">
                    {row.title}
                  </span>
                  {row.weight_percent != null && (
                    <Badge variant="outline" className="shrink-0">
                      {row.weight_percent}%
                    </Badge>
                  )}
                </div>
                {row.due_date && (
                  <p className="text-xs text-muted-foreground">{row.due_date}</p>
                )}
              </div>

              {!row.skipped && (
                <div className="flex items-center gap-2 shrink-0">
                  <div className="flex items-center gap-1">
                    <Input
                      type="number"
                      min={0}
                      max={100}
                      placeholder="--"
                      className="w-16 h-8 text-center"
                      value={row.score}
                      onChange={(e) => {
                        const val = e.target.value;
                        setRows((prev) =>
                          prev.map((r) =>
                            r.id === row.id ? { ...r, score: val, saved: false } : r,
                          ),
                        );
                      }}
                      onBlur={() => {
                        if (row.score) handleSave(row.id, row.score);
                      }}
                      disabled={row.saving}
                    />
                    <span className="text-xs text-muted-foreground">/ 100</span>
                  </div>
                  {row.saved && (
                    <Check className="h-4 w-4 text-green-600 shrink-0" />
                  )}
                  {!row.saved && (
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => handleSkip(row.id)}
                    >
                      Skip
                    </Button>
                  )}
                </div>
              )}
            </CardContent>
          </Card>
        ))}
      </div>

      <p className="text-xs text-muted-foreground text-center">
        This is optional. Your scores help estimate which topics need more
        attention.
      </p>

      <div className="flex justify-end">
        <Button onClick={onContinue}>Continue &rarr;</Button>
      </div>
    </div>
  );
}
