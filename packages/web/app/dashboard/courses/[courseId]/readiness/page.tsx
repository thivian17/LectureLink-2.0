"use client";

import { useState, useEffect, useCallback } from "react";
import { useParams, useRouter } from "next/navigation";
import { toast } from "sonner";
import { BookOpen, GraduationCap } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { AssessmentReadinessCard } from "@/components/dashboard/AssessmentReadinessCard";
import { getCourseReadinessV2, AuthError } from "@/lib/api";
import type { AssessmentReadinessV2 } from "@/types/database";

export default function ReadinessPage() {
  const params = useParams<{ courseId: string }>();
  const router = useRouter();
  const courseId = params.courseId;

  const [assessments, setAssessments] = useState<AssessmentReadinessV2[]>([]);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    try {
      const data = await getCourseReadinessV2(courseId);
      setAssessments(data);
    } catch (err) {
      if (err instanceof AuthError) {
        router.push("/login");
        return;
      }
      toast.error("Failed to load readiness data");
    } finally {
      setLoading(false);
    }
  }, [courseId, router]);

  useEffect(() => {
    load();
  }, [load]);

  // Compute overall readiness across all assessments
  const overallReadiness =
    assessments.length > 0
      ? Math.round(
          (assessments.reduce((sum, a) => sum + a.readiness, 0) /
            assessments.length) *
            100,
        )
      : 0;

  return (
    <div className="space-y-5">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">
          Assessment Readiness
        </h1>
        <p className="text-muted-foreground text-sm">
          Track your preparation for upcoming assessments
        </p>
      </div>

      {/* Overall readiness bar */}
      {!loading && assessments.length > 0 && (
        <div className="rounded-xl border bg-card p-4">
          <div className="flex items-center justify-between mb-2">
            <span className="text-sm font-semibold">Overall Readiness</span>
            <span className="text-sm font-bold tabular-nums">
              {overallReadiness}%
            </span>
          </div>
          <div className="h-2.5 rounded-full bg-muted overflow-hidden">
            <div
              className="h-full rounded-full transition-all duration-1000"
              style={{
                width: `${overallReadiness}%`,
                background: "linear-gradient(90deg, #2563EB, #3B82F6)",
              }}
            />
          </div>
        </div>
      )}

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
            <AssessmentReadinessCard key={a.assessment_id} assessment={a} />
          ))}
        </div>
      )}

      {/* Study action buttons */}
      <div className="flex gap-3">
        <Button
          className="flex-1"
          onClick={() =>
            router.push(`/dashboard/courses/${courseId}/learn`)
          }
        >
          <BookOpen className="h-4 w-4 mr-2" />
          Study Weakest Concepts
        </Button>
        <Button
          variant="outline"
          className="flex-1"
          onClick={() =>
            router.push(`/dashboard/courses/${courseId}/assessment-prep`)
          }
        >
          <GraduationCap className="h-4 w-4 mr-2" />
          Start Master Mode
        </Button>
      </div>
    </div>
  );
}
