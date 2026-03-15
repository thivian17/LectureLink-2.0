"use client";

import { Skeleton } from "@/components/ui/skeleton";
import { CourseIntelligenceCard } from "./CourseIntelligenceCard";
import type { DashboardCourses } from "@/types/database";

interface CourseIntelligenceGridProps {
  courses: DashboardCourses | null;
  loading: boolean;
}

export function CourseIntelligenceGrid({
  courses,
  loading,
}: CourseIntelligenceGridProps) {
  if (loading) {
    return (
      <section className="space-y-3">
        <h2 className="text-base font-semibold">Your Courses</h2>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
          {Array.from({ length: 3 }).map((_, i) => (
            <Skeleton key={i} className="h-44 w-full rounded-xl" />
          ))}
        </div>
      </section>
    );
  }

  const items = courses?.courses ?? [];
  if (items.length === 0) return null;

  return (
    <section className="space-y-3">
      <h2 className="text-base font-semibold">Your Courses</h2>
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
        {items.map((course) => (
          <CourseIntelligenceCard key={course.course_id} course={course} />
        ))}
      </div>
    </section>
  );
}
