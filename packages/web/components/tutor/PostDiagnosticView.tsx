"use client";

import { useMemo } from "react";
import {
  Check,
  X,
  Minus,
  AlertTriangle,
  ArrowRight,
  ArrowLeft,
} from "lucide-react";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";
import { Skeleton } from "@/components/ui/skeleton";
import type { DiagnosticResult, AssessmentReadiness } from "@/types/database";

interface PostDiagnosticViewProps {
  diagnosticResult: DiagnosticResult;
  readiness: AssessmentReadiness | null;
  readinessLoading: boolean;
  onFillGaps?: () => void;
  onBackToCourse?: () => void;
}

export function PostDiagnosticView({
  diagnosticResult,
  readiness,
  readinessLoading,
  onFillGaps,
  onBackToCourse,
}: PostDiagnosticViewProps) {
  const pct =
    diagnosticResult.total_questions > 0
      ? Math.round(
          (diagnosticResult.total_correct / diagnosticResult.total_questions) *
            100,
        )
      : 0;

  // Build a map of tested concepts from diagnostic results
  const testedMap = useMemo(() => {
    const map = new Map<
      string,
      { correct: boolean; misconception?: string }
    >();
    for (const cr of diagnosticResult.concept_results) {
      if (!cr.concept) continue;
      map.set(cr.concept.toLowerCase().trim(), {
        correct: cr.correct,
        misconception: cr.misconception,
      });
    }
    return map;
  }, [diagnosticResult.concept_results]);

  const hasWeakAreas = readiness
    ? readiness.concepts.some((c) => c.mastery < 0.7)
    : diagnosticResult.identified_gaps.length > 0;

  return (
    <div className="space-y-4 max-w-2xl mx-auto">
      {/* Header + Score */}
      <Card>
        <CardHeader className="pb-3">
          <div className="flex items-center justify-between">
            <CardTitle className="text-lg">
              {readiness
                ? readiness.assessment_title
                : "Diagnostic Results"}
            </CardTitle>
            {readiness?.days_remaining != null && (
              <Badge
                variant={
                  readiness.days_remaining <= 3 ? "destructive" : "secondary"
                }
              >
                {readiness.days_remaining} day
                {readiness.days_remaining !== 1 ? "s" : ""} remaining
              </Badge>
            )}
          </div>
        </CardHeader>
        <CardContent>
          <div className="text-center py-2">
            <p className="text-3xl font-bold">
              {diagnosticResult.total_correct} of{" "}
              {diagnosticResult.total_questions}
            </p>
            <p className="text-sm text-muted-foreground">{pct}% correct</p>
          </div>
        </CardContent>
      </Card>

      {/* Concept Readiness Table */}
      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-base">Concept Breakdown</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          {readinessLoading ? (
            // Skeleton rows while readiness is loading
            <div className="space-y-3">
              {Array.from({ length: 5 }).map((_, i) => (
                <div key={i} className="space-y-1">
                  <div className="flex items-center justify-between">
                    <Skeleton className="h-4 w-40" />
                    <Skeleton className="h-4 w-20" />
                  </div>
                  <Skeleton className="h-1.5 w-full rounded-full" />
                </div>
              ))}
            </div>
          ) : readiness ? (
            // Full readiness data — show ALL assessment concepts
            <div className="space-y-3">
              {readiness.concepts.map((concept, i) => {
                const tested = testedMap.get(
                  concept.title.toLowerCase().trim(),
                );
                const masteryPct = Math.round(concept.mastery * 100);
                const hasAttempts = concept.total_attempts > 0;
                return (
                  <div key={i} className="space-y-1">
                    <div className="flex items-center gap-2 text-sm">
                      {/* Result icon */}
                      {tested ? (
                        tested.correct ? (
                          <Check className="h-4 w-4 shrink-0 text-green-600" />
                        ) : (
                          <X className="h-4 w-4 shrink-0 text-red-500" />
                        )
                      ) : (
                        <Minus className="h-4 w-4 shrink-0 text-muted-foreground" />
                      )}
                      <span className="flex-1 min-w-0 truncate">
                        {concept.title}
                      </span>
                      <div className="flex items-center gap-2 shrink-0">
                        <Badge
                          variant={tested ? "secondary" : "outline"}
                          className="text-[10px]"
                        >
                          {tested ? "Tested" : "Not Tested"}
                        </Badge>
                        {hasAttempts ? (
                          <span className="text-muted-foreground w-10 text-right">
                            {masteryPct}%
                          </span>
                        ) : (
                          <span className="text-xs text-muted-foreground w-10 text-right italic">—</span>
                        )}
                      </div>
                    </div>
                    {hasAttempts && (
                      <Progress
                        value={masteryPct}
                        className={`h-1.5 ${
                          masteryPct >= 70
                            ? "[&>div]:bg-green-500"
                            : masteryPct >= 40
                              ? "[&>div]:bg-amber-500"
                              : "[&>div]:bg-red-500"
                        }`}
                      />
                    )}
                  </div>
                );
              })}

              {/* Overall readiness */}
              <div className="border-t pt-3 mt-3">
                <div className="flex items-center justify-between text-sm">
                  <span className="font-medium">Overall Readiness</span>
                  <span className="font-medium">
                    {Math.round(readiness.overall_readiness * 100)}%
                  </span>
                </div>
                <Progress
                  value={Math.round(readiness.overall_readiness * 100)}
                  className="h-2 mt-1"
                />
                <p className="text-xs text-muted-foreground mt-1">
                  {readiness.ready_count} of {readiness.total_count} concepts at
                  70%+ mastery
                </p>
              </div>
            </div>
          ) : (
            // Fallback: no readiness data, show only diagnostic results
            <div className="space-y-2">
              {diagnosticResult.concept_results.map((cr, i) => (
                <div key={i} className="flex items-center gap-2 text-sm">
                  {cr.correct ? (
                    <Check className="h-4 w-4 shrink-0 text-green-600" />
                  ) : (
                    <X className="h-4 w-4 shrink-0 text-red-500" />
                  )}
                  <span className="flex-1">{cr.concept}</span>
                  {cr.misconception && (
                    <Badge variant="outline" className="text-[10px]">
                      {cr.misconception}
                    </Badge>
                  )}
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      {/* Gaps Identified */}
      {diagnosticResult.identified_gaps.length > 0 && (
        <Card>
          <CardContent className="pt-6 space-y-2">
            <div className="flex items-center gap-1.5 text-sm font-medium text-amber-600">
              <AlertTriangle className="h-4 w-4" />
              Gaps Identified
            </div>
            <ul className="list-disc list-inside text-sm text-muted-foreground space-y-0.5">
              {diagnosticResult.identified_gaps.map((gap, i) => (
                <li key={i}>{gap}</li>
              ))}
            </ul>
          </CardContent>
        </Card>
      )}

      {/* Actions */}
      <div className="flex gap-3">
        {onBackToCourse && (
          <Button variant="outline" className="flex-1" onClick={onBackToCourse}>
            <ArrowLeft className="mr-2 h-4 w-4" />
            Back to Course
          </Button>
        )}
        {hasWeakAreas && onFillGaps && (
          <Button className="flex-1" onClick={onFillGaps}>
            Fill in the Gaps
            <ArrowRight className="ml-2 h-4 w-4" />
          </Button>
        )}
      </div>
    </div>
  );
}
