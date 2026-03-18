"use client";

import { BookOpen } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { Badge } from "@/components/ui/badge";
import type { LectureMastery } from "@/lib/api";

interface LectureMasteryGridProps {
  lectures: LectureMastery[];
  onStudyLecture?: (lectureId: string) => void;
}

export function LectureMasteryGrid({
  lectures,
  onStudyLecture,
}: LectureMasteryGridProps) {
  if (!lectures.length) return null;

  return (
    <div className="space-y-3">
      <h3 className="text-sm font-medium flex items-center gap-1.5">
        <BookOpen className="h-4 w-4 text-muted-foreground" />
        Lecture Mastery
      </h3>
      <div className="grid gap-2">
        {lectures.map((lec) => {
          const pct = Math.round(lec.avg_mastery * 100);
          return (
            <button
              key={lec.lecture_id}
              type="button"
              className="w-full text-left rounded-lg border p-3 text-sm transition-colors hover:bg-muted/50"
              onClick={() => onStudyLecture?.(lec.lecture_id)}
            >
              <div className="flex items-center justify-between mb-1.5">
                <span className="font-medium truncate flex-1 mr-2">
                  {lec.title}
                </span>
                <span className="text-xs text-muted-foreground shrink-0">
                  {pct}%
                </span>
              </div>
              <Progress value={pct} className="h-1.5 mb-1.5" />
              <div className="flex gap-2 text-xs text-muted-foreground">
                <span>{lec.concept_count} concepts</span>
                {lec.unstarted > 0 && (
                  <Badge variant="secondary" className="text-xs px-1.5 py-0">
                    {lec.unstarted} new
                  </Badge>
                )}
              </div>
            </button>
          );
        })}
      </div>
    </div>
  );
}
