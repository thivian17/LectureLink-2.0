"use client";

import { useState, useEffect } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";
import { getSuggestedPath, setOnboardingPath } from "@/lib/api";
import type { OnboardingPath } from "@/types/database";

interface PathSelectionStepProps {
  courseId: string;
  syllabusSkipped?: boolean;
  onComplete: (path: OnboardingPath) => void;
}

const PATH_OPTIONS: {
  value: OnboardingPath;
  icon: string;
  title: string;
  description: string;
}[] = [
  {
    value: "just_starting",
    icon: "\u{1F7E2}",
    title: "Just Starting",
    description:
      "The semester just began and I want to stay ahead from day one.",
  },
  {
    value: "mid_semester",
    icon: "\u{1F7E1}",
    title: "Mid-Semester",
    description:
      "I'm partway through the course and want to catch up or prepare for exams.",
  },
  {
    value: "course_complete",
    icon: "\u{1F535}",
    title: "Course Complete",
    description:
      "The semester is over and I want to review the material at my own pace.",
  },
];

const SUGGESTION_DESCRIPTIONS: Record<OnboardingPath, string> = {
  just_starting: "just getting started",
  mid_semester: "partway through the semester",
  course_complete: "done with this course",
};

export function PathSelectionStep({
  courseId,
  syllabusSkipped,
  onComplete,
}: PathSelectionStepProps) {
  const [selected, setSelected] = useState<OnboardingPath | null>(null);
  const [suggestion, setSuggestion] = useState<OnboardingPath | null>(null);
  const [loading, setLoading] = useState(!syllabusSkipped);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    if (syllabusSkipped) return;
    async function load() {
      try {
        const data = await getSuggestedPath(courseId);
        setSuggestion(data.suggested_path);
        setSelected(data.suggested_path);
      } catch {
        // No suggestion available — fine
      } finally {
        setLoading(false);
      }
    }
    load();
  }, [courseId, syllabusSkipped]);

  async function handleConfirm() {
    if (!selected) return;
    setSubmitting(true);
    try {
      await setOnboardingPath(courseId, selected);
      onComplete(selected);
    } catch {
      toast.error("Failed to set path");
    } finally {
      setSubmitting(false);
    }
  }

  if (loading) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-8 w-64" />
        <div className="grid gap-4 sm:grid-cols-3">
          <Skeleton className="h-40" />
          <Skeleton className="h-40" />
          <Skeleton className="h-40" />
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="space-y-2">
        <h2 className="text-xl font-semibold tracking-tight">
          {syllabusSkipped
            ? "Where are you in this course?"
            : "Where are you in this course?"}
        </h2>
        {suggestion && !syllabusSkipped && (
          <p className="text-sm text-muted-foreground">
            Based on your syllabus dates, it looks like you&apos;re{" "}
            <span className="font-medium text-foreground">
              {SUGGESTION_DESCRIPTIONS[suggestion]}
            </span>
            . Is that right?
          </p>
        )}
      </div>

      {/* Path cards */}
      <div className="grid gap-4 sm:grid-cols-3">
        {PATH_OPTIONS.map((option) => (
          <Card
            key={option.value}
            role="button"
            tabIndex={0}
            onClick={() => setSelected(option.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" || e.key === " ") {
                e.preventDefault();
                setSelected(option.value);
              }
            }}
            className={cn(
              "cursor-pointer transition-all",
              selected === option.value
                ? "border-primary ring-2 ring-primary/20"
                : "hover:border-muted-foreground/50",
            )}
          >
            <CardHeader className="pb-2">
              <div className="text-2xl">{option.icon}</div>
              <CardTitle className="text-base">{option.title}</CardTitle>
            </CardHeader>
            <CardContent>
              <CardDescription>{option.description}</CardDescription>
            </CardContent>
          </Card>
        ))}
      </div>

      {/* Confirm button */}
      <div className="flex justify-end">
        <Button
          onClick={handleConfirm}
          disabled={!selected || submitting}
        >
          {submitting ? "Saving..." : "Confirm & Continue \u2192"}
        </Button>
      </div>
    </div>
  );
}
