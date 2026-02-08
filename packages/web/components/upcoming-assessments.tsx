"use client";

import { useMemo } from "react";
import { format, differenceInCalendarDays } from "date-fns";
import { Clock } from "lucide-react";

import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import type { CalendarAssessment } from "@/components/assessment-calendar";
import { getTypeColors, parseLocalDate } from "@/components/assessment-calendar";

interface UpcomingAssessmentsProps {
  assessments: CalendarAssessment[];
  /** Number of days to look ahead (default 7). */
  days?: number;
}

export function UpcomingAssessments({
  assessments,
  days = 7,
}: UpcomingAssessmentsProps) {
  const upcoming = useMemo(() => {
    const today = new Date();
    today.setHours(0, 0, 0, 0);

    return assessments
      .filter((a) => {
        if (!a.due_date) return false;
        const d = parseLocalDate(a.due_date);
        const diff = differenceInCalendarDays(d, today);
        return diff >= 0 && diff <= days;
      })
      .sort((a, b) => a.due_date!.localeCompare(b.due_date!));
  }, [assessments, days]);

  if (upcoming.length === 0) {
    return (
      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-base flex items-center gap-2">
            <Clock className="h-4 w-4" />
            Next {days} Days
          </CardTitle>
          <CardDescription>No upcoming assessments.</CardDescription>
        </CardHeader>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader className="pb-3">
        <CardTitle className="text-base flex items-center gap-2">
          <Clock className="h-4 w-4" />
          Next {days} Days
        </CardTitle>
        <CardDescription>
          {upcoming.length} assessment{upcoming.length !== 1 ? "s" : ""} coming up
        </CardDescription>
      </CardHeader>
      <CardContent>
        <div className="space-y-2">
          {upcoming.map((a) => {
            const colors = getTypeColors(a.type);
            const dueDate = parseLocalDate(a.due_date!);
            const daysUntil = differenceInCalendarDays(dueDate, new Date());
            const courseLabel = a.course_code ?? a.course_name;

            return (
              <div
                key={a.id}
                className="flex items-center gap-3 text-sm"
              >
                <span
                  className={`h-2.5 w-2.5 rounded-full shrink-0 ${colors.dot}`}
                />
                <div className="flex-1 min-w-0">
                  <span className="font-medium truncate">{a.title}</span>
                  <span className="text-muted-foreground">
                    {" "}({courseLabel})
                  </span>
                </div>
                <div className="text-right text-muted-foreground text-xs shrink-0">
                  <p>{format(dueDate, "MMM d")}</p>
                  {a.weight_percent != null && <p>{a.weight_percent}%</p>}
                  {daysUntil === 0 && (
                    <p className="text-amber-600 font-medium">Today</p>
                  )}
                  {daysUntil === 1 && (
                    <p className="text-amber-600 font-medium">Tomorrow</p>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      </CardContent>
    </Card>
  );
}
