"use client";

import { useState } from "react";
import { ChevronDown, ChevronUp } from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import type { GamificationReadiness } from "@/types/database";

interface ReadinessDetailProps {
  assessment: GamificationReadiness;
}

const URGENCY_STYLES: Record<string, { progress: string; badge: string }> = {
  danger: { progress: "[&>div]:bg-red-500", badge: "bg-red-100 text-red-700 border-red-200" },
  building: { progress: "[&>div]:bg-amber-500", badge: "bg-amber-100 text-amber-700 border-amber-200" },
  strong: { progress: "[&>div]:bg-blue-500", badge: "bg-blue-100 text-blue-700 border-blue-200" },
  ready: { progress: "[&>div]:bg-green-500", badge: "bg-green-100 text-green-700 border-green-200" },
};

function masteryColor(mastery: number): string {
  if (mastery >= 0.8) return "[&>div]:bg-green-500";
  if (mastery >= 0.6) return "[&>div]:bg-blue-500";
  if (mastery >= 0.3) return "[&>div]:bg-amber-500";
  return "[&>div]:bg-red-500";
}

export function ReadinessDetail({ assessment }: ReadinessDetailProps) {
  const [expanded, setExpanded] = useState(false);
  const style = URGENCY_STYLES[assessment.urgency] ?? URGENCY_STYLES.building;

  return (
    <Card>
      <CardContent className="p-4 space-y-3">
        <div className="flex items-start justify-between">
          <div>
            <p className="text-sm font-medium">{assessment.title}</p>
            <div className="flex items-center gap-2 text-xs text-muted-foreground mt-0.5">
              {assessment.due_date && (
                <span>
                  {new Date(assessment.due_date).toLocaleDateString("en", {
                    month: "short",
                    day: "numeric",
                  })}
                </span>
              )}
              {assessment.weight_percent != null && (
                <span>· {assessment.weight_percent}% of grade</span>
              )}
            </div>
          </div>
          <Badge variant="outline" className={cn("text-xs", style.badge)}>
            {Math.round(assessment.readiness_score)}% ready
          </Badge>
        </div>

        <Progress
          value={assessment.readiness_score}
          className={cn("h-2.5", style.progress)}
        />

        <button
          onClick={() => setExpanded(!expanded)}
          className="flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground transition-colors"
        >
          {expanded ? <ChevronUp className="h-3 w-3" /> : <ChevronDown className="h-3 w-3" />}
          {assessment.concept_scores.length} concepts
        </button>

        {expanded && (
          <div className="space-y-2 pt-1">
            {assessment.concept_scores
              .sort((a, b) => a.mastery - b.mastery)
              .map((c) => (
                <div key={c.concept_id} className="flex items-center gap-2 text-xs">
                  <span className="flex-1 truncate">{c.title}</span>
                  <Progress
                    value={c.mastery * 100}
                    className={cn("h-1.5 w-20", masteryColor(c.mastery))}
                  />
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
