"use client";

import { useState, useEffect, useCallback } from "react";
import { useRouter } from "next/navigation";
import { Plus, BookOpen } from "lucide-react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { LectureCard } from "@/components/lectures/lecture-card";
import { ErrorState } from "@/components/error-state";
import { getLectures, AuthError, RateLimitError } from "@/lib/api";
import type { Lecture } from "@/types/database";

interface LectureListProps {
  courseId: string;
  courseName: string;
}

export function LectureList({ courseId, courseName }: LectureListProps) {
  const router = useRouter();
  const [lectures, setLectures] = useState<Lecture[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);

  const loadLectures = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await getLectures(courseId);
      data.sort(
        (a, b) =>
          new Date(b.lecture_date ?? b.created_at).getTime() -
          new Date(a.lecture_date ?? a.created_at).getTime(),
      );
      setLectures(data);
    } catch (err) {
      const e = err instanceof Error ? err : new Error("Failed to load lectures");
      setError(e);
      if (err instanceof AuthError) {
        toast.error("Session expired. Please log in again.");
        router.push("/login");
        return;
      }
      if (err instanceof RateLimitError) {
        toast.error(
          `Rate limit reached. Try again in ${Math.ceil(err.retryAfterSeconds / 60)} min.`,
        );
        return;
      }
      toast.error(e.message);
    } finally {
      setLoading(false);
    }
  }, [courseId, router]);

  useEffect(() => {
    let cancelled = false;
    loadLectures().then(() => {
      if (cancelled) return;
    });
    return () => {
      cancelled = true;
    };
  }, [loadLectures]);

  if (loading) {
    return (
      <div className="space-y-6">
        <LectureListHeader courseName={courseName} courseId={courseId} />
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {[1, 2, 3].map((i) => (
            <Card key={i} className="h-full">
              <CardHeader className="pb-3">
                <div className="flex items-start justify-between gap-2">
                  <div className="flex-1 space-y-2">
                    <Skeleton className="h-5 w-3/4" />
                    <Skeleton className="h-4 w-1/3" />
                  </div>
                  <Skeleton className="h-5 w-16 rounded-full" />
                </div>
              </CardHeader>
              <CardContent className="space-y-3">
                <Skeleton className="h-4 w-24" />
                <Skeleton className="h-4 w-full" />
                <Skeleton className="h-4 w-2/3" />
              </CardContent>
            </Card>
          ))}
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="space-y-6">
        <LectureListHeader courseName={courseName} courseId={courseId} />
        <ErrorState error={error} onRetry={loadLectures} />
      </div>
    );
  }

  if (lectures.length === 0) {
    return (
      <div className="space-y-6">
        <LectureListHeader courseName={courseName} courseId={courseId} />
        <div className="flex flex-col items-center justify-center rounded-lg border border-dashed py-16 text-center">
          <BookOpen className="h-12 w-12 text-muted-foreground/50" />
          <h3 className="mt-4 text-lg font-medium">No lectures yet</h3>
          <p className="mt-1 text-sm text-muted-foreground">
            Upload your first lecture recording to get started.
          </p>
          <Button
            className="mt-6"
            onClick={() =>
              router.push(`/dashboard/courses/${courseId}/lectures/new`)
            }
          >
            <Plus className="mr-2 h-4 w-4" />
            Upload Lecture
          </Button>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <LectureListHeader courseName={courseName} courseId={courseId} />
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {lectures.map((lecture) => (
          <LectureCard key={lecture.id} lecture={lecture} courseId={courseId} onRetry={loadLectures} />
        ))}
      </div>
    </div>
  );
}

function LectureListHeader({
  courseName,
  courseId,
}: {
  courseName: string;
  courseId: string;
}) {
  const router = useRouter();
  return (
    <div className="flex items-center justify-between">
      <div>
        <h2 className="text-lg font-semibold">Lectures</h2>
        <p className="text-sm text-muted-foreground">{courseName}</p>
      </div>
      <Button
        onClick={() =>
          router.push(`/dashboard/courses/${courseId}/lectures/new`)
        }
      >
        <Plus className="mr-2 h-4 w-4" />
        Upload Lecture
      </Button>
    </div>
  );
}
