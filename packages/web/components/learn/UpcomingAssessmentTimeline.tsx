"use client";

import { format, parseISO } from "date-fns";
import { Card, CardContent } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";
import type { GamificationReadiness } from "@/types/database";

interface UpcomingAssessmentTimelineProps {
  assessments: GamificationReadiness[];
  loading?: boolean;
}

const TYPE_BADGE_COLORS: Record<string, string> = {
  exam: "bg-red-50 text-red-700",
  quiz: "bg-amber-50 text-amber-700",
  homework: "bg-blue-50 text-blue-700",
  project: "bg-purple-50 text-purple-700",
  lab: "bg-green-50 text-green-700",
  paper: "bg-teal-50 text-teal-700",
  presentation: "bg-indigo-50 text-indigo-700",
  participation: "bg-slate-50 text-slate-700",
  other: "bg-gray-50 text-gray-700",
};

function getTypeBadgeColor(type: string): string {
  return TYPE_BADGE_COLORS[type.toLowerCase()] ?? TYPE_BADGE_COLORS.other;
}

function urgencyTextColor(daysLeft: number | null): string {
  if (daysLeft == null) return "text-muted-foreground";
  if (daysLeft <= 2) return "text-red-600 font-semibold";
  if (daysLeft <= 5) return "text-amber-600 font-medium";
  return "text-muted-foreground";
}

const URGENCY_PROGRESS: Record<string, string> = {
  danger: "[&>div]:bg-red-500",
  building: "[&>div]:bg-amber-500",
  strong: "[&>div]:bg-blue-500",
  ready: "[&>div]:bg-green-500",
};

export function UpcomingAssessmentTimeline({ assessments, loading }: UpcomingAssessmentTimelineProps) {
  if (loading) {
    return (
      <div className="grid gap-3 sm:grid-cols-2">
        {[1, 2].map((i) => (
          <Skeleton key={i} className="h-28 w-full rounded-xl" />
        ))}
      </div>
    );
  }

  if (assessments.length === 0) return null;

  return (
    <div className="grid gap-3 sm:grid-cols-2">
      {assessments.map((a) => (
        <Card key={a.assessment_id} className="hover:border-primary/30 transition-colors">
          <CardContent className="pt-4 pb-4 space-y-2.5">
            {/* Title + type badge */}
            <div className="flex items-start justify-between gap-2">
              <p className="font-medium text-sm leading-tight">{a.title}</p>
              <span className={`text-xs font-medium px-1.5 py-0.5 rounded shrink-0 ${getTypeBadgeColor(a.type)}`}>
                {a.type}
              </span>
            </div>

            {/* Date + weight */}
            <div className="flex items-center gap-2 text-xs text-muted-foreground">
              {a.due_date && (
                <span>{format(parseISO(a.due_date), "MMM d")}</span>
              )}
              {a.weight_percent != null && (
                <span className="font-medium">
                  {a.weight_percent}% of grade
                </span>
              )}
            </div>

            {/* Readiness bar */}
            {a.readiness_score === 0 && a.concept_scores.every((c) => c.total_attempts === 0) ? (
              <p className="text-xs text-muted-foreground italic">Not Yet Started</p>
            ) : (
              <div className="flex items-center gap-2">
                <Progress
                  value={a.readiness_score}
                  className={cn("h-2 flex-1", URGENCY_PROGRESS[a.urgency])}
                />
                <span className="text-xs font-semibold tabular-nums">
                  {Math.round(a.readiness_score)}%
                </span>
              </div>
            )}

            {/* Days remaining with urgency coloring */}
            {a.days_until_due != null && (
              <p className={cn("text-xs tabular-nums", urgencyTextColor(a.days_until_due))}>
                {a.days_until_due === 0
                  ? "Due today"
                  : a.days_until_due === 1
                    ? "Due tomorrow"
                    : `${a.days_until_due} days left`}
              </p>
            )}
          </CardContent>
        </Card>
      ))}
    </div>
  );
}
