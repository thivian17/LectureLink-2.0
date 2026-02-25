"use client";

import { CalendarDays, Scale } from "lucide-react";
import { cn } from "@/lib/utils";
import { Badge } from "@/components/ui/badge";
import type { AssessmentChoice } from "@/types/database";

interface AssessmentSelectorProps {
  assessments: AssessmentChoice[];
  selected: string | null;
  onSelect: (id: string | null) => void;
}

function urgencyColor(daysRemaining: number): string {
  if (daysRemaining < 3) return "text-red-600 bg-red-50 border-red-200";
  if (daysRemaining < 7)
    return "text-yellow-600 bg-yellow-50 border-yellow-200";
  return "text-green-600 bg-green-50 border-green-200";
}

export function AssessmentSelector({
  assessments,
  selected,
  onSelect,
}: AssessmentSelectorProps) {
  if (assessments.length === 0) return null;

  return (
    <div className="space-y-2">
      <p className="text-sm font-medium">Prepare for an upcoming assessment</p>
      <div className="grid gap-2 sm:grid-cols-2">
        {assessments.map((a) => {
          const isSelected = selected === a.id;
          return (
            <button
              key={a.id}
              onClick={() => onSelect(isSelected ? null : a.id)}
              className={cn(
                "flex flex-col items-start gap-1.5 rounded-lg border p-3 text-left transition-all",
                isSelected
                  ? "border-primary bg-primary/5 ring-1 ring-primary"
                  : "border-border hover:border-muted-foreground/30",
              )}
            >
              <p className="text-sm font-medium leading-tight">{a.title}</p>
              <div className="flex flex-wrap items-center gap-2">
                <Badge
                  variant="outline"
                  className={cn("text-[10px]", urgencyColor(a.days_remaining))}
                >
                  <CalendarDays className="mr-1 h-3 w-3" />
                  {a.days_remaining === 0
                    ? "Today"
                    : a.days_remaining === 1
                      ? "Tomorrow"
                      : `${a.days_remaining} days`}
                </Badge>
                {a.weight_percent != null && (
                  <Badge variant="outline" className="text-[10px]">
                    <Scale className="mr-1 h-3 w-3" />
                    {a.weight_percent}%
                  </Badge>
                )}
              </div>
            </button>
          );
        })}
      </div>
    </div>
  );
}
