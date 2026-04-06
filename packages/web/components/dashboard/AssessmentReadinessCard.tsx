"use client";

import { useState } from "react";
import Link from "next/link";
import { ChevronDown, ChevronUp, Loader2 } from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { ReadinessBreakdown } from "./ReadinessBreakdown";
import { getAssessmentReadinessV2 } from "@/lib/api";
import type { AssessmentReadinessV2 } from "@/types/database";

interface AssessmentReadinessCardProps {
  assessment: AssessmentReadinessV2;
}

const ACTION_ROUTES: Record<string, string> = {
  study_session: "learn",
  practice_test: "quizzes",
  flash_review: "learn",
};

function getStudyHref(data: AssessmentReadinessV2): string {
  const base = `/dashboard/courses/${data.course_id}/learn`;
  // If we have weak concepts, pass them so the session targets them directly
  if (data.weak_concepts && data.weak_concepts.length > 0) {
    const ids = data.weak_concepts.map((wc) => wc.concept_id).join(",");
    return `${base}?concepts=${ids}`;
  }
  // Otherwise pass the assessment ID for schedule-based concept selection
  return `${base}?assessmentId=${data.assessment_id}`;
}

function readinessColor(pct: number): string {
  if (pct >= 80) return "text-green-600";
  if (pct >= 60) return "text-amber-500";
  return "text-red-500";
}

function daysBadgeVariant(days: number | null): string {
  if (days == null) return "";
  if (days <= 3) return "bg-red-100 text-red-700 border-red-200";
  if (days <= 7) return "bg-amber-100 text-amber-700 border-amber-200";
  return "";
}

export function AssessmentReadinessCard({
  assessment: initialData,
}: AssessmentReadinessCardProps) {
  const [expanded, setExpanded] = useState(false);
  const [fullData, setFullData] = useState<AssessmentReadinessV2 | null>(null);
  const [fetching, setFetching] = useState(false);

  const data = fullData ?? initialData;
  const pct = Math.round(data.readiness * 100);
  const hasBreakdown = fullData != null;

  async function handleToggle() {
    if (!expanded && !fullData && !fetching) {
      setFetching(true);
      try {
        const result = await getAssessmentReadinessV2(data.assessment_id);
        setFullData(result);
      } catch {
        // Show what we have
      } finally {
        setFetching(false);
      }
    }
    setExpanded((prev) => !prev);
  }

  return (
    <Card>
      <CardContent className="pt-5 pb-5 space-y-3">
        {/* Header */}
        <div className="flex items-start justify-between gap-2">
          <div className="flex-1 min-w-0">
            <p className="font-medium text-sm truncate">{data.title}</p>
            <div className="flex items-center gap-1.5 mt-1">
              {data.course_name && (
                <Badge variant="outline" className="text-xs">
                  {data.course_name}
                </Badge>
              )}
              {data.days_until_due != null && (
                <Badge
                  variant="secondary"
                  className={cn("text-xs", daysBadgeVariant(data.days_until_due))}
                >
                  {data.days_until_due}d
                </Badge>
              )}
            </div>
          </div>
          <div className="flex flex-col items-end gap-1.5 shrink-0">
            <span
              className={cn(
                "text-3xl font-bold tabular-nums",
                readinessColor(pct),
              )}
            >
              {pct}%
            </span>
            {data.course_id && (
              <Button asChild size="sm" variant="secondary" className="text-xs h-7">
                <Link href={getStudyHref(data)}>Study</Link>
              </Button>
            )}
          </div>
        </div>

        {/* Expand toggle */}
        <button
          onClick={handleToggle}
          className="flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground transition-colors"
        >
          {fetching ? (
            <Loader2 className="h-3 w-3 animate-spin" />
          ) : expanded ? (
            <ChevronUp className="h-3 w-3" />
          ) : (
            <ChevronDown className="h-3 w-3" />
          )}
          {expanded ? "Hide details" : "Show details"}
        </button>

        {/* Expanded content */}
        {expanded && (
          <div className="space-y-3 pt-1">
            {/* Breakdown rings */}
            {hasBreakdown && <ReadinessBreakdown breakdown={data.breakdown} />}

            {/* Overall readiness bar */}
            {hasBreakdown && (
              <div className="space-y-1.5 pt-2">
                <div className="flex items-center justify-between text-xs">
                  <span className="font-medium text-muted-foreground">
                    Overall Readiness
                  </span>
                  <span className="font-bold tabular-nums">{pct}%</span>
                </div>
                <div className="h-2 rounded-full bg-muted overflow-hidden">
                  <div
                    className="h-full rounded-full bg-primary transition-all duration-1000"
                    style={{ width: `${pct}%` }}
                  />
                </div>
              </div>
            )}

            {/* Weak concepts */}
            {data.weak_concepts && data.weak_concepts.length > 0 && (
              <div className="space-y-1.5">
                <p className="text-xs font-medium text-muted-foreground uppercase tracking-wide">
                  Weak Areas
                </p>
                <div className="flex flex-wrap gap-1">
                  {data.weak_concepts.slice(0, 5).map((wc) => (
                    <Badge key={wc.concept_id} variant="outline" className="text-xs">
                      {wc.title}
                    </Badge>
                  ))}
                </div>
              </div>
            )}

            {/* Suggested actions */}
            {data.suggested_actions && data.suggested_actions.length > 0 && (
              <div className="space-y-1.5">
                <p className="text-xs font-medium text-muted-foreground uppercase tracking-wide">
                  Suggested Preparation
                </p>
                <div className="space-y-1">
                  {data.suggested_actions.map((action, i) => {
                    const courseId = action.target_course_id;
                    const routeSuffix = ACTION_ROUTES[action.action_type] ?? "";
                    const href = courseId
                      ? `/dashboard/courses/${courseId}${routeSuffix ? `/${routeSuffix}` : ""}`
                      : "/dashboard";
                    return (
                      <Link
                        key={i}
                        href={href}
                        className="flex items-center gap-1 text-xs text-primary hover:underline"
                      >
                        <span>{action.title}</span>
                        <span>&rarr;</span>
                      </Link>
                    );
                  })}
                </div>
              </div>
            )}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
