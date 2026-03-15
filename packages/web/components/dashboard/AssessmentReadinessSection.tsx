"use client";

import { useMemo } from "react";
import { Skeleton } from "@/components/ui/skeleton";
import { AssessmentReadinessCard } from "./AssessmentReadinessCard";
import type { DashboardCourses, AssessmentReadinessV2 } from "@/types/database";

const EXAM_TYPES = new Set(["exam", "midterm", "quiz", "test", "final"]);

interface AssessmentReadinessSectionProps {
  courses: DashboardCourses | null;
  loading: boolean;
}

export function AssessmentReadinessSection({
  courses,
  loading,
}: AssessmentReadinessSectionProps) {
  // Extract exam-type assessments from course intelligence data
  const assessments = useMemo(() => {
    if (!courses?.courses) return [];

    const items: AssessmentReadinessV2[] = [];

    for (const course of courses.courses) {
      const next = course.next_assessment;
      if (!next) continue;
      if (!EXAM_TYPES.has(next.type.toLowerCase())) continue;

      // Build a partial AssessmentReadinessV2 from the summary data
      items.push({
        assessment_id: `${course.course_id}-next`,
        title: next.title,
        course_id: course.course_id,
        course_name: course.course_name,
        assessment_type: next.type,
        due_date: next.due_date,
        days_until_due: next.days_until,
        readiness: next.readiness ?? course.readiness,
        breakdown: { coverage: 0, practice: 0, freshness: 0, effort: 0 },
        weak_concepts: [],
        suggested_actions: course.recommended_action
          ? [course.recommended_action]
          : [],
        urgency:
          course.risk === "high"
            ? "high"
            : course.risk === "medium"
              ? "medium"
              : "low",
        concept_count: 0,
        covered_count: 0,
      });
    }

    // Sort by days_until ascending (most urgent first)
    items.sort((a, b) => {
      const da = a.days_until_due ?? 9999;
      const db = b.days_until_due ?? 9999;
      return da - db;
    });

    return items;
  }, [courses]);

  if (loading) {
    return (
      <section className="space-y-3">
        <div>
          <h2 className="text-base font-semibold">Assessment Readiness</h2>
          <p className="text-xs text-muted-foreground">
            Your exam preparation status
          </p>
        </div>
        <div className="space-y-3">
          <Skeleton className="h-28 w-full rounded-xl" />
          <Skeleton className="h-28 w-full rounded-xl" />
        </div>
      </section>
    );
  }

  if (assessments.length === 0) {
    return (
      <section className="space-y-3">
        <div>
          <h2 className="text-base font-semibold">Assessment Readiness</h2>
          <p className="text-xs text-muted-foreground">
            Your exam preparation status
          </p>
        </div>
        <p className="text-sm text-muted-foreground py-2">
          No upcoming exams
        </p>
      </section>
    );
  }

  return (
    <section className="space-y-3">
      <div>
        <h2 className="text-base font-semibold">Assessment Readiness</h2>
        <p className="text-xs text-muted-foreground">
          Your exam preparation status
        </p>
      </div>
      <div className="space-y-3">
        {assessments.map((assessment) => (
          <AssessmentReadinessCard
            key={assessment.assessment_id}
            assessment={assessment}
          />
        ))}
      </div>
    </section>
  );
}
