"use client";

import { Flame, Zap, Clock, Brain } from "lucide-react";
import { Skeleton } from "@/components/ui/skeleton";
import type { DashboardStats } from "@/types/database";

interface StatsRowProps {
  stats: DashboardStats | null;
  loading: boolean;
}

export function StatsRow({ stats, loading }: StatsRowProps) {
  if (loading) {
    return (
      <div className="flex flex-wrap items-center gap-3">
        {Array.from({ length: 4 }).map((_, i) => (
          <div key={i} className="flex items-center gap-1.5">
            <Skeleton className="h-3.5 w-3.5 rounded" />
            <Skeleton className="h-4 w-6" />
            <Skeleton className="h-3 w-12" />
          </div>
        ))}
      </div>
    );
  }

  if (!stats) return null;

  const items = [
    {
      icon: Flame,
      value: stats.streak,
      label: "day streak",
      highlight: stats.streak > 0,
    },
    {
      icon: Zap,
      value: stats.xp_this_week,
      label: "XP this week",
      highlight: false,
    },
    {
      icon: Clock,
      value: stats.study_minutes_this_week,
      label: "min studied",
      highlight: false,
    },
    {
      icon: Brain,
      value: stats.concepts_practiced_this_week,
      label: "concepts",
      highlight: false,
    },
  ];

  return (
    <div className="flex flex-wrap items-center gap-3">
      {items.map((item) => (
        <div key={item.label} className="flex items-center gap-1.5">
          <item.icon
            className={`h-3.5 w-3.5 shrink-0 ${
              item.highlight ? "text-orange-500" : "text-muted-foreground"
            }`}
          />
          <span className="text-sm font-semibold tabular-nums">
            {item.value}
          </span>
          <span className="text-xs text-muted-foreground">{item.label}</span>
        </div>
      ))}
    </div>
  );
}
