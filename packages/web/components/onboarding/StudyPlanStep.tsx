"use client";

import { useState, useEffect } from "react";
import { toast } from "sonner";
import { CalendarDays, BarChart3 } from "lucide-react";

import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { AssessmentTimeline } from "./AssessmentTimeline";
import { getSemesterProgress, completeOnboarding } from "@/lib/api";
import type { OnboardingPath, SemesterProgress } from "@/types/database";

interface StudyPlanStepProps {
  courseId: string;
  path: OnboardingPath;
  onComplete: () => void;
}

export function StudyPlanStep({
  courseId,
  path,
  onComplete,
}: StudyPlanStepProps) {
  const [progress, setProgress] = useState<SemesterProgress | null>(null);
  const [loading, setLoading] = useState(true);
  const [completing, setCompleting] = useState(false);

  useEffect(() => {
    async function load() {
      try {
        const data = await getSemesterProgress(courseId);
        setProgress(data);
      } catch {
        toast.error("Failed to load semester progress");
      } finally {
        setLoading(false);
      }
    }
    load();
  }, [courseId]);

  async function handleComplete() {
    setCompleting(true);
    try {
      await completeOnboarding(courseId);
      onComplete();
    } catch {
      toast.error("Failed to complete onboarding");
    } finally {
      setCompleting(false);
    }
  }

  if (loading) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-8 w-48" />
        <Skeleton className="h-32 w-full" />
        <Skeleton className="h-48 w-full" />
      </div>
    );
  }

  const totalAssessments =
    (progress?.past_assessments.length ?? 0) +
    (progress?.upcoming_assessments.length ?? 0);

  return (
    <div className="space-y-6">
      <h2 className="text-xl font-semibold tracking-tight">Your Study Plan</h2>

      {/* Summary card */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base flex items-center gap-2">
            <BarChart3 className="h-4 w-4" />
            Course Overview
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="flex flex-wrap gap-2">
            <Badge variant="secondary">
              {totalAssessments} assessment{totalAssessments !== 1 && "s"}
            </Badge>
            {progress?.next_assessment && (
              <Badge variant="outline">
                Next: {progress.next_assessment.title}
              </Badge>
            )}
          </div>
          <p className="text-sm text-muted-foreground">
            {path === "mid_semester"
              ? "Your study plan will prioritize topics based on upcoming exams and your past performance."
              : "Your study plan will start generating recommendations as you upload lecture content. For now, here's your assessment calendar."}
          </p>
        </CardContent>
      </Card>

      {/* Assessment timeline */}
      {progress && progress.upcoming_assessments.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base flex items-center gap-2">
              <CalendarDays className="h-4 w-4" />
              Upcoming Deadlines
            </CardTitle>
            <CardDescription>
              {progress.upcoming_assessments.length} upcoming assessment
              {progress.upcoming_assessments.length !== 1 && "s"}
            </CardDescription>
          </CardHeader>
          <CardContent>
            <AssessmentTimeline assessments={progress.upcoming_assessments} />
          </CardContent>
        </Card>
      )}

      {/* Go to dashboard */}
      <div className="flex justify-end">
        <Button onClick={handleComplete} disabled={completing}>
          {completing ? "Finishing..." : "Go to Dashboard \u2192"}
        </Button>
      </div>
    </div>
  );
}
