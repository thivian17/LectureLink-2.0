"use client";

import { Award } from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import { cn } from "@/lib/utils";
import type { BadgeInfo } from "@/types/database";

interface BadgeCardProps {
  badge: BadgeInfo;
  earned: boolean;
  onClick?: () => void;
}

const CATEGORY_STYLES: Record<string, string> = {
  streak: "bg-orange-100 text-orange-700 border-orange-200",
  mastery: "bg-blue-100 text-blue-700 border-blue-200",
  assessment: "bg-purple-100 text-purple-700 border-purple-200",
  behavior: "bg-emerald-100 text-emerald-700 border-emerald-200",
  rare: "bg-amber-100 text-amber-700 border-amber-200",
};

export function BadgeCard({ badge, earned, onClick }: BadgeCardProps) {
  return (
    <Card
      className={cn(
        "cursor-pointer hover:shadow-sm transition-all",
        !earned && "opacity-60",
      )}
      onClick={onClick}
    >
      <CardContent className="p-4 space-y-2">
        <div className="flex items-start justify-between">
          <span className="text-2xl">{badge.icon || "🏆"}</span>
          <Badge
            variant="outline"
            className={cn("text-[10px] py-0", CATEGORY_STYLES[badge.category] ?? "")}
          >
            {badge.category}
          </Badge>
        </div>
        <div>
          <p className="text-sm font-medium">{badge.name}</p>
          <p className="text-xs text-muted-foreground line-clamp-2">{badge.description}</p>
        </div>
        {earned && badge.earned_at ? (
          <p className="text-[10px] text-muted-foreground flex items-center gap-1">
            <Award className="h-3 w-3" />
            Earned {new Date(badge.earned_at).toLocaleDateString("en", {
              month: "short",
              day: "numeric",
              year: "numeric",
            })}
          </p>
        ) : (
          badge.progress != null && (
            <div className="space-y-1">
              <Progress value={badge.progress} className="h-1.5" />
              <p className="text-[10px] text-muted-foreground text-right">{Math.round(badge.progress)}%</p>
            </div>
          )
        )}
      </CardContent>
    </Card>
  );
}
