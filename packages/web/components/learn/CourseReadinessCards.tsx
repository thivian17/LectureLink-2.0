"use client";

import Link from "next/link";
import { format, differenceInCalendarDays } from "date-fns";
import { Card, CardContent } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";
import type { Course, CourseReadinessSummary } from "@/types/database";

function parseLocalDate(dateStr: string): Date {
  const [y, m, d] = dateStr.split("T")[0].split("-").map(Number);
  return new Date(y, m - 1, d);
}

interface CourseReadinessCardsProps {
  courses: CourseReadinessSummary[];
  allCourses?: Course[];
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

export function CourseReadinessCards({ courses, allCourses, loading }: CourseReadinessCardsProps) {
  if (loading) {
    return (
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {[1, 2, 3].map((i) => (
          <Skeleton key={i} className="h-32 w-full rounded-xl" />
        ))}
      </div>
    );
  }

  if (courses.length === 0) return null;

  return (
    <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
      {courses.map((course) => {
        const pct = Math.round(course.overall_readiness);
        const full = allCourses?.find((c) => c.id === course.course_id);
        const courseCode = full?.code;

        // Semester progress
        let semesterPct = 0;
        let semesterLabel = "";
        if (full) {
          const start = parseLocalDate(full.semester_start);
          const end = parseLocalDate(full.semester_end);
          const totalDays = differenceInCalendarDays(end, start);
          const elapsed = differenceInCalendarDays(new Date(), start);
          semesterPct = totalDays > 0
            ? Math.max(0, Math.min(100, Math.round((elapsed / totalDays) * 100)))
            : 0;
          semesterLabel = `${format(start, "MMM d")} – ${format(end, "MMM d, yyyy")}`;
        }

        return (
          <Link
            key={course.course_id}
            href={`/dashboard/courses/${course.course_id}`}
          >
            <Card className="hover:border-primary/50 hover:shadow-sm transition-all cursor-pointer h-full">
              <CardContent className="pt-5 pb-5 space-y-3">
                {/* Title + code badge */}
                <div className="flex items-start justify-between gap-2">
                  <p className="font-semibold text-sm leading-tight">
                    {course.course_name}
                  </p>
                  {courseCode && (
                    <span className="text-xs font-medium px-2 py-0.5 rounded-full bg-primary/10 text-primary shrink-0">
                      {courseCode}
                    </span>
                  )}
                </div>

                {/* Readiness progress bar */}
                {pct === 0 && course.concepts_mastered === 0 && course.concepts_total > 0 ? (
                  <p className="text-xs text-muted-foreground italic">Not Yet Assessed</p>
                ) : (
                  <div className="space-y-1.5">
                    <div className="flex items-center gap-2">
                      <Progress
                        value={pct}
                        className={cn("h-2 flex-1", readinessColor(pct))}
                      />
                      <span className={cn("text-xs font-semibold tabular-nums", readinessTextColor(pct))}>
                        {pct}%
                      </span>
                    </div>
                    <p className="text-xs text-muted-foreground">
                      {course.concepts_mastered}/{course.concepts_total} concepts mastered
                    </p>
                  </div>
                )}

                {/* Semester dates */}
                {semesterLabel && (
                  <p className="text-xs text-muted-foreground">{semesterLabel}</p>
                )}
              </CardContent>
            </Card>
          </Link>
        );
      })}
    </div>
  );
}
