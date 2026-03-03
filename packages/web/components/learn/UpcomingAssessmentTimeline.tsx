"use client";

import { format, parseISO } from "date-fns";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";
import type { GamificationReadiness } from "@/types/database";

interface UpcomingAssessmentTimelineProps {
  assessments: GamificationReadiness[];
  loading?: boolean;
}

const URGENCY_BADGE: Record<string, string> = {
  danger: "bg-red-100 text-red-700 border-red-200",
  building: "bg-amber-100 text-amber-700 border-amber-200",
  strong: "bg-blue-100 text-blue-700 border-blue-200",
  ready: "bg-green-100 text-green-700 border-green-200",
};

const URGENCY_PROGRESS: Record<string, string> = {
  danger: "[&>div]:bg-red-500",
  building: "[&>div]:bg-amber-500",
  strong: "[&>div]:bg-blue-500",
  ready: "[&>div]:bg-green-500",
};

export function UpcomingAssessmentTimeline({ assessments, loading }: UpcomingAssessmentTimelineProps) {
  if (loading) {
    return (
      <div className="flex gap-3 overflow-x-auto pb-1">
        {[1, 2, 3].map((i) => (
          <Skeleton key={i} className="h-28 w-52 shrink-0 rounded-xl" />
        ))}
      </div>
    );
  }

  if (assessments.length === 0) return null;

  return (
    <div className="flex gap-3 overflow-x-auto pb-1 -mx-1 px-1">
      {assessments.map((a) => (
        <Card key={a.assessment_id} className="w-52 shrink-0">
          <CardContent className="p-3 space-y-2">
            <p className="text-sm font-medium truncate">{a.title}</p>
            <div className="flex items-center gap-2 text-xs text-muted-foreground">
              {a.due_date && (
                <span>{format(parseISO(a.due_date), "MMM d")}</span>
              )}
              {a.weight_percent != null && (
                <Badge variant="outline" className={cn("text-[10px] py-0", URGENCY_BADGE[a.urgency])}>
                  {a.weight_percent}%
                </Badge>
              )}
            </div>
            <div className="flex items-center gap-2">
              <Progress
                value={a.readiness_score}
                className={cn("h-2 flex-1", URGENCY_PROGRESS[a.urgency])}
              />
              <span className="text-xs font-semibold tabular-nums">
                {Math.round(a.readiness_score)}%
              </span>
            </div>
            {a.days_until_due != null && (
              <p className="text-[10px] text-muted-foreground">
                {a.days_until_due} day{a.days_until_due !== 1 ? "s" : ""} left
              </p>
            )}
          </CardContent>
        </Card>
      ))}
    </div>
  );
}
