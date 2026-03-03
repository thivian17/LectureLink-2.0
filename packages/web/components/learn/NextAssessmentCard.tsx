"use client";

import { useState } from "react";
import { Calendar, TrendingUp, ChevronDown, ChevronUp } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";
import type { GamificationReadiness } from "@/types/database";

interface NextAssessmentCardProps {
  assessment: GamificationReadiness | null;
  loading?: boolean;
}

const URGENCY_STYLES: Record<string, { bg: string; text: string; progress: string; badge: string }> = {
  danger: { bg: "border-red-200", text: "text-red-700", progress: "[&>div]:bg-red-500", badge: "bg-red-100 text-red-700 border-red-200" },
  building: { bg: "border-amber-200", text: "text-amber-700", progress: "[&>div]:bg-amber-500", badge: "bg-amber-100 text-amber-700 border-amber-200" },
  strong: { bg: "border-blue-200", text: "text-blue-700", progress: "[&>div]:bg-blue-500", badge: "bg-blue-100 text-blue-700 border-blue-200" },
  ready: { bg: "border-green-200", text: "text-green-700", progress: "[&>div]:bg-green-500", badge: "bg-green-100 text-green-700 border-green-200" },
};

export function NextAssessmentCard({ assessment, loading }: NextAssessmentCardProps) {
  const [expanded, setExpanded] = useState(false);

  if (loading) {
    return (
      <Card>
        <CardHeader><Skeleton className="h-6 w-3/4" /></CardHeader>
        <CardContent className="space-y-3">
          <Skeleton className="h-4 w-1/2" />
          <Skeleton className="h-3 w-full" />
        </CardContent>
      </Card>
    );
  }

  if (!assessment) {
    return (
      <Card className="border-dashed">
        <CardContent className="py-8 text-center text-muted-foreground">
          No upcoming assessments — you&apos;re all caught up!
        </CardContent>
      </Card>
    );
  }

  const style = URGENCY_STYLES[assessment.urgency] ?? URGENCY_STYLES.building;
  const daysLabel = assessment.days_until_due != null
    ? `${assessment.days_until_due} day${assessment.days_until_due !== 1 ? "s" : ""}`
    : "No date";

  return (
    <Card className={cn("transition-colors", style.bg)}>
      <CardHeader className="pb-2">
        <div className="flex items-center justify-between">
          <CardTitle className="text-base">{assessment.title}</CardTitle>
          <Badge variant="outline" className={cn("text-xs", style.badge)}>
            {assessment.type}
          </Badge>
        </div>
        <div className="flex items-center gap-3 text-sm text-muted-foreground">
          <span className="flex items-center gap-1">
            <Calendar className="h-3.5 w-3.5" />
            {daysLabel}
          </span>
          {assessment.weight_percent != null && (
            <span>Worth {assessment.weight_percent}%</span>
          )}
        </div>
      </CardHeader>
      <CardContent className="space-y-2">
        <div className="flex items-center gap-2">
          <Progress value={assessment.readiness_score} className={cn("h-3 flex-1", style.progress)} />
          <span className={cn("text-sm font-semibold tabular-nums", style.text)}>
            {Math.round(assessment.readiness_score)}%
          </span>
        </div>
        {assessment.trend !== 0 && (
          <div className="flex items-center gap-1 text-xs text-emerald-600">
            <TrendingUp className="h-3 w-3" />
            <span>+{assessment.trend}% this week</span>
          </div>
        )}
        {assessment.concept_scores.length > 0 && (
          <button
            onClick={() => setExpanded(!expanded)}
            className="flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground transition-colors"
          >
            {expanded ? <ChevronUp className="h-3 w-3" /> : <ChevronDown className="h-3 w-3" />}
            {expanded ? "Hide" : "Show"} concept breakdown
          </button>
        )}
        {expanded && (
          <div className="space-y-1.5 pt-1">
            {assessment.concept_scores.map((c) => (
              <div key={c.concept_id} className="flex items-center gap-2 text-xs">
                <span className="flex-1 truncate">{c.title}</span>
                <Progress value={c.mastery * 100} className="h-1.5 w-16" />
                <span className="tabular-nums text-muted-foreground w-8 text-right">
                  {Math.round(c.mastery * 100)}%
                </span>
              </div>
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
