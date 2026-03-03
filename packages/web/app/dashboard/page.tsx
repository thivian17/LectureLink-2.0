"use client";

import { useState, useEffect, useCallback } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { toast } from "sonner";
import { Plus, BookOpen } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { StreakDisplay } from "@/components/learn/StreakDisplay";
import { LevelBadge } from "@/components/learn/LevelBadge";
import { NextAssessmentCard } from "@/components/learn/NextAssessmentCard";
import { StartSessionButton } from "@/components/learn/StartSessionButton";
import { CourseReadinessCards } from "@/components/learn/CourseReadinessCards";
import { UpcomingAssessmentTimeline } from "@/components/learn/UpcomingAssessmentTimeline";
import { WeeklyProgressSummary } from "@/components/learn/WeeklyProgressSummary";
import { ActivityFeed } from "@/components/learn/ActivityFeed";
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
            (a) => a.type.toLowerCase() !== "ongoing",
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
    <div className="space-y-5">
      {/* Top bar: Streak + Level + Add Course */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <StreakDisplay
            streak={gamification?.streak ?? null}
            loading={loading}
          />
          <LevelBadge
            level={gamification?.level ?? null}
            todayXp={gamification?.today_xp}
            loading={loading}
          />
        </div>
        <Button asChild size="sm" variant="outline">
          <Link href="/dashboard/courses/new">
            <Plus className="mr-1.5 h-3.5 w-3.5" />
            Add Course
          </Link>
        </Button>
      </div>

      {!hasCourses && !loading ? (
        <Card className="flex flex-col items-center justify-center py-16">
          <CardHeader className="items-center text-center">
            <div className="mb-2 flex h-12 w-12 items-center justify-center rounded-full bg-muted">
              <BookOpen className="h-6 w-6 text-muted-foreground" />
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
      ) : (
        <>
          {/* Next Assessment Card */}
          <NextAssessmentCard assessment={topAssessment} loading={loading} />

          {/* Primary CTA */}
          <StartSessionButton
            topAssessment={topAssessment}
            courseId={topCourseId}
            loading={loading}
          />

          {/* Course readiness row */}
          {(loading || courseReadiness.length > 0) && (
            <div>
              <h2 className="text-sm font-semibold mb-2 text-muted-foreground">
                Your Courses
              </h2>
              <CourseReadinessCards courses={courseReadiness} loading={loading} />
            </div>
          )}

          {/* Assessment timeline */}
          {(loading || assessments.length > 0) && (
            <div>
              <h2 className="text-sm font-semibold mb-2 text-muted-foreground">
                Upcoming Assessments
              </h2>
              <UpcomingAssessmentTimeline assessments={assessments} loading={loading} />
            </div>
          )}

          {/* Bottom: Weekly Progress + Activity Feed */}
          <div className="grid gap-4 sm:grid-cols-2">
            <WeeklyProgressSummary progress={weeklyProgress} loading={loading} />
            <ActivityFeed
              recentBadges={gamification?.recent_badges ?? []}
              loading={loading}
            />
          </div>
        </>
      )}
    </div>
  );
}
