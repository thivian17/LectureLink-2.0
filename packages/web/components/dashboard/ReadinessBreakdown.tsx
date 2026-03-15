"use client";

import { BookOpen, Target, RefreshCw, TrendingUp } from "lucide-react";
import { Progress } from "@/components/ui/progress";
import { cn } from "@/lib/utils";
import type { ReadinessBreakdownV2 } from "@/types/database";

interface ReadinessBreakdownProps {
  breakdown: ReadinessBreakdownV2;
}

const signals = [
  { key: "coverage" as const, icon: BookOpen, label: "Coverage" },
  { key: "practice" as const, icon: Target, label: "Practice" },
  { key: "freshness" as const, icon: RefreshCw, label: "Freshness" },
  { key: "effort" as const, icon: TrendingUp, label: "Study Effort" },
] as const;

function barColor(value: number): string {
  if (value < 0.4) return "[&>div]:bg-red-500";
  if (value < 0.7) return "[&>div]:bg-amber-500";
  return "[&>div]:bg-green-500";
}

export function ReadinessBreakdown({ breakdown }: ReadinessBreakdownProps) {
  return (
    <div className="space-y-2">
      {signals.map(({ key, icon: Icon, label }) => {
        const value = breakdown[key];
        const pct = Math.round(value * 100);
        return (
          <div key={key} className="flex items-center gap-2">
            <Icon className="h-3.5 w-3.5 text-muted-foreground shrink-0" />
            <span className="text-xs w-16 shrink-0">{label}</span>
            <Progress
              value={pct}
              className={cn("h-2 flex-1", barColor(value))}
            />
            <span className="text-xs tabular-nums w-8 text-right text-muted-foreground">
              {pct}%
            </span>
          </div>
        );
      })}
    </div>
  );
}
