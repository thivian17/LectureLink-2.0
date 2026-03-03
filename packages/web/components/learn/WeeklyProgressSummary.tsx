"use client";

import { TrendingUp } from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import type { WeeklyProgress } from "@/types/database";

interface WeeklyProgressSummaryProps {
  progress: WeeklyProgress | null;
  loading?: boolean;
}

export function WeeklyProgressSummary({ progress, loading }: WeeklyProgressSummaryProps) {
  if (loading) {
    return <Skeleton className="h-24 w-full rounded-xl" />;
  }

  if (!progress) return null;

  const maxXp = Math.max(...progress.xp_by_day.map((d) => d.xp), 1);

  return (
    <Card>
      <CardContent className="p-4 space-y-3">
        <div className="flex items-center gap-2 text-sm">
          <TrendingUp className="h-4 w-4 text-emerald-500" />
          <span className="font-medium">This Week</span>
        </div>
        <div className="flex items-center gap-4 text-xs text-muted-foreground">
          <span>{progress.sessions_count} session{progress.sessions_count !== 1 ? "s" : ""}</span>
          <span>{progress.concepts_improved} concept{progress.concepts_improved !== 1 ? "s" : ""} improved</span>
          <span className="font-medium text-foreground">+{progress.total_xp} XP</span>
        </div>
        <div className="flex items-end gap-1 h-10">
          {progress.xp_by_day.map((day) => {
            const height = maxXp > 0 ? Math.max((day.xp / maxXp) * 100, 4) : 4;
            return (
              <div key={day.date} className="flex-1 flex flex-col items-center gap-0.5">
                <div
                  className="w-full rounded-sm bg-primary/80 transition-all duration-300"
                  style={{ height: `${height}%` }}
                />
              </div>
            );
          })}
        </div>
        <div className="flex justify-between text-[10px] text-muted-foreground">
          {progress.xp_by_day.map((day) => (
            <span key={day.date} className="flex-1 text-center">
              {new Date(day.date).toLocaleDateString("en", { weekday: "narrow" })}
            </span>
          ))}
        </div>
      </CardContent>
    </Card>
  );
}
