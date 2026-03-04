"use client";

import { BookOpen, Clock, ArrowRight, Layers, CalendarClock } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import type { LessonPlan, AssessmentReadiness } from "@/types/database";

interface LessonPlanOverviewProps {
  plan: LessonPlan;
  assessmentReadiness: AssessmentReadiness | null;
  onBegin: () => void;
}

function approachLabel(
  approach: "foundational" | "application" | "synthesis",
): string {
  switch (approach) {
    case "foundational":
      return "Building foundations";
    case "application":
      return "Practice & apply";
    case "synthesis":
      return "Connect & deepen";
  }
}

function approachColor(
  approach: "foundational" | "application" | "synthesis",
): string {
  switch (approach) {
    case "foundational":
      return "text-blue-600 border-blue-200 bg-blue-50";
    case "application":
      return "text-amber-600 border-amber-200 bg-amber-50";
    case "synthesis":
      return "text-purple-600 border-purple-200 bg-purple-50";
  }
}

function masteryColor(mastery: number): string {
  if (mastery < 0.4) return "[&>div]:bg-red-500";
  if (mastery < 0.7) return "[&>div]:bg-amber-500";
  return "[&>div]:bg-green-500";
}

function statusLabel(mastery: number): string {
  if (mastery < 0.4) return "Weak";
  if (mastery < 0.7) return "Developing";
  return "Strong";
}

function statusColor(mastery: number): string {
  if (mastery < 0.4) return "text-red-600 border-red-200";
  if (mastery < 0.7) return "text-yellow-600 border-yellow-200";
  return "text-green-600 border-green-200";
}

export function LessonPlanOverview({
  plan,
  assessmentReadiness,
  onBegin,
}: LessonPlanOverviewProps) {
  const totalMinutes = plan.estimated_duration_minutes;
  const conceptCount = plan.concepts.length;

  // Build set of concept keys covered in the plan
  const planConceptKeys = new Set(
    plan.concepts.map((c) => c.concept_id ?? c.title),
  );

  // Concepts on the assessment but NOT in this session's plan
  const notCovered =
    assessmentReadiness?.concepts.filter(
      (c) => !planConceptKeys.has(c.concept_id ?? c.title),
    ) ?? [];

  // How many more sessions to cover remaining concepts
  const remainingSessions =
    notCovered.length > 0 && conceptCount > 0
      ? Math.ceil(notCovered.length / conceptCount)
      : 0;

  return (
    <div className="mx-auto max-w-2xl space-y-6 px-4 py-8">
      {/* Header */}
      <div className="text-center space-y-2">
        <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-full bg-primary/10">
          <BookOpen className="h-6 w-6 text-primary" />
        </div>
        <h1 className="text-2xl font-bold tracking-tight">
          {plan.session_title || "Your Study Plan"}
        </h1>
        <p className="text-muted-foreground">
          Here&apos;s what we&apos;ll cover in this session
        </p>
      </div>

      {/* Session stats */}
      <div className="grid grid-cols-2 gap-3">
        <Card>
          <CardContent className="flex items-center gap-3 py-4">
            <Layers className="h-5 w-5 text-muted-foreground shrink-0" />
            <div>
              <p className="text-2xl font-bold">{conceptCount}</p>
              <p className="text-xs text-muted-foreground">
                concept{conceptCount !== 1 ? "s" : ""}
              </p>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="flex items-center gap-3 py-4">
            <Clock className="h-5 w-5 text-muted-foreground shrink-0" />
            <div>
              <p className="text-2xl font-bold">~{totalMinutes}</p>
              <p className="text-xs text-muted-foreground">minutes</p>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Concept list */}
      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-base">This Session</CardTitle>
          <CardDescription>
            Ordered by priority — weakest concepts first
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          {plan.concepts.map((concept, i) => {
            const masteryPct = Math.round(concept.mastery * 100);
            const hasAttempts = (concept.total_attempts ?? 0) > 0;
            return (
              <div key={concept.concept_id ?? concept.title} className="space-y-2">
                <div className="flex items-start gap-3">
                  <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-muted text-xs font-medium">
                    {i + 1}
                  </span>
                  <div className="flex-1 min-w-0 space-y-1.5">
                    <div className="flex items-center justify-between gap-2">
                      <p className="text-sm font-medium leading-tight">
                        {concept.title}
                      </p>
                      <span className="text-xs text-muted-foreground shrink-0">
                        ~{concept.estimated_minutes} min
                      </span>
                    </div>

                    {/* Mastery bar */}
                    {hasAttempts ? (
                      <div className="flex items-center gap-2">
                        <Progress
                          value={masteryPct}
                          className={`h-1.5 flex-1 ${masteryColor(concept.mastery)}`}
                        />
                        <span className="text-xs text-muted-foreground w-8 text-right">
                          {masteryPct}%
                        </span>
                      </div>
                    ) : (
                      <span className="text-xs text-muted-foreground italic">
                        Not Yet Assessed
                      </span>
                    )}

                    {/* Approach badge */}
                    <Badge
                      variant="outline"
                      className={`text-[10px] ${approachColor(concept.teaching_approach)}`}
                    >
                      {approachLabel(concept.teaching_approach)}
                    </Badge>
                  </div>
                </div>
                {i < plan.concepts.length - 1 && (
                  <div className="ml-3 border-l-2 border-dashed border-muted h-2" />
                )}
              </div>
            );
          })}
        </CardContent>
      </Card>

      {/* Not covered concepts */}
      {notCovered.length > 0 && (
        <Card className="border-dashed">
          <CardHeader className="pb-3">
            <div className="flex items-center gap-2">
              <CalendarClock className="h-4 w-4 text-muted-foreground" />
              <CardTitle className="text-base">Coming Up</CardTitle>
            </div>
            <CardDescription>
              {notCovered.length} more concept{notCovered.length !== 1 ? "s" : ""}{" "}
              on this assessment — approximately{" "}
              <strong>
                {remainingSessions} more session
                {remainingSessions !== 1 ? "s" : ""}
              </strong>{" "}
              to cover them all
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-2">
            {notCovered
              .sort((a, b) => a.mastery - b.mastery)
              .map((concept) => {
                const masteryPct = Math.round(concept.mastery * 100);
                const hasAttempts = concept.total_attempts > 0;
                return (
                  <div
                    key={concept.concept_id ?? concept.title}
                    className="flex items-center gap-2 text-sm text-muted-foreground"
                  >
                    <span className="flex-1 min-w-0 truncate">
                      {concept.title}
                    </span>
                    {hasAttempts ? (
                      <>
                        <Badge
                          variant="outline"
                          className={`text-[10px] shrink-0 ${statusColor(concept.mastery)}`}
                        >
                          {statusLabel(concept.mastery)}
                        </Badge>
                        <span className="w-8 text-right text-xs shrink-0">
                          {masteryPct}%
                        </span>
                      </>
                    ) : (
                      <span className="text-xs italic shrink-0">
                        Not Yet Assessed
                      </span>
                    )}
                  </div>
                );
              })}
          </CardContent>
        </Card>
      )}

      {/* Begin button */}
      <Button size="lg" className="w-full" onClick={onBegin}>
        Begin Session
        <ArrowRight className="ml-2 h-4 w-4" />
      </Button>
    </div>
  );
}
