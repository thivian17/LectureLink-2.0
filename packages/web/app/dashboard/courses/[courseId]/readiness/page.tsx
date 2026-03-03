"use client";

import { useState, useEffect, useCallback } from "react";
import { useParams, useRouter } from "next/navigation";
import { toast } from "sonner";
import { BookOpen, GraduationCap } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { ReadinessDetail } from "@/components/learn/ReadinessDetail";
import { GradeProjection } from "@/components/learn/GradeProjection";
import {
  getGamificationReadiness,
  getGradeProjection,
  AuthError,
} from "@/lib/api";
import type {
  GamificationReadiness,
  GradeProjection as GradeProjectionType,
} from "@/types/database";

export default function ReadinessPage() {
  const params = useParams<{ courseId: string }>();
  const router = useRouter();
  const courseId = params.courseId;

  const [assessments, setAssessments] = useState<GamificationReadiness[]>([]);
  const [projection, setProjection] = useState<GradeProjectionType | null>(null);
  const [loading, setLoading] = useState(true);
  const [projectionLoading, setProjectionLoading] = useState(true);

  const load = useCallback(async () => {
    try {
      const [readinessData, projData] = await Promise.allSettled([
        getGamificationReadiness(courseId),
        getGradeProjection(courseId),
      ]);

      if (readinessData.status === "fulfilled") setAssessments(readinessData.value);
      if (projData.status === "fulfilled") setProjection(projData.value);
    } catch (err) {
      if (err instanceof AuthError) {
        router.push("/login");
        return;
      }
      toast.error("Failed to load readiness data");
    } finally {
      setLoading(false);
      setProjectionLoading(false);
    }
  }, [courseId, router]);

  useEffect(() => {
    load();
  }, [load]);

  return (
    <div className="space-y-5">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Assessment Readiness</h1>
        <p className="text-muted-foreground text-sm">
          Track your preparation for upcoming assessments
        </p>
      </div>

      <GradeProjection projection={projection} loading={projectionLoading} />

      {loading ? (
        <div className="space-y-3">
          {[1, 2, 3].map((i) => (
            <Skeleton key={i} className="h-28 rounded-xl" />
          ))}
        </div>
      ) : assessments.length === 0 ? (
        <div className="text-center py-12 text-muted-foreground text-sm">
          No assessments found for this course.
        </div>
      ) : (
        <div className="space-y-3">
          {assessments.map((a) => (
            <ReadinessDetail key={a.assessment_id} assessment={a} />
          ))}
        </div>
      )}

      {/* Study action buttons */}
      <div className="flex gap-3">
        <Button
          className="flex-1"
          onClick={() => router.push(`/dashboard/courses/${courseId}/learn`)}
        >
          <BookOpen className="h-4 w-4 mr-2" />
          Study Weakest Concepts
        </Button>
        <Button
          variant="outline"
          className="flex-1"
          onClick={() => router.push(`/dashboard/courses/${courseId}/tutor`)}
        >
          <GraduationCap className="h-4 w-4 mr-2" />
          Start Master Mode
        </Button>
      </div>
    </div>
  );
}
