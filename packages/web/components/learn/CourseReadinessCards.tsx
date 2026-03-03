"use client";

import Link from "next/link";
import { Card, CardContent } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";
import type { CourseReadinessSummary } from "@/types/database";

interface CourseReadinessCardsProps {
  courses: CourseReadinessSummary[];
  loading?: boolean;
}

function readinessColor(pct: number): string {
  if (pct >= 80) return "[&>div]:bg-green-500";
  if (pct >= 60) return "[&>div]:bg-blue-500";
  if (pct >= 30) return "[&>div]:bg-amber-500";
  return "[&>div]:bg-red-500";
}

function readinessTextColor(pct: number): string {
  if (pct >= 80) return "text-green-700";
  if (pct >= 60) return "text-blue-700";
  if (pct >= 30) return "text-amber-700";
  return "text-red-700";
}

export function CourseReadinessCards({ courses, loading }: CourseReadinessCardsProps) {
  if (loading) {
    return (
      <div className="flex gap-3 overflow-x-auto pb-1">
        {[1, 2, 3].map((i) => (
          <Skeleton key={i} className="h-24 w-44 shrink-0 rounded-xl" />
        ))}
      </div>
    );
  }

  if (courses.length === 0) return null;

  return (
    <div className="flex gap-3 overflow-x-auto pb-1 -mx-1 px-1">
      {courses.map((course) => {
        const pct = Math.round(course.overall_readiness);
        return (
          <Link
            key={course.course_id}
            href={`/dashboard/courses/${course.course_id}/readiness`}
          >
            <Card className="w-44 shrink-0 hover:border-primary/50 transition-colors cursor-pointer">
              <CardContent className="p-3 space-y-2">
                <p className="text-sm font-medium truncate">{course.course_name}</p>
                <div className="flex items-center gap-2">
                  <Progress
                    value={pct}
                    className={cn("h-2 flex-1", readinessColor(pct))}
                  />
                  <span className={cn("text-sm font-semibold tabular-nums", readinessTextColor(pct))}>
                    {pct}%
                  </span>
                </div>
                <p className="text-[10px] text-muted-foreground">
                  {course.concepts_mastered}/{course.concepts_total} concepts
                </p>
              </CardContent>
            </Card>
          </Link>
        );
      })}
    </div>
  );
}
