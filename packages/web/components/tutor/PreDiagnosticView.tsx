"use client";

import { Loader2, ArrowRight } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";
import { Skeleton } from "@/components/ui/skeleton";
import type { AssessmentReadiness } from "@/types/database";

interface PreDiagnosticViewProps {
  readiness: AssessmentReadiness | null;
  loading: boolean;
  onBegin: () => void;
  beginning: boolean;
}

export function PreDiagnosticView({
  readiness,
  loading,
  onBegin,
  beginning,
}: PreDiagnosticViewProps) {
  if (loading) {
    return (
      <div className="space-y-4 max-w-2xl mx-auto">
        <Card>
          <CardHeader className="pb-3">
            <Skeleton className="h-6 w-48" />
            <Skeleton className="h-4 w-32 mt-1" />
          </CardHeader>
          <CardContent className="space-y-3">
            {Array.from({ length: 5 }).map((_, i) => (
              <div key={i} className="space-y-1">
                <div className="flex items-center justify-between">
                  <Skeleton className="h-4 w-40" />
                  <Skeleton className="h-4 w-12" />
                </div>
                <Skeleton className="h-1.5 w-full rounded-full" />
              </div>
            ))}
          </CardContent>
        </Card>
      </div>
    );
  }

  // No assessment data — simple start view
  if (!readiness) {
    return (
      <div className="space-y-4 max-w-2xl mx-auto">
        <Card>
          <CardContent className="py-8 text-center space-y-4">
            <p className="text-lg font-medium">Ready to begin</p>
            <p className="text-sm text-muted-foreground">
              This diagnostic will test your current knowledge to identify gaps.
            </p>
            <Button onClick={onBegin} disabled={beginning}>
              {beginning && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              Begin Diagnostic
              <ArrowRight className="ml-2 h-4 w-4" />
            </Button>
          </CardContent>
        </Card>
      </div>
    );
  }

  const attemptedConcepts = readiness.concepts.filter((c) => c.total_attempts > 0);
  const readyCount = attemptedConcepts.filter((c) => c.mastery >= 0.7).length;

  return (
    <div className="space-y-4 max-w-2xl mx-auto">
      <Card>
        <CardHeader className="pb-3">
          <div className="flex items-center justify-between">
            <CardTitle className="text-lg">
              {readiness.assessment_title}
            </CardTitle>
            {readiness.days_remaining != null && (
              <Badge
                variant={readiness.days_remaining <= 3 ? "destructive" : "secondary"}
              >
                {readiness.days_remaining} day
                {readiness.days_remaining !== 1 ? "s" : ""} remaining
              </Badge>
            )}
          </div>
        </CardHeader>
        <CardContent className="space-y-4">
          {/* Summary */}
          <p className="text-sm text-muted-foreground">
            {attemptedConcepts.length === 0
              ? `${readiness.concepts.length} concepts to cover — none assessed yet`
              : `${readyCount} of ${attemptedConcepts.length} assessed concepts at 70%+ mastery (${readiness.concepts.length} total)`
            }
          </p>

          {/* Concept table */}
          <div className="space-y-3">
            {readiness.concepts.map((concept, i) => {
              const masteryPct = Math.round(concept.mastery * 100);
              const hasAttempts = concept.total_attempts > 0;
              return (
                <div key={i} className="space-y-1">
                  <div className="flex items-center justify-between text-sm">
                    <span className="flex-1 min-w-0 truncate">
                      {concept.title}
                    </span>
                    <div className="flex items-center gap-2 shrink-0">
                      <Badge variant="outline" className="text-[10px]">
                        {concept.teaching_approach}
                      </Badge>
                      {hasAttempts ? (
                        <span className="text-muted-foreground w-10 text-right">
                          {masteryPct}%
                        </span>
                      ) : (
                        <span className="text-xs text-muted-foreground italic">Not Yet Assessed</span>
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
          </div>

          {/* Description */}
          <p className="text-sm text-muted-foreground text-center pt-2">
            This diagnostic will test your knowledge of these concepts to
            identify gaps.
          </p>

          {/* Begin button */}
          <Button className="w-full" onClick={onBegin} disabled={beginning}>
            {beginning && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
            Begin Diagnostic
            <ArrowRight className="ml-2 h-4 w-4" />
          </Button>
        </CardContent>
      </Card>
    </div>
  );
}
