"use client";

import { useState } from "react";
import Link from "next/link";
import { ChevronDown, ChevronUp, Loader2 } from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { ReadinessBreakdown } from "./ReadinessBreakdown";
import { getAssessmentReadinessV2 } from "@/lib/api";
import type { AssessmentReadinessV2 } from "@/types/database";

interface AssessmentReadinessCardProps {
  assessment: AssessmentReadinessV2;
}

function getStudyHref(data: AssessmentReadinessV2): string {
  const base = `/dashboard/courses/${data.course_id}/learn`;
  if (data.weak_concepts && data.weak_concepts.length > 0) {
    const ids = data.weak_concepts.map((wc) => wc.concept_id).join(",");
    return `${base}?concepts=${ids}`;
  }
  return `${base}?assessmentId=${data.assessment_id}`;
}

function daysPillStyle(days: number | null): string {
  if (days == null) return "bg-muted text-muted-foreground";
  if (days <= 3) return "bg-red-50 text-red-600";
  if (days <= 7) return "bg-amber-50 text-amber-600";
  return "bg-muted text-muted-foreground";
}

function daysLabel(days: number | null): string {
  if (days == null) return "";
  if (days === 0) return "Due today";
  if (days === 1) return "1 day away";
  return `${days} days away`;
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
      <CardContent className="pt-5 pb-5">
        {/* Header — matches mockup: title + subtitle left, days pill right */}
        <div className="flex items-start justify-between gap-2 mb-2">
          <div className="min-w-0">
            <h3 className="text-base font-bold text-foreground truncate">
              {data.title}
            </h3>
            {data.course_name && (
              <p className="text-xs text-muted-foreground mt-0.5">
                {data.course_name}
              </p>
            )}
          </div>
          <div className="flex items-center gap-2 shrink-0">
            {data.days_until_due != null && (
              <span
                className={cn(
                  "text-xs font-semibold px-3 py-1 rounded-full",
                  daysPillStyle(data.days_until_due),
                )}
              >
                {daysLabel(data.days_until_due)}
              </span>
            )}
          </div>
        </div>

        {/* Expand toggle */}
        <button
          onClick={handleToggle}
          className="flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground transition-colors mb-1"
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

        {/* Expanded content — matches mockup layout */}
        {expanded && (
          <div className="space-y-3 pt-1">
            {/* Rings */}
            {hasBreakdown && (
              <ReadinessBreakdown breakdown={data.breakdown} />
            )}

            {/* Overall readiness bar — gradient fill matching mockup */}
            <div>
              <div className="flex items-center justify-between mb-1.5">
                <span className="text-xs font-semibold text-muted-foreground">
                  Overall Readiness
                </span>
                <span className="text-xs font-bold tabular-nums text-foreground">
                  {pct}%
                </span>
              </div>
              <div className="h-2 rounded-full bg-muted overflow-hidden">
                <div
                  className="h-full rounded-full transition-all duration-1000"
                  style={{
                    width: `${pct}%`,
                    background: "linear-gradient(90deg, #2563EB, #3B82F6)",
                  }}
                />
              </div>
            </div>

            {/* Weak areas — inline style matching mockup */}
            {data.weak_concepts && data.weak_concepts.length > 0 && (
              <div className="flex items-center gap-1.5 flex-wrap">
                <span className="text-[11px] font-medium text-muted-foreground">
                  Weak areas:
                </span>
                {data.weak_concepts.slice(0, 5).map((wc) => (
                  <span
                    key={wc.concept_id}
                    className="text-[11px] font-medium bg-muted text-muted-foreground px-2 py-0.5 rounded-md"
                  >
                    {wc.title}
                  </span>
                ))}
              </div>
            )}

            {/* Study button */}
            {data.course_id && (
              <div className="pt-1">
                <Button
                  asChild
                  size="sm"
                  className="text-xs"
                >
                  <Link href={getStudyHref(data)}>Start Studying</Link>
                </Button>
              </div>
            )}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
