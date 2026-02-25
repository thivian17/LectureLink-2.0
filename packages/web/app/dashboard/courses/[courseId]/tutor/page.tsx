"use client";

import { useState, useEffect, useCallback } from "react";
import { useParams, useRouter } from "next/navigation";
import { Loader2, History, Play, ArrowRight } from "lucide-react";
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
import { Skeleton } from "@/components/ui/skeleton";
import { ModeSelector } from "@/components/tutor/ModeSelector";
import { AssessmentSelector } from "@/components/tutor/AssessmentSelector";
import { AssessmentConceptsPanel } from "@/components/tutor/AssessmentConceptsPanel";
import {
  getTutorEntry,
  startTutorSession,
  resumeTutorSession,
  getAssessmentReadiness,
} from "@/lib/api";
import { AuthError } from "@/lib/api-errors";
import type {
  TutorMode,
  TutorSessionEntry,
  AssessmentReadiness,
} from "@/types/database";

export default function TutorHomePage() {
  const params = useParams<{ courseId: string }>();
  const courseId = params.courseId;
  const router = useRouter();

  const [entry, setEntry] = useState<TutorSessionEntry | null>(null);
  const [loading, setLoading] = useState(true);
  const [starting, setStarting] = useState(false);
  const [resuming, setResuming] = useState(false);

  const [selectedMode, setSelectedMode] = useState<TutorMode | null>(null);
  const [selectedAssessment, setSelectedAssessment] = useState<string | null>(
    null,
  );

  // Assessment readiness data
  const [readiness, setReadiness] = useState<AssessmentReadiness | null>(null);
  const [readinessLoading, setReadinessLoading] = useState(false);

  // Custom plan concept selection
  const [selectedConcepts, setSelectedConcepts] = useState<Set<string>>(
    new Set(),
  );

  const load = useCallback(async () => {
    try {
      const data = await getTutorEntry(courseId);
      setEntry(data);
      // Auto-select the first (most urgent) assessment so concepts show immediately
      if (data.upcoming_assessments.length > 0) {
        setSelectedAssessment((prev) => prev ?? data.upcoming_assessments[0].id);
      }
    } catch (err) {
      if (err instanceof AuthError) {
        router.push("/login");
        return;
      }
      toast.error("Failed to load tutor data");
    } finally {
      setLoading(false);
    }
  }, [courseId, router]);

  useEffect(() => {
    load();
  }, [load]);

  // Fetch readiness when assessment changes
  useEffect(() => {
    if (!selectedAssessment) {
      setReadiness(null);
      return;
    }
    setReadinessLoading(true);
    getAssessmentReadiness(courseId, selectedAssessment)
      .then(setReadiness)
      .catch(() => toast.error("Failed to load concept readiness"))
      .finally(() => setReadinessLoading(false));
  }, [courseId, selectedAssessment]);

  // Clear concept selection when assessment or mode changes
  useEffect(() => {
    setSelectedConcepts(new Set());
  }, [selectedAssessment, selectedMode]);

  function handleToggleConcept(conceptId: string) {
    setSelectedConcepts((prev) => {
      const next = new Set(prev);
      if (next.has(conceptId)) {
        next.delete(conceptId);
      } else {
        next.add(conceptId);
      }
      return next;
    });
  }

  async function handleStart() {
    if (!selectedMode) return;

    const effectiveMode =
      selectedMode === "custom_plan" ? "full_lesson" : selectedMode;

    setStarting(true);
    try {
      const session = await startTutorSession(courseId, {
        mode: effectiveMode,
        target_assessment_id: selectedAssessment ?? undefined,
        concept_ids:
          selectedMode === "custom_plan"
            ? Array.from(selectedConcepts)
            : undefined,
      });
      router.push(
        `/dashboard/courses/${courseId}/tutor/session/${session.id}`,
      );
    } catch (err) {
      if (err instanceof AuthError) {
        router.push("/login");
        return;
      }
      toast.error("Failed to start session");
    } finally {
      setStarting(false);
    }
  }

  async function handleResume() {
    if (!entry?.active_session) return;
    setResuming(true);
    try {
      const session = await resumeTutorSession(entry.active_session.id);
      router.push(
        `/dashboard/courses/${courseId}/tutor/session/${session.id}`,
      );
    } catch (err) {
      if (err instanceof AuthError) {
        router.push("/login");
        return;
      }
      toast.error("Failed to resume session");
    } finally {
      setResuming(false);
    }
  }

  if (loading) {
    return (
      <div className="space-y-6">
        <Skeleton className="h-8 w-48" />
        <Skeleton className="h-40 w-full rounded-xl" />
        <div className="grid gap-4 sm:grid-cols-3">
          <Skeleton className="h-28 rounded-xl" />
          <Skeleton className="h-28 rounded-xl" />
          <Skeleton className="h-28 rounded-xl" />
        </div>
      </div>
    );
  }

  const canStart =
    selectedMode != null &&
    (selectedMode !== "custom_plan" || selectedConcepts.size > 0);

  // Auto plan: compute which concepts will be covered (weakest 5)
  const autoConceptIds = new Set<string>();
  if (readiness) {
    const sorted = [...readiness.concepts].sort(
      (a, b) => a.mastery - b.mastery,
    );
    for (const c of sorted.slice(0, 5)) {
      if (c.mastery < 0.7) {
        autoConceptIds.add(c.concept_id ?? c.title);
      }
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Study Tutor</h1>
          <p className="text-muted-foreground">
            Interactive AI-powered study sessions
          </p>
        </div>
        <Button variant="outline" size="sm" asChild>
          <Link
            href={`/dashboard/courses/${courseId}/tutor/history`}
          >
            <History className="mr-2 h-4 w-4" />
            Past Sessions
          </Link>
        </Button>
      </div>

      {/* Resume active session */}
      {entry?.active_session && (
        <Card className="border-primary/50 bg-primary/5">
          <CardHeader className="pb-3">
            <CardTitle className="text-base flex items-center gap-2">
              <Play className="h-4 w-4" />
              Active Session
            </CardTitle>
            <CardDescription>
              You have an in-progress {entry.active_session.mode.replace("_", " ")}{" "}
              session &mdash;{" "}
              {entry.active_session.concepts_completed} of{" "}
              {entry.active_session.concepts_planned} concepts covered.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <Button onClick={handleResume} disabled={resuming}>
              {resuming && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              Resume Session
            </Button>
          </CardContent>
        </Card>
      )}

      {/* Assessment selector */}
      {entry && entry.upcoming_assessments.length > 0 && (
        <AssessmentSelector
          assessments={entry.upcoming_assessments}
          selected={selectedAssessment}
          onSelect={setSelectedAssessment}
        />
      )}

      {/* Assessment concepts panel */}
      {selectedAssessment && (
        <AssessmentConceptsPanel
          readiness={readiness}
          loading={readinessLoading}
          selectable={selectedMode === "custom_plan"}
          selectedIds={selectedConcepts}
          onToggle={handleToggleConcept}
          highlightedIds={selectedMode === "full_lesson" ? autoConceptIds : undefined}
        />
      )}

      {/* Mode selector */}
      <div className="space-y-3">
        <p className="text-sm font-medium">Choose your study mode</p>
        <ModeSelector
          selected={selectedMode}
          onSelect={setSelectedMode}
        />
      </div>

      {/* Start button */}
      <Button
        size="lg"
        className="w-full sm:w-auto"
        onClick={handleStart}
        disabled={!canStart || starting}
      >
        {starting ? (
          <Loader2 className="mr-2 h-4 w-4 animate-spin" />
        ) : (
          <ArrowRight className="mr-2 h-4 w-4" />
        )}
        Start Session
      </Button>
    </div>
  );
}
