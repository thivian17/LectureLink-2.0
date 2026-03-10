"use client";

import { Badge } from "@/components/ui/badge";
import { MATERIAL_TYPE_LABELS, type MaterialType } from "@/types/database";

const TYPE_STYLES: Record<MaterialType, string> = {
  reading: "bg-blue-100 text-blue-800 dark:bg-blue-900/30 dark:text-blue-300",
  homework:
    "bg-amber-100 text-amber-800 dark:bg-amber-900/30 dark:text-amber-300",
  practice_exam:
    "bg-purple-100 text-purple-800 dark:bg-purple-900/30 dark:text-purple-300",
  assignment_outline:
    "bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-300",
  study_guide:
    "bg-teal-100 text-teal-800 dark:bg-teal-900/30 dark:text-teal-300",
  problem_set:
    "bg-orange-100 text-orange-800 dark:bg-orange-900/30 dark:text-orange-300",
  lab_manual:
    "bg-slate-100 text-slate-800 dark:bg-slate-900/30 dark:text-slate-300",
  other: "bg-gray-100 text-gray-800 dark:bg-gray-900/30 dark:text-gray-300",
};

interface MaterialTypeBadgeProps {
  type: MaterialType;
  className?: string;
}

export function MaterialTypeBadge({ type, className }: MaterialTypeBadgeProps) {
  return (
    <Badge
      variant="outline"
      className={`border-transparent ${TYPE_STYLES[type] ?? TYPE_STYLES.other} ${className ?? ""}`}
    >
      {MATERIAL_TYPE_LABELS[type] ?? type}
    </Badge>
  );
}
