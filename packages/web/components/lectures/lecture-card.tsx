"use client";

import React from "react";
import Link from "next/link";
import { format } from "date-fns";
import { Clock } from "lucide-react";

import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { StatusBadge } from "@/components/lectures/status-badge";
import { formatDuration } from "@/lib/format";
import type { Lecture } from "@/types/database";

function parseLocalDate(dateStr: string): Date {
  const [year, month, day] = dateStr.split("-").map(Number);
  return new Date(year, month - 1, day);
}

interface LectureCardProps {
  lecture: Lecture;
  courseId: string;
}

export const LectureCard = React.memo(function LectureCard({ lecture, courseId }: LectureCardProps) {
  return (
    <Link href={`/dashboard/courses/${courseId}/lectures/${lecture.id}`}>
      <Card className="h-full transition-colors hover:bg-accent/50">
        <CardHeader className="pb-3">
          <div className="flex items-start justify-between gap-2">
            <div className="min-w-0 flex-1">
              <CardTitle className="text-base leading-tight truncate">
                {lecture.title}
              </CardTitle>
              {lecture.lecture_date && (
                <CardDescription className="mt-1">
                  {format(parseLocalDate(lecture.lecture_date), "MMM d, yyyy")}
                </CardDescription>
              )}
            </div>
            {lecture.lecture_number != null && (
              <Badge variant="secondary" className="shrink-0 text-xs">
                Lec #{lecture.lecture_number}
              </Badge>
            )}
          </div>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="flex items-center gap-2">
            <StatusBadge status={lecture.processing_status} />
            {lecture.processing_status === "completed" &&
              lecture.duration_seconds != null && (
                <span className="flex items-center gap-1 text-xs text-muted-foreground">
                  <Clock className="h-3 w-3" />
                  {formatDuration(lecture.duration_seconds)}
                </span>
              )}
          </div>
          {lecture.processing_status === "completed" && lecture.summary && (
            <p className="text-sm text-muted-foreground line-clamp-2">
              {lecture.summary.length > 100
                ? lecture.summary.slice(0, 100) + "..."
                : lecture.summary}
            </p>
          )}
        </CardContent>
      </Card>
    </Link>
  );
});
