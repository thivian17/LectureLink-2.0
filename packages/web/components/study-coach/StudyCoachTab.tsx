"use client";

import { useState, useEffect, useCallback } from "react";
import { toast } from "sonner";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { PerformanceDashboard } from "@/components/study-coach/PerformanceDashboard";
import { WeakAreasPanel } from "@/components/study-coach/WeakAreasPanel";
import { CoachChat } from "@/components/study-coach/CoachChat";
import { getCoursePerformance, AuthError } from "@/lib/api";
import type { PerformanceData } from "@/types/database";

interface StudyCoachTabProps {
  courseId: string;
}

export function StudyCoachTab({ courseId }: StudyCoachTabProps) {
  const [performance, setPerformance] = useState<PerformanceData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadPerformance = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await getCoursePerformance(courseId);
      setPerformance(data);
    } catch (err) {
      if (err instanceof AuthError) {
        toast.error("Session expired. Please log in again.");
        return;
      }
      setError(
        err instanceof Error ? err.message : "Failed to load performance",
      );
    } finally {
      setLoading(false);
    }
  }, [courseId]);

  useEffect(() => {
    loadPerformance();
  }, [loadPerformance]);

  if (loading) {
    return <StudyCoachSkeleton />;
  }

  if (error) {
    return (
      <Card>
        <CardContent className="py-10 text-center">
          <p className="text-sm text-destructive mb-4">{error}</p>
          <button
            onClick={loadPerformance}
            className="text-sm text-primary hover:underline"
          >
            Try again
          </button>
        </CardContent>
      </Card>
    );
  }

  const hasQuizData =
    performance && performance.overall.total_questions_attempted > 0;

  return (
    <div className="space-y-6">
      {hasQuizData ? (
        <>
          <PerformanceDashboard performance={performance} />
          <div className="grid gap-6 lg:grid-cols-2">
            <WeakAreasPanel
              concepts={performance.concepts}
              weakConceptIds={performance.weak_concepts}
              courseId={courseId}
            />
            <CoachChat courseId={courseId} />
          </div>
        </>
      ) : (
        <div className="grid gap-6 lg:grid-cols-2">
          <Card className="flex flex-col items-center justify-center py-16">
            <CardHeader className="items-center text-center">
              <CardTitle>No quiz data yet</CardTitle>
              <p className="text-sm text-muted-foreground mt-1">
                Take some quizzes to unlock personalized performance insights
                and study recommendations.
              </p>
            </CardHeader>
          </Card>
          <CoachChat courseId={courseId} />
        </div>
      )}
    </div>
  );
}

function StudyCoachSkeleton() {
  return (
    <div className="space-y-6">
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {[1, 2, 3, 4].map((i) => (
          <Card key={i}>
            <CardContent className="pt-6">
              <Skeleton className="h-4 w-20 mb-2" />
              <Skeleton className="h-8 w-16" />
            </CardContent>
          </Card>
        ))}
      </div>
      <div className="grid gap-6 lg:grid-cols-2">
        <Skeleton className="h-64" />
        <Skeleton className="h-64" />
      </div>
    </div>
  );
}
