"use client";

import Link from "next/link";
import { ArrowRight } from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import { cn } from "@/lib/utils";
import type { CourseIntelligenceV2 } from "@/types/database";

const RISK_BADGE: Record<string, { className: string; label: string }> = {
  high: {
    className: "bg-red-100 text-red-700 border-red-200",
    label: "High Risk",
  },
  medium: {
    className: "bg-amber-100 text-amber-700 border-amber-200",
    label: "Medium Risk",
  },
  low: {
    className: "bg-green-100 text-green-700 border-green-200",
    label: "On Track",
  },
};

function readinessColor(pct: number): string {
  if (pct >= 80) return "text-green-600";
  if (pct >= 60) return "text-amber-500";
  return "text-red-500";
}

function progressColor(pct: number): string {
  if (pct >= 80) return "[&>div]:bg-green-500";
  if (pct >= 60) return "[&>div]:bg-amber-500";
  return "[&>div]:bg-red-500";
}

interface CourseIntelligenceCardProps {
  course: CourseIntelligenceV2;
}

export function CourseIntelligenceCard({ course }: CourseIntelligenceCardProps) {
  const pct = Math.round(course.readiness * 100);
  const risk = RISK_BADGE[course.risk] ?? RISK_BADGE.low;
  const next = course.next_assessment;
  const action = course.recommended_action;

  return (
    <Link href={`/dashboard/courses/${course.course_id}`}>
      <Card className="hover:border-primary/50 hover:shadow-sm transition-all cursor-pointer h-full">
        <CardContent className="pt-5 pb-5 space-y-3">
          {/* Title + risk badge */}
          <div className="flex items-start justify-between gap-2">
            <p className="font-medium text-sm leading-tight truncate">
              {course.course_name}
            </p>
            <Badge variant="outline" className={cn("text-xs shrink-0", risk.className)}>
              {risk.label}
            </Badge>
          </div>

          {/* Readiness number + progress bar */}
          <div className="space-y-1.5">
            <div className="flex items-baseline gap-1">
              <span className={cn("text-2xl font-bold tabular-nums", readinessColor(pct))}>
                {pct}
              </span>
              <span className="text-xs text-muted-foreground">% ready</span>
            </div>
            <Progress value={pct} className={cn("h-2", progressColor(pct))} />
          </div>

          {/* Next assessment */}
          {next ? (
            <div className="flex items-center gap-2 text-sm">
              <span className="truncate flex-1">{next.title}</span>
              {next.days_until != null && (
                <Badge variant="secondary" className="text-xs shrink-0">
                  {next.days_until}d
                </Badge>
              )}
              <Badge variant="outline" className="text-xs shrink-0">
                {next.type}
              </Badge>
            </div>
          ) : (
            <p className="text-xs text-muted-foreground">No upcoming exams</p>
          )}

          {/* Recommended action */}
          {action && (
            <div className="flex items-center gap-1 text-xs text-primary">
              <span className="truncate">{action.title}</span>
              <ArrowRight className="h-3 w-3 shrink-0" />
            </div>
          )}
        </CardContent>
      </Card>
    </Link>
  );
}
