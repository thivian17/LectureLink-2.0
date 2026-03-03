"use client";

import { Flame, Snowflake } from "lucide-react";
import { cn } from "@/lib/utils";
import { Skeleton } from "@/components/ui/skeleton";
import type { StreakInfo } from "@/types/database";

interface StreakDisplayProps {
  streak: StreakInfo | null;
  loading?: boolean;
}

export function StreakDisplay({ streak, loading }: StreakDisplayProps) {
  if (loading || !streak) {
    return <Skeleton className="h-10 w-24 rounded-full" />;
  }

  return (
    <div
      className={cn(
        "flex items-center gap-1.5 rounded-full px-3 py-1.5 text-sm font-semibold transition-colors",
        streak.studied_today
          ? "bg-orange-100 text-orange-700"
          : "bg-muted text-muted-foreground",
      )}
    >
      <Flame
        className={cn(
          "h-5 w-5",
          streak.studied_today ? "text-orange-500" : "text-gray-400",
        )}
      />
      <span>{streak.current_streak}</span>
      {streak.freeze_available && !streak.studied_today && (
        <Snowflake className="h-3.5 w-3.5 text-blue-400 ml-0.5" />
      )}
    </div>
  );
}
