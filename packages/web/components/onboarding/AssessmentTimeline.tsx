"use client";

import { format, parseISO } from "date-fns";

import { Badge } from "@/components/ui/badge";
import type { Assessment } from "@/types/database";

interface AssessmentTimelineProps {
  assessments: Assessment[];
}

function weightColor(weight: number | null): string {
  if (!weight) return "bg-muted text-muted-foreground";
  if (weight >= 25) return "bg-red-100 text-red-700 border-red-200";
  if (weight >= 10) return "bg-yellow-100 text-yellow-700 border-yellow-200";
  return "bg-muted text-muted-foreground";
}

export function AssessmentTimeline({ assessments }: AssessmentTimelineProps) {
  const items = assessments.filter((a) => a.due_date).slice(0, 5);

  if (items.length === 0) {
    return (
      <p className="text-sm text-muted-foreground">
        No upcoming deadlines found.
      </p>
    );
  }

  return (
    <div className="space-y-3">
      {items.map((a, i) => (
        <div key={a.id} className="flex items-center gap-3">
          {/* Timeline dot + connector */}
          <div className="flex flex-col items-center">
            <div className="h-3 w-3 rounded-full bg-primary" />
            {i < items.length - 1 && (
              <div className="w-px flex-1 bg-border min-h-[24px]" />
            )}
          </div>

          {/* Content */}
          <div className="flex flex-1 items-center justify-between min-w-0">
            <div className="min-w-0">
              <p className="text-sm font-medium truncate">{a.title}</p>
              <p className="text-xs text-muted-foreground">
                {a.due_date ? format(parseISO(a.due_date), "MMM d, yyyy") : ""}
              </p>
            </div>
            {a.weight_percent != null && (
              <Badge variant="outline" className={weightColor(a.weight_percent)}>
                {a.weight_percent}%
              </Badge>
            )}
          </div>
        </div>
      ))}
    </div>
  );
}
