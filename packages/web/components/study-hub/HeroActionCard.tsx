"use client";

import Link from "next/link";
import {
  UploadCloud,
  FileCheck,
  BookOpen,
  AlertTriangle,
  Brain,
} from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { cn } from "@/lib/utils";
import type { StudyAction } from "@/types/database";

const ACTION_CONFIG: Record<
  string,
  { icon: typeof UploadCloud; borderColor: string; iconColor: string }
> = {
  upload_syllabus: {
    icon: UploadCloud,
    borderColor: "border-l-amber-500",
    iconColor: "text-amber-600 bg-amber-50",
  },
  review_syllabus: {
    icon: FileCheck,
    borderColor: "border-l-amber-500",
    iconColor: "text-amber-600 bg-amber-50",
  },
  upload_lectures: {
    icon: BookOpen,
    borderColor: "border-l-blue-500",
    iconColor: "text-blue-600 bg-blue-50",
  },
  assessment_prep: {
    icon: AlertTriangle,
    borderColor: "border-l-red-500",
    iconColor: "text-red-600 bg-red-50",
  },
  take_quiz: {
    icon: Brain,
    borderColor: "border-l-green-500",
    iconColor: "text-green-600 bg-green-50",
  },
  study_weak_concept: {
    icon: Brain,
    borderColor: "border-l-green-500",
    iconColor: "text-green-600 bg-green-50",
  },
};

const DEFAULT_CONFIG = {
  icon: BookOpen,
  borderColor: "border-l-gray-400",
  iconColor: "text-gray-600 bg-gray-50",
};

interface HeroActionCardProps {
  action: StudyAction;
}

export function HeroActionCard({ action }: HeroActionCardProps) {
  const config = ACTION_CONFIG[action.action_type] ?? DEFAULT_CONFIG;
  const Icon = config.icon;

  return (
    <Card className={cn("border-l-4", config.borderColor)}>
      <CardContent className="flex items-start gap-4 py-5">
        <div
          className={cn(
            "flex h-10 w-10 shrink-0 items-center justify-center rounded-lg",
            config.iconColor,
          )}
        >
          <Icon className="h-5 w-5" />
        </div>
        <div className="flex-1 min-w-0">
          <p className="font-semibold text-base">{action.title}</p>
          <p className="text-sm text-muted-foreground mt-1">
            {action.description}
          </p>
        </div>
        <Button asChild className="shrink-0">
          <Link href={action.cta_url}>{action.cta_label}</Link>
        </Button>
      </CardContent>
    </Card>
  );
}
