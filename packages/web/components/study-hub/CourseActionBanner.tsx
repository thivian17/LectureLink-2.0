"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import {
  UploadCloud,
  FileCheck,
  BookOpen,
  AlertTriangle,
  Brain,
  X,
} from "lucide-react";

import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { getCourseStudyActions, AuthError } from "@/lib/api";
import type { StudyAction } from "@/types/database";

const ICON_MAP: Record<string, typeof UploadCloud> = {
  upload_syllabus: UploadCloud,
  review_syllabus: FileCheck,
  upload_lectures: BookOpen,
  assessment_prep: AlertTriangle,
  take_quiz: Brain,
  study_weak_concept: Brain,
};

const BG_MAP: Record<string, string> = {
  upload_syllabus: "bg-amber-50 border-amber-200",
  review_syllabus: "bg-amber-50 border-amber-200",
  upload_lectures: "bg-blue-50 border-blue-200",
  assessment_prep: "bg-red-50 border-red-200",
  take_quiz: "bg-green-50 border-green-200",
  study_weak_concept: "bg-green-50 border-green-200",
};

const ICON_COLOR_MAP: Record<string, string> = {
  upload_syllabus: "text-amber-600",
  review_syllabus: "text-amber-600",
  upload_lectures: "text-blue-600",
  assessment_prep: "text-red-600",
  take_quiz: "text-green-600",
  study_weak_concept: "text-green-600",
};

interface CourseActionBannerProps {
  courseId: string;
}

export function CourseActionBanner({ courseId }: CourseActionBannerProps) {
  const [action, setAction] = useState<StudyAction | null>(null);
  const [loading, setLoading] = useState(true);
  const [dismissed, setDismissed] = useState(false);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        const data = await getCourseStudyActions(courseId);
        if (!cancelled && data.actions.length > 0) {
          setAction(data.actions[0]);
        }
      } catch (err) {
        if (err instanceof AuthError) return;
        console.error("[StudyHub] Failed to load course actions:", err);
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    load();
    return () => {
      cancelled = true;
    };
  }, [courseId]);

  if (loading || !action || dismissed) return null;

  const Icon = ICON_MAP[action.action_type] ?? BookOpen;
  const bgClass = BG_MAP[action.action_type] ?? "bg-primary/5 border-primary/20";
  const iconColor = ICON_COLOR_MAP[action.action_type] ?? "text-primary";

  return (
    <div className={cn("flex items-start gap-3 rounded-lg border p-3", bgClass)}>
      <Icon className={cn("h-4 w-4 shrink-0 mt-0.5", iconColor)} />
      <div className="flex-1 min-w-0">
        <p className="text-sm font-medium">{action.title}</p>
        <p className="text-xs text-muted-foreground mt-0.5">
          {action.description}
        </p>
      </div>
      <Button asChild size="sm" variant="outline" className="shrink-0">
        <Link href={action.cta_url}>{action.cta_label}</Link>
      </Button>
      <Button
        variant="ghost"
        size="icon"
        className="h-6 w-6 shrink-0"
        onClick={() => setDismissed(true)}
      >
        <X className="h-3 w-3" />
      </Button>
    </div>
  );
}
