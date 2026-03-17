"use client";

import { useState, useEffect, useCallback } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { toast } from "sonner";
import { Plus, BookOpen } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { AcademicCommandCenter } from "@/components/dashboard/AcademicCommandCenter";
import { BestNextActions } from "@/components/dashboard/BestNextActions";
import { CourseIntelligenceGrid } from "@/components/dashboard/CourseIntelligenceGrid";
import { AssessmentReadinessSection } from "@/components/dashboard/AssessmentReadinessSection";
import { StudyToolsLibrary } from "@/components/dashboard/StudyToolsLibrary";
import { ProcessingBanner } from "@/components/dashboard/ProcessingBanner";
import {
  getCourses,
  getDashboardTimeline,
  getDashboardActions,
  getDashboardCourses,
  getDashboardStats,
  AuthError,
} from "@/lib/api";
import type {
  Course,
  DashboardTimeline,
  DashboardActions,
  DashboardCourses,
  DashboardStats,
} from "@/types/database";

export default function DashboardPage() {
  const router = useRouter();
  const [courses, setCourses] = useState<Course[]>([]);
  const [timeline, setTimeline] = useState<DashboardTimeline | null>(null);
  const [actions, setActions] = useState<DashboardActions | null>(null);
  const [courseData, setCourseData] = useState<DashboardCourses | null>(null);
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    try {
      const coursesData = await getCourses();
      setCourses(coursesData);

      if (coursesData.length === 0) {
        setLoading(false);
        return;
      }

      const results = await Promise.allSettled([
        getDashboardTimeline(),
        getDashboardActions(),
        getDashboardCourses(),
        getDashboardStats(),
      ]);

      const [timelineRes, actionsRes, coursesRes, statsRes] = results;

      if (timelineRes.status === "fulfilled") setTimeline(timelineRes.value);
      if (actionsRes.status === "fulfilled") setActions(actionsRes.value);
      if (coursesRes.status === "fulfilled") setCourseData(coursesRes.value);
      if (statsRes.status === "fulfilled") setStats(statsRes.value);
    } catch (err) {
      if (err instanceof AuthError) {
        router.push("/login");
        return;
      }
      toast.error("Failed to load dashboard data");
    } finally {
      setLoading(false);
    }
  }, [router]);

  useEffect(() => {
    load();
  }, [load]);

  const hasCourses = courses.length > 0;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Study Hub</h1>
          <p className="text-sm text-muted-foreground">
            Your academic command center.
          </p>
        </div>
        <Button asChild size="sm">
          <Link href="/dashboard/courses/new">
            <Plus className="mr-1.5 h-3.5 w-3.5" />
            Add Course
          </Link>
        </Button>
      </div>

      {hasCourses && !loading && <ProcessingBanner />}

      {!hasCourses && !loading ? (
        <Card className="py-16">
          <div className="flex flex-col items-center text-center px-6">
            <div className="mb-4 flex h-12 w-12 items-center justify-center rounded-2xl bg-primary/10">
              <BookOpen className="h-6 w-6 text-primary" />
            </div>
            <h2 className="text-lg font-semibold">No courses yet</h2>
            <p className="mt-1 text-sm text-muted-foreground max-w-sm">
              Add your first course and upload a syllabus to get started with
              personalized study sessions, quizzes, and mastery tracking.
            </p>
            <Button asChild className="mt-6">
              <Link href="/dashboard/courses/new">
                <Plus className="mr-2 h-4 w-4" /> Add Course
              </Link>
            </Button>
          </div>
        </Card>
      ) : (
        <>
          <AcademicCommandCenter
            timeline={timeline}
            stats={stats}
            loading={loading}
          />
          <BestNextActions actions={actions} loading={loading} />
          <CourseIntelligenceGrid courses={courseData} loading={loading} />
          <AssessmentReadinessSection courses={courseData} loading={loading} />
          <StudyToolsLibrary />
        </>
      )}
    </div>
  );
}
