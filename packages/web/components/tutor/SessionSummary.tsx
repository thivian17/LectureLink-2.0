"use client";

import { Trophy, Clock, Target, ArrowLeft, RotateCcw, ClipboardCheck } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import type { SessionSummary as SessionSummaryType } from "@/types/database";

interface SessionSummaryProps {
  summary: SessionSummaryType;
  onBackToCourse: () => void;
  onStartAnother: () => void;
  onRetestDiagnostic?: () => void;
}

function formatDuration(seconds: number): string {
  const m = Math.floor(seconds / 60);
  const s = seconds % 60;
  if (m === 0) return `${s}s`;
  return s > 0 ? `${m}m ${s}s` : `${m}m`;
}

export function SessionSummary({
  summary,
  onBackToCourse,
  onStartAnother,
  onRetestDiagnostic,
}: SessionSummaryProps) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-background/80 backdrop-blur-sm p-4">
      <Card className="w-full max-w-lg max-h-[90vh] overflow-y-auto">
        <CardHeader className="text-center">
          <Trophy className="mx-auto h-8 w-8 text-amber-500" />
          <CardTitle className="text-xl">Session Complete</CardTitle>
        </CardHeader>
        <CardContent className="space-y-6">
          {/* Stats */}
          <div className="grid grid-cols-3 gap-4 text-center">
            <div>
              <Clock className="mx-auto h-5 w-5 text-muted-foreground mb-1" />
              <p className="text-lg font-bold">
                {formatDuration(summary.duration_seconds)}
              </p>
              <p className="text-xs text-muted-foreground">Time spent</p>
            </div>
            <div>
              <Target className="mx-auto h-5 w-5 text-muted-foreground mb-1" />
              <p className="text-lg font-bold">
                {summary.total_correct}/{summary.total_questions}
              </p>
              <p className="text-xs text-muted-foreground">Correct</p>
            </div>
            <div>
              <div className="mx-auto mb-1 flex h-5 w-5 items-center justify-center text-muted-foreground text-sm font-bold">
                %
              </div>
              <p className="text-lg font-bold">{summary.accuracy_percent}%</p>
              <p className="text-xs text-muted-foreground">Accuracy</p>
            </div>
          </div>

          {/* Per-concept breakdown */}
          {summary.concepts_covered.length > 0 && (
            <div className="space-y-2">
              <p className="text-sm font-medium">Concepts Covered</p>
              {summary.concepts_covered.map((c, i) => {
                const acc =
                  c.questions_asked > 0
                    ? Math.round(
                        (c.questions_correct / c.questions_asked) * 100,
                      )
                    : 0;
                return (
                  <div
                    key={i}
                    className="flex items-center justify-between text-sm"
                  >
                    <span className="truncate flex-1 mr-2">
                      {c.concept_title}
                    </span>
                    <span className="text-muted-foreground shrink-0">
                      {c.questions_correct}/{c.questions_asked} ({acc}%)
                    </span>
                  </div>
                );
              })}
            </div>
          )}

          {/* Mastery changes */}
          {summary.mastery_changes && summary.mastery_changes.length > 0 && (
            <div className="space-y-2">
              <p className="text-sm font-medium">Mastery Changes</p>
              {summary.mastery_changes.map((mc, i) => {
                const wasAssessed = mc.before > 0;
                return (
                  <div key={i} className="space-y-1">
                    <div className="flex items-center justify-between text-sm">
                      <span className="truncate flex-1 mr-2">{mc.concept}</span>
                      <span className="text-muted-foreground shrink-0">
                        {wasAssessed
                          ? `${Math.round(mc.before * 100)}%`
                          : "New"}{" "}
                        &rarr; {Math.round(mc.after * 100)}%
                      </span>
                    </div>
                    <div className="flex gap-1 items-center">
                      {wasAssessed && (
                        <Progress
                          value={mc.before * 100}
                          className="h-1 flex-1 opacity-40"
                        />
                      )}
                      <Progress value={mc.after * 100} className="h-1.5 flex-1" />
                    </div>
                  </div>
                );
              })}
            </div>
          )}

          {/* Actions */}
          <div className="flex flex-col gap-3">
            {onRetestDiagnostic && (
              <Button className="w-full" onClick={onRetestDiagnostic}>
                <ClipboardCheck className="mr-2 h-4 w-4" />
                Re-Test Knowledge
              </Button>
            )}
            <div className="flex gap-3">
              <Button
                variant="outline"
                className="flex-1"
                onClick={onBackToCourse}
              >
                <ArrowLeft className="mr-2 h-4 w-4" />
                Back to Course
              </Button>
              <Button
                variant={onRetestDiagnostic ? "outline" : "default"}
                className="flex-1"
                onClick={onStartAnother}
              >
                <RotateCcw className="mr-2 h-4 w-4" />
                New Session
              </Button>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
