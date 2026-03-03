"use client";

import { TrendingUp } from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";
import type { GradeProjection as GradeProjectionType } from "@/types/database";

interface GradeProjectionProps {
  projection: GradeProjectionType | null;
  loading?: boolean;
}

function gradeColor(letter: string): string {
  if (letter.startsWith("A")) return "text-green-700 bg-green-50 border-green-200";
  if (letter.startsWith("B")) return "text-blue-700 bg-blue-50 border-blue-200";
  if (letter.startsWith("C")) return "text-amber-700 bg-amber-50 border-amber-200";
  return "text-red-700 bg-red-50 border-red-200";
}

export function GradeProjection({ projection, loading }: GradeProjectionProps) {
  if (loading) {
    return <Skeleton className="h-20 w-full rounded-xl" />;
  }

  if (!projection) return null;

  const rangeStr = projection.projected_grade_low === projection.projected_grade_high
    ? `${Math.round(projection.projected_grade_high)}%`
    : `${Math.round(projection.projected_grade_low)}% – ${Math.round(projection.projected_grade_high)}%`;

  return (
    <Card>
      <CardContent className="p-4 flex items-center gap-4">
        <div
          className={cn(
            "flex items-center justify-center h-14 w-14 rounded-xl border text-xl font-bold shrink-0",
            gradeColor(projection.grade_letter),
          )}
        >
          {projection.grade_letter}
        </div>
        <div>
          <p className="text-sm font-medium flex items-center gap-1.5">
            <TrendingUp className="h-4 w-4 text-muted-foreground" />
            Grade Projection
          </p>
          <p className="text-xs text-muted-foreground">
            Current trajectory: {rangeStr}
          </p>
        </div>
      </CardContent>
    </Card>
  );
}
