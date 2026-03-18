"use client";

import { Brain } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import type { PriorityConcept } from "@/lib/api";

interface PriorityConceptsWidgetProps {
  concepts: PriorityConcept[];
  onStudy?: (conceptIds: string[]) => void;
}

function masteryDot(score: number) {
  if (score >= 0.85)
    return "bg-green-500";
  if (score >= 0.6)
    return "bg-yellow-500";
  if (score >= 0.3)
    return "bg-orange-500";
  return "bg-red-500";
}

function formatDaysSince(days: number): string {
  if (days >= 999) return "never";
  if (days === 0) return "today";
  if (days === 1) return "yesterday";
  return `${days}d ago`;
}

export function PriorityConceptsWidget({
  concepts,
  onStudy,
}: PriorityConceptsWidgetProps) {
  if (!concepts.length) return null;

  const topConcepts = concepts.slice(0, 5);

  return (
    <Card>
      <CardHeader className="pb-3">
        <CardTitle className="text-base flex items-center gap-2">
          <Brain className="h-4 w-4" />
          Review These
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-2">
        {topConcepts.map((c) => (
          <div
            key={c.concept_id}
            className="flex items-center gap-2 text-sm"
          >
            <span
              className={cn("h-2 w-2 rounded-full shrink-0", masteryDot(c.mastery_score))}
            />
            <span className="flex-1 truncate">{c.concept_title}</span>
            <span className="text-xs text-muted-foreground shrink-0">
              {formatDaysSince(c.days_since_review)}
            </span>
          </div>
        ))}
        {onStudy && (
          <Button
            size="sm"
            className="w-full mt-2"
            onClick={() =>
              onStudy(topConcepts.map((c) => c.concept_id))
            }
          >
            Study
          </Button>
        )}
      </CardContent>
    </Card>
  );
}
