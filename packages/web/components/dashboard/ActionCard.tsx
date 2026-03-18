"use client";

import Link from "next/link";
import { Clock } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import type { SuggestedAction } from "@/types/database";

const URGENCY_DOT: Record<string, string> = {
  critical: "bg-red-500",
  high: "bg-amber-500",
  medium: "bg-blue-500",
  low: "bg-green-500",
};

const ACTION_CTA: Record<string, { label: string; path: string }> = {
  study_session: { label: "Start", path: "learn" },
  practice_test: { label: "Practice", path: "" },
  lecture_review: { label: "Review", path: "" },
  flash_review: { label: "Refresh", path: "learn" },
};

function getActionHref(action: SuggestedAction): string {
  const courseId = action.target_course_id;
  if (!courseId) return "/dashboard";
  const config = ACTION_CTA[action.action_type];
  if (!config) return `/dashboard/courses/${courseId}`;
  if (!config.path) return `/dashboard/courses/${courseId}`;
  const base = `/dashboard/courses/${courseId}/${config.path}`;
  // Pass assessment targeting as search params so the learn session auto-focuses
  if (action.target_assessment_id && config.path === "learn") {
    return `${base}?assessmentId=${action.target_assessment_id}`;
  }
  return base;
}

interface ActionCardProps {
  action: SuggestedAction;
  courseNames?: Record<string, string>;
}

export function ActionCard({ action, courseNames }: ActionCardProps) {
  const dotColor = URGENCY_DOT[action.urgency] ?? URGENCY_DOT.low;
  const cta = ACTION_CTA[action.action_type] ?? { label: "Go", path: "" };
  const href = getActionHref(action);
  const courseName =
    action.target_course_id && courseNames
      ? courseNames[action.target_course_id]
      : null;

  return (
    <Card className="p-4">
      <div className="flex items-start gap-3">
        <div className="flex-1 min-w-0 space-y-1.5">
          <div className="flex items-center gap-2">
            <span className={`h-2 w-2 rounded-full shrink-0 ${dotColor}`} />
            <p className="text-sm font-medium truncate">{action.title}</p>
          </div>
          {courseName && (
            <Badge variant="outline" className="text-xs">
              {courseName}
            </Badge>
          )}
          <p className="text-xs text-muted-foreground line-clamp-2">
            {action.description}
          </p>
          <div className="flex items-center gap-3 text-xs text-muted-foreground">
            <span className="flex items-center gap-1">
              <Clock className="h-3 w-3" />~{action.estimated_minutes} min
            </span>
            {action.expected_impact && (
              <span className="font-medium text-primary">
                {action.expected_impact}
              </span>
            )}
          </div>
        </div>
        <Button asChild size="sm" variant="secondary" className="shrink-0">
          <Link href={href}>{cta.label}</Link>
        </Button>
      </div>
    </Card>
  );
}
