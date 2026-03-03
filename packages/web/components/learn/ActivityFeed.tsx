"use client";

import { Award, TrendingUp, BookOpen } from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import type { BadgeInfo } from "@/types/database";

interface ActivityFeedProps {
  recentBadges: BadgeInfo[];
  loading?: boolean;
}

export function ActivityFeed({ recentBadges, loading }: ActivityFeedProps) {
  if (loading) {
    return <Skeleton className="h-24 w-full rounded-xl" />;
  }

  if (recentBadges.length === 0) {
    return (
      <Card>
        <CardContent className="p-4 text-sm text-muted-foreground flex items-center gap-2">
          <BookOpen className="h-4 w-4" />
          Start a session to build your activity feed!
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardContent className="p-4 space-y-2">
        <div className="flex items-center gap-2 text-sm font-medium">
          <TrendingUp className="h-4 w-4 text-primary" />
          Recent Activity
        </div>
        <div className="space-y-1.5">
          {recentBadges.slice(0, 4).map((badge) => (
            <div
              key={badge.badge_id}
              className="flex items-center gap-2 text-xs"
            >
              <Award className="h-3.5 w-3.5 text-amber-500 shrink-0" />
              <span className="truncate">
                Earned <span className="font-medium">{badge.name}</span>
              </span>
              {badge.earned_at && (
                <span className="text-muted-foreground ml-auto shrink-0">
                  {new Date(badge.earned_at).toLocaleDateString("en", {
                    month: "short",
                    day: "numeric",
                  })}
                </span>
              )}
            </div>
          ))}
        </div>
      </CardContent>
    </Card>
  );
}
