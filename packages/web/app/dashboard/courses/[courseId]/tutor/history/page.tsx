"use client";

import { useState, useEffect, useCallback } from "react";
import { useParams, useRouter } from "next/navigation";
import { format } from "date-fns";
import {
  ArrowLeft,
  Clock,
  Target,
  BrainCircuit,
  BookOpen,
  Pencil,
  Loader2,
} from "lucide-react";
import { toast } from "sonner";
import Link from "next/link";

import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { SessionSummary } from "@/components/tutor/SessionSummary";
import { getTutorHistory, getTutorSessionSummary } from "@/lib/api";
import { AuthError } from "@/lib/api-errors";
import type {
  TutorSession,
  TutorMode,
  SessionSummary as SessionSummaryType,
} from "@/types/database";

const MODE_ICONS: Record<TutorMode, React.ElementType> = {
  diagnostic: BrainCircuit,
  full_lesson: BookOpen,
  custom_topic: Pencil,
  custom_plan: Pencil,
};

const MODE_LABELS: Record<TutorMode, string> = {
  diagnostic: "Diagnostic",
  full_lesson: "Full Lesson",
  custom_topic: "Custom Topic",
  custom_plan: "Custom Plan",
};

function formatDuration(seconds: number): string {
  const m = Math.floor(seconds / 60);
  if (m === 0) return `${seconds}s`;
  return `${m}m`;
}

export default function TutorHistoryPage() {
  const params = useParams<{ courseId: string }>();
  const courseId = params.courseId;
  const router = useRouter();

  const [sessions, setSessions] = useState<TutorSession[]>([]);
  const [loading, setLoading] = useState(true);
  const [viewingSummary, setViewingSummary] =
    useState<SessionSummaryType | null>(null);
  const [loadingSummary, setLoadingSummary] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      const data = await getTutorHistory(courseId);
      setSessions(data);
    } catch (err) {
      if (err instanceof AuthError) {
        router.push("/login");
        return;
      }
      toast.error("Failed to load session history");
    } finally {
      setLoading(false);
    }
  }, [courseId, router]);

  useEffect(() => {
    load();
  }, [load]);

  async function handleViewSummary(sessionId: string) {
    setLoadingSummary(sessionId);
    try {
      const summary = await getTutorSessionSummary(sessionId);
      setViewingSummary(summary);
    } catch {
      toast.error("Failed to load session summary");
    } finally {
      setLoadingSummary(null);
    }
  }

  if (loading) {
    return (
      <div className="space-y-6">
        <Skeleton className="h-8 w-48" />
        <div className="space-y-3">
          {Array.from({ length: 4 }, (_, i) => (
            <Skeleton key={i} className="h-24 w-full rounded-xl" />
          ))}
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-3">
        <Button variant="ghost" size="icon" asChild>
          <Link href={`/dashboard/courses/${courseId}/tutor`}>
            <ArrowLeft className="h-4 w-4" />
          </Link>
        </Button>
        <div>
          <h1 className="text-2xl font-bold tracking-tight">
            Session History
          </h1>
          <p className="text-muted-foreground">
            {sessions.length} past study session
            {sessions.length !== 1 ? "s" : ""}
          </p>
        </div>
      </div>

      {sessions.length === 0 ? (
        <Card className="flex flex-col items-center justify-center py-16">
          <CardHeader className="items-center text-center">
            <CardTitle>No sessions yet</CardTitle>
            <CardDescription>
              Start your first study session to see your history here.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <Button asChild>
              <Link href={`/dashboard/courses/${courseId}/tutor`}>
                Start a Session
              </Link>
            </Button>
          </CardContent>
        </Card>
      ) : (
        <div className="space-y-3">
          {sessions.map((s) => {
            const Icon = MODE_ICONS[s.mode];
            const accuracy =
              s.questions_asked > 0
                ? Math.round(
                    (s.questions_correct / s.questions_asked) * 100,
                  )
                : null;

            return (
              <Card
                key={s.id}
                className="cursor-pointer transition-shadow hover:shadow-md"
                onClick={() => handleViewSummary(s.id)}
              >
                <CardContent className="pt-6">
                  <div className="flex items-start justify-between gap-4">
                    <div className="space-y-1.5 min-w-0">
                      <div className="flex items-center gap-2">
                        <Icon className="h-4 w-4 text-muted-foreground shrink-0" />
                        <p className="font-medium text-sm">
                          {MODE_LABELS[s.mode]}
                        </p>
                        <Badge
                          variant={
                            s.status === "completed"
                              ? "secondary"
                              : "outline"
                          }
                          className="text-[10px]"
                        >
                          {s.status}
                        </Badge>
                      </div>
                      <div className="flex flex-wrap items-center gap-3 text-sm text-muted-foreground">
                        <span>
                          {format(new Date(s.started_at), "MMM d, yyyy")}
                        </span>
                        <span className="flex items-center gap-1">
                          <Clock className="h-3 w-3" />
                          {formatDuration(s.duration_seconds)}
                        </span>
                        <span>
                          {s.concepts_completed} of {s.concepts_planned}{" "}
                          concepts
                        </span>
                        {accuracy != null && (
                          <span className="flex items-center gap-1">
                            <Target className="h-3 w-3" />
                            {accuracy}%
                          </span>
                        )}
                      </div>
                    </div>
                    {loadingSummary === s.id && (
                      <Loader2 className="h-4 w-4 animate-spin text-muted-foreground shrink-0" />
                    )}
                  </div>
                </CardContent>
              </Card>
            );
          })}
        </div>
      )}

      {/* Summary overlay */}
      {viewingSummary && (
        <SessionSummary
          summary={viewingSummary}
          onBackToCourse={() => setViewingSummary(null)}
          onStartAnother={() =>
            router.push(`/dashboard/courses/${courseId}/tutor`)
          }
        />
      )}
    </div>
  );
}
