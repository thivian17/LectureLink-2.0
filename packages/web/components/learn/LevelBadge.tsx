"use client";

import { Zap } from "lucide-react";
import { Progress } from "@/components/ui/progress";
import { Skeleton } from "@/components/ui/skeleton";
import type { LevelInfo } from "@/types/database";

interface LevelBadgeProps {
  level: LevelInfo | null;
  todayXp?: number;
  loading?: boolean;
}

export function LevelBadge({ level, todayXp = 0, loading }: LevelBadgeProps) {
  if (loading || !level) {
    return <Skeleton className="h-10 w-48 rounded-full" />;
  }

  return (
    <div className="flex items-center gap-2">
      <div className="flex items-center gap-1 rounded-full bg-primary/10 px-2.5 py-1 text-sm font-semibold text-primary">
        <span>Lv {level.current_level}</span>
      </div>
      <div className="flex flex-col gap-0.5 min-w-[120px]">
        <Progress value={level.progress_percent} className="h-2" />
        <div className="flex justify-between text-[10px] text-muted-foreground">
          <span>{level.total_xp} XP</span>
          <span>{level.xp_to_next_level} to next</span>
        </div>
      </div>
      {todayXp > 0 && (
        <span className="flex items-center gap-0.5 text-xs font-medium text-emerald-600">
          <Zap className="h-3 w-3" />+{todayXp}
        </span>
      )}
    </div>
  );
}
