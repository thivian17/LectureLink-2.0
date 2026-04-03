"use client";

import { motion } from "framer-motion";
import { GraduationCap } from "lucide-react";
import { Skeleton } from "@/components/ui/skeleton";
import { CourseIntelligenceCard } from "./CourseIntelligenceCard";
import type { DashboardCourses } from "@/types/database";

interface CourseIntelligenceGridProps {
  courses: DashboardCourses | null;
  loading: boolean;
}

/* ------------------------------------------------------------------ */
/*  Shimmer skeleton for loading state                                */
/* ------------------------------------------------------------------ */

function CardSkeleton() {
  return (
    <div className="rounded-2xl border border-border/40 bg-card p-5 space-y-4">
      <div className="flex items-start justify-between">
        <div className="space-y-2 flex-1">
          <Skeleton className="h-3 w-16 rounded-full" />
          <Skeleton className="h-4 w-36 rounded-full" />
        </div>
        <Skeleton className="h-5 w-20 rounded-full" />
      </div>
      <div className="flex items-center gap-4">
        <Skeleton className="h-[72px] w-[72px] rounded-full" />
        <div className="space-y-2 flex-1">
          <Skeleton className="h-3 w-24 rounded-full" />
          <Skeleton className="h-1.5 w-full rounded-full" />
          <Skeleton className="h-3 w-28 rounded-full" />
        </div>
      </div>
      <Skeleton className="h-px w-full" />
      <div className="flex items-center gap-2.5">
        <Skeleton className="h-8 w-8 rounded-lg" />
        <div className="space-y-1.5 flex-1">
          <Skeleton className="h-3 w-32 rounded-full" />
          <Skeleton className="h-3 w-20 rounded-full" />
        </div>
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  Grid component                                                    */
/* ------------------------------------------------------------------ */

export function CourseIntelligenceGrid({
  courses,
  loading,
}: CourseIntelligenceGridProps) {
  if (loading) {
    return (
      <section className="space-y-4">
        <div className="flex items-center gap-2.5">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary/10">
            <GraduationCap className="h-4 w-4 text-primary" />
          </div>
          <div>
            <h2 className="text-base font-semibold">Your Courses</h2>
            <p className="text-xs text-muted-foreground">Loading...</p>
          </div>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {Array.from({ length: 3 }).map((_, i) => (
            <CardSkeleton key={i} />
          ))}
        </div>
      </section>
    );
  }

  const items = courses?.courses ?? [];
  if (items.length === 0) return null;

  return (
    <section className="space-y-4">
      {/* Section header */}
      <motion.div
        className="flex items-center gap-2.5"
        initial={{ opacity: 0, x: -10 }}
        animate={{ opacity: 1, x: 0 }}
        transition={{ duration: 0.3 }}
      >
        <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary/10">
          <GraduationCap className="h-4 w-4 text-primary" />
        </div>
        <div>
          <h2 className="text-base font-semibold">Your Courses</h2>
          <p className="text-xs text-muted-foreground">
            {items.length} course{items.length !== 1 ? "s" : ""} this semester
          </p>
        </div>
      </motion.div>

      {/* Card grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {items.map((course, i) => (
          <CourseIntelligenceCard
            key={course.course_id}
            course={course}
            index={i}
          />
        ))}
      </div>
    </section>
  );
}
