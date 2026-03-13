"use client";

import { useState, useEffect, useCallback } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { toast } from "sonner";
import { Plus, BookOpen, Calendar } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { StudyBriefingAgent } from "@/components/dashboard-agent/StudyBriefingAgent";
import { StartSessionButton } from "@/components/learn/StartSessionButton";
import { CourseReadinessCards } from "@/components/learn/CourseReadinessCards";
import { UpcomingAssessmentTimeline } from "@/components/learn/UpcomingAssessmentTimeline";
import {
  getCourses,
  getGamificationState,
  getGamificationReadiness,
  getCourseReadiness,
  getWeeklyProgress,
  AuthError,
} from "@/lib/api";
import type {
  Course,
  GamificationState,
  GamificationReadiness,
  CourseReadinessSummary,
  WeeklyProgress,
} from "@/types/database";

export default function DashboardPage() {
  const router = useRouter();

  const [courses, setCourses] = useState<Course[]>([]);
  const [gamification, setGamification] = useState<GamificationState | null>(null);
  const [assessments, setAssessments] = useState<GamificationReadiness[]>([]);
  const [courseReadiness, setCourseReadiness] = useState<CourseReadinessSummary[]>([]);
  const [weeklyProgress, setWeeklyProgress] = useState<WeeklyProgress | null>(null);
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
        getGamificationState(),
        getGamificationReadiness(),
        getWeeklyProgress(),
        ...coursesData.map((c) => getCourseReadiness(c.id)),
      ]);

      const [gamState, readiness, weekly, ...courseResults] = results;

      if (gamState.status === "fulfilled") setGamification(gamState.value);
      if (readiness.status === "fulfilled")
        setAssessments(
          readiness.value.filter(
            (a) => a.type.toLowerCase() !== "ongoing" && a.due_date != null,
          ),
        );
      if (weekly.status === "fulfilled") setWeeklyProgress(weekly.value);

      const summaries: CourseReadinessSummary[] = [];
      courseResults.forEach((r) => {
        if (r.status === "fulfilled") summaries.push(r.value);
      });
      setCourseReadiness(summaries);
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
  const topAssessment = assessments.length > 0 ? assessments[0] : null;
  const topCourseId = topAssessment
    ? courseReadiness.find(
        (cr) => cr.next_assessment?.title === topAssessment.title,
      )?.course_id ?? courses[0]?.id ?? null
    : courses[0]?.id ?? null;

  return (
    <div className="space-y-6">
      {/* Header: Study Hub title + Add Course */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Study Hub</h1>
          <p className="text-sm text-muted-foreground">
            Here&apos;s what to focus on today.
          </p>
        </div>
        <Button asChild size="sm">
          <Link href="/dashboard/courses/new">
            <Plus className="mr-1.5 h-3.5 w-3.5" />
            Add Course
          </Link>
        </Button>
      </div>

      {!hasCourses && !loading ? (
        <>
          <StudyBriefingAgent />
          <Card className="flex flex-col items-center justify-center py-16">
            <CardHeader className="items-center text-center">
              <div className="mb-2 flex h-12 w-12 items-center justify-center rounded-2xl bg-primary/10">
                <BookOpen className="h-6 w-6 text-primary" />
              </div>
              <CardTitle>No courses yet</CardTitle>
              <CardDescription>
                Add your first course and upload a syllabus to get started.
              </CardDescription>
            </CardHeader>
            <Button asChild>
              <Link href="/dashboard/courses/new">
                <Plus className="mr-2 h-4 w-4" />
                Add Course
              </Link>
            </Button>
          </Card>
        </>
      ) : (
        <>
          {/* Study Briefing Agent */}
          <StudyBriefingAgent />

          {/* Primary CTA: Start Today's Session */}
          <StartSessionButton
            topAssessment={topAssessment}
            courseId={topCourseId}
            loading={loading}
          />

          {/* Your Courses */}
          {(loading || courseReadiness.length > 0) && (
            <div>
              <h2 className="text-base font-semibold mb-3">Your Courses</h2>
              <CourseReadinessCards
                courses={courseReadiness}
                allCourses={courses}
                loading={loading}
              />
            </div>
          )}

          {/* Upcoming Assessments */}
          {(loading || assessments.length > 0) && (
            <div>
              <div className="flex items-center justify-between mb-3">
                <h2 className="text-base font-semibold">
                  Upcoming Assessments
                </h2>
                <Button variant="ghost" size="sm" asChild>
                  <Link href="/dashboard/calendar">
                    <Calendar className="mr-2 h-4 w-4" />
                    View Calendar
                  </Link>
                </Button>
              </div>
              <UpcomingAssessmentTimeline assessments={assessments} loading={loading} />
            </div>
          )}
        </>
      )}
    </div>
  );
}
