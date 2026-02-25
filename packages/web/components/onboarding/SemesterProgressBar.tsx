"use client";

import { Progress } from "@/components/ui/progress";

interface SemesterProgressBarProps {
  progressPct: number;
}

export function SemesterProgressBar({ progressPct }: SemesterProgressBarProps) {
  return (
    <div className="flex items-center gap-3">
      <span className="text-sm font-medium whitespace-nowrap">
        Semester Progress
      </span>
      <Progress value={progressPct} className="h-2 flex-1" />
      <span className="text-sm font-medium tabular-nums">
        {Math.round(progressPct)}%
      </span>
    </div>
  );
}
