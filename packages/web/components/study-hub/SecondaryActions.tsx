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

const ICON_MAP: Record<string, typeof UploadCloud> = {
  upload_syllabus: UploadCloud,
  review_syllabus: FileCheck,
  upload_lectures: BookOpen,
  assessment_prep: AlertTriangle,
  take_quiz: Brain,
  study_weak_concept: Brain,
};

const COLOR_MAP: Record<string, string> = {
  upload_syllabus: "text-amber-600",
  review_syllabus: "text-amber-600",
  upload_lectures: "text-blue-600",
  assessment_prep: "text-red-600",
  take_quiz: "text-green-600",
  study_weak_concept: "text-green-600",
};

interface SecondaryActionsProps {
  actions: StudyAction[];
}

export function SecondaryActions({ actions }: SecondaryActionsProps) {
  if (actions.length === 0) return null;

  return (
    <div className="grid gap-4 sm:grid-cols-2">
      {actions.map((action, i) => {
        const Icon = ICON_MAP[action.action_type] ?? BookOpen;
        const iconColor = COLOR_MAP[action.action_type] ?? "text-gray-600";

        return (
          <Card key={i}>
            <CardContent className="flex items-start gap-3 py-4">
              <Icon className={cn("h-4 w-4 shrink-0 mt-0.5", iconColor)} />
              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium leading-tight">
                  {action.title}
                </p>
                <p className="text-xs text-muted-foreground mt-1 line-clamp-2">
                  {action.description}
                </p>
                <Button
                  asChild
                  variant="link"
                  size="sm"
                  className="h-auto p-0 mt-1.5 text-xs"
                >
                  <Link href={action.cta_url}>{action.cta_label} &rarr;</Link>
                </Button>
              </div>
            </CardContent>
          </Card>
        );
      })}
    </div>
  );
}
