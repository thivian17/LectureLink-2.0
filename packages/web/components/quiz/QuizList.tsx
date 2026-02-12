"use client";

import { useState, useEffect, useCallback } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { Plus, GraduationCap } from "lucide-react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { QuizCard } from "@/components/quiz/QuizCard";
import { GenerateQuizDialog } from "@/components/quiz/GenerateQuizDialog";
import { QuizGenerationStatus } from "@/components/quiz/QuizGenerationStatus";
import { ErrorState } from "@/components/error-state";
import {
  getQuizzes,
  getAssessments,
  getLectures,
  generateQuiz,
  AuthError,
  RateLimitError,
} from "@/lib/api";
import type { Quiz, Assessment, Lecture, QuizDifficulty } from "@/types/database";

interface QuizListProps {
  courseId: string;
  courseName: string;
}

export function QuizList({ courseId, courseName }: QuizListProps) {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [quizzes, setQuizzes] = useState<Quiz[]>([]);
  const [assessments, setAssessments] = useState<Assessment[]>([]);
  const [lectures, setLectures] = useState<Lecture[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);
  const [dialogOpen, setDialogOpen] = useState(
    searchParams.get("generate") === "1",
  );
  const [generatingQuizId, setGeneratingQuizId] = useState<string | null>(null);

  const loadQuizzes = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      // Use allSettled so one failure doesn't block the rest
      const [quizResult, assessmentResult, lectureResult] =
        await Promise.allSettled([
          getQuizzes(courseId),
          getAssessments(courseId),
          getLectures(courseId),
        ]);

      // Check for auth errors first
      for (const r of [quizResult, assessmentResult, lectureResult]) {
        if (r.status === "rejected" && r.reason instanceof AuthError) {
          toast.error("Session expired. Please log in again.");
          router.push("/login");
          return;
        }
      }

      if (quizResult.status === "fulfilled") {
        setQuizzes(quizResult.value);
      } else {
        throw quizResult.reason;
      }

      // Assessments and lectures are optional — dialog still works without them
      if (assessmentResult.status === "fulfilled") {
        setAssessments(assessmentResult.value);
      }
      if (lectureResult.status === "fulfilled") {
        setLectures(lectureResult.value);
      }
    } catch (err) {
      const e = err instanceof Error ? err : new Error("Failed to load quizzes");
      setError(e);
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
    loadQuizzes().then(() => {
      if (cancelled) return;
    });
    return () => {
      cancelled = true;
    };
  }, [loadQuizzes]);

  async function handleGenerate(options: {
    target_assessment_id: string | null;
    lecture_ids: string[] | null;
    question_count: number;
    difficulty: QuizDifficulty;
  }) {
    try {
      const result = await generateQuiz(courseId, options);
      setDialogOpen(false);
      setGeneratingQuizId(result.quiz_id);
      toast.success("Quiz generation started!");
    } catch (err) {
      if (err instanceof RateLimitError) {
        toast.error(
          `Daily quiz limit reached. Try again in ${Math.ceil(err.retryAfterSeconds / 60)} min.`,
        );
      } else {
        toast.error("Failed to generate quiz");
      }
    }
  }

  // Always render the dialog so it's available in every state
  const dialog = (
    <GenerateQuizDialog
      open={dialogOpen}
      onOpenChange={setDialogOpen}
      assessments={assessments}
      lectures={lectures}
      onGenerate={handleGenerate}
    />
  );

  if (generatingQuizId) {
    return (
      <div className="space-y-6">
        <QuizListHeader
          courseName={courseName}
          onGenerate={() => setDialogOpen(true)}
        />
        <div className="max-w-md mx-auto">
          <QuizGenerationStatus
            quizId={generatingQuizId}
            courseId={courseId}
          />
        </div>
        {dialog}
      </div>
    );
  }

  if (loading) {
    return (
      <div className="space-y-6">
        <QuizListHeader
          courseName={courseName}
          onGenerate={() => setDialogOpen(true)}
        />
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {[1, 2, 3].map((i) => (
            <Card key={i} className="h-full">
              <CardHeader className="pb-3">
                <div className="flex items-start justify-between gap-2">
                  <Skeleton className="h-5 w-2/3" />
                  <Skeleton className="h-5 w-16 rounded-full" />
                </div>
                <Skeleton className="h-4 w-1/2 mt-1" />
              </CardHeader>
              <CardContent>
                <Skeleton className="h-8 w-16" />
              </CardContent>
            </Card>
          ))}
        </div>
        {dialog}
      </div>
    );
  }

  if (error) {
    return (
      <div className="space-y-6">
        <QuizListHeader
          courseName={courseName}
          onGenerate={() => setDialogOpen(true)}
        />
        <ErrorState error={error} onRetry={loadQuizzes} />
        {dialog}
      </div>
    );
  }

  if (quizzes.length === 0) {
    return (
      <div className="space-y-6">
        <QuizListHeader
          courseName={courseName}
          onGenerate={() => setDialogOpen(true)}
        />
        <div className="flex flex-col items-center justify-center rounded-lg border border-dashed py-16 text-center">
          <GraduationCap className="h-12 w-12 text-muted-foreground/50" />
          <h3 className="mt-4 text-lg font-medium">No quizzes yet</h3>
          <p className="mt-1 text-sm text-muted-foreground">
            Generate your first quiz to test your knowledge.
          </p>
          <Button className="mt-6" onClick={() => setDialogOpen(true)}>
            <Plus className="mr-2 h-4 w-4" />
            Generate Quiz
          </Button>
        </div>
        {dialog}
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <QuizListHeader
        courseName={courseName}
        onGenerate={() => setDialogOpen(true)}
      />
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {quizzes.map((quiz) => (
          <QuizCard key={quiz.id} quiz={quiz} courseId={courseId} />
        ))}
      </div>
      {dialog}
    </div>
  );
}

function QuizListHeader({
  courseName,
  onGenerate,
}: {
  courseName: string;
  onGenerate: () => void;
}) {
  return (
    <div className="flex items-center justify-between">
      <div>
        <h2 className="text-lg font-semibold">Quizzes</h2>
        <p className="text-sm text-muted-foreground">{courseName}</p>
      </div>
      <Button onClick={onGenerate}>
        <Plus className="mr-2 h-4 w-4" />
        Generate Quiz
      </Button>
    </div>
  );
}
