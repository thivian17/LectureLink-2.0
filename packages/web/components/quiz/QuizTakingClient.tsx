"use client";

import { useState, useEffect, useRef, useCallback } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import {
  ChevronLeft,
  ChevronRight,
  SkipForward,
  Send,
  Loader2,
} from "lucide-react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardHeader,
} from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { QuestionView } from "@/components/quiz/QuestionView";
import { QuizProgress } from "@/components/quiz/QuizProgress";
import { cn } from "@/lib/utils";
import { getQuizQuestions, submitQuiz, AuthError, RateLimitError } from "@/lib/api";
import type { QuizQuestion, QuizAnswer } from "@/types/database";

type FeedbackMode = "immediate" | "exam";

interface QuizTakingClientProps {
  courseId: string;
  quizId: string;
}

export function QuizTakingClient({
  courseId,
  quizId,
}: QuizTakingClientProps) {
  const router = useRouter();
  const searchParams = useSearchParams();
  const isRetake = searchParams.get("retake") === "1";

  const [questions, setQuestions] = useState<QuizQuestion[]>([]);
  const [loading, setLoading] = useState(true);
  const [currentIndex, setCurrentIndex] = useState(0);
  const [answers, setAnswers] = useState<Map<string, string | null>>(new Map());
  const [timers, setTimers] = useState<Map<string, number>>(new Map());
  const [feedbackMode, setFeedbackMode] = useState<FeedbackMode | null>(null);
  const [feedbackShown, setFeedbackShown] = useState<Set<string>>(new Set());
  const [submitting, setSubmitting] = useState(false);
  const [confirmOpen, setConfirmOpen] = useState(false);

  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        const data = await getQuizQuestions(quizId);
        if (cancelled) return;
        setQuestions(data);
      } catch (err) {
        if (cancelled) return;
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
        toast.error(
          err instanceof Error ? err.message : "Failed to load quiz questions",
        );
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    load();
    return () => {
      cancelled = true;
    };
  }, [quizId]);

  // Per-question timer
  useEffect(() => {
    if (questions.length === 0 || feedbackMode === null) return;
    const qId = questions[currentIndex]?.id;
    if (!qId) return;

    timerRef.current = setInterval(() => {
      setTimers((prev) => {
        const next = new Map(prev);
        next.set(qId, (next.get(qId) ?? 0) + 1);
        return next;
      });
    }, 1000);

    return () => {
      if (timerRef.current) clearInterval(timerRef.current);
    };
  }, [currentIndex, questions, feedbackMode]);

  const currentQuestion = questions[currentIndex];
  const currentAnswer = currentQuestion
    ? answers.get(currentQuestion.id) ?? null
    : null;
  const currentTime = currentQuestion
    ? timers.get(currentQuestion.id) ?? 0
    : 0;

  const answeredCount = Array.from(answers.values()).filter(
    (a) => a != null && a !== "",
  ).length;

  const allAnswered = answeredCount === questions.length;

  function handleAnswer(answer: string) {
    if (!currentQuestion) return;
    // If feedback was already shown for this question (immediate mode), don't allow changes
    if (feedbackShown.has(currentQuestion.id)) return;

    setAnswers((prev) => {
      const next = new Map(prev);
      if (answer === "" || answer === null) {
        next.delete(currentQuestion.id);
      } else {
        next.set(currentQuestion.id, answer);
      }
      return next;
    });
  }

  const handleNext = useCallback(() => {
    if (!currentQuestion) return;

    // In immediate mode, show feedback first before advancing
    if (
      feedbackMode === "immediate" &&
      !feedbackShown.has(currentQuestion.id) &&
      answers.has(currentQuestion.id)
    ) {
      setFeedbackShown((prev) => new Set(prev).add(currentQuestion.id));
      return;
    }

    if (currentIndex < questions.length - 1) {
      setCurrentIndex(currentIndex + 1);
    }
  }, [currentQuestion, feedbackMode, feedbackShown, answers, currentIndex, questions.length]);

  function handlePrevious() {
    if (currentIndex > 0) {
      setCurrentIndex(currentIndex - 1);
    }
  }

  function handleSkip() {
    if (currentIndex < questions.length - 1) {
      setCurrentIndex(currentIndex + 1);
    }
  }

  async function handleSubmit() {
    setConfirmOpen(false);
    setSubmitting(true);
    try {
      const quizAnswers: QuizAnswer[] = questions.map((q) => ({
        question_id: q.id,
        selected_answer: answers.get(q.id) ?? null,
        time_spent_seconds: timers.get(q.id) ?? 0,
      }));
      const result = await submitQuiz(quizId, quizAnswers);
      // Store result in sessionStorage for the results page
      sessionStorage.setItem(
        `quiz-result-${quizId}`,
        JSON.stringify(result),
      );
      router.push(
        `/dashboard/courses/${courseId}/quiz/${quizId}/results`,
      );
    } catch (err) {
      if (err instanceof AuthError) {
        toast.error("Session expired. Please log in again.");
        router.push("/login");
        return;
      }
      if (err instanceof RateLimitError) {
        toast.error(
          `Rate limit reached. Try again in ${Math.ceil(err.retryAfterSeconds / 60)} min.`,
        );
      } else {
        toast.error(
          err instanceof Error ? err.message : "Failed to submit quiz",
        );
      }
      setSubmitting(false);
    }
  }

  function formatTimer(seconds: number): string {
    const m = Math.floor(seconds / 60);
    const s = seconds % 60;
    return `${m}:${String(s).padStart(2, "0")}`;
  }

  // Mode selection screen
  if (feedbackMode === null && !loading && questions.length > 0) {
    return (
      <div className="flex flex-col items-center justify-center py-16 space-y-6">
        <h2 className="text-xl font-semibold">Choose your quiz mode</h2>
        <div className="grid gap-4 sm:grid-cols-2 max-w-lg w-full">
          <Card
            className="cursor-pointer transition-colors hover:border-primary"
            onClick={() => setFeedbackMode("immediate")}
          >
            <CardContent className="pt-6 text-center space-y-2">
              <p className="font-medium">Show answers as you go</p>
              <p className="text-sm text-muted-foreground">
                Get immediate feedback after each question
              </p>
            </CardContent>
          </Card>
          <Card
            className="cursor-pointer transition-colors hover:border-primary"
            onClick={() => setFeedbackMode("exam")}
          >
            <CardContent className="pt-6 text-center space-y-2">
              <p className="font-medium">Exam mode</p>
              <p className="text-sm text-muted-foreground">
                Show all answers at the end
              </p>
            </CardContent>
          </Card>
        </div>
      </div>
    );
  }

  if (loading) {
    return (
      <div className="max-w-2xl mx-auto space-y-4">
        <div className="flex items-center justify-between">
          <Skeleton className="h-5 w-32" />
          <Skeleton className="h-5 w-20" />
        </div>
        <Skeleton className="h-1.5 w-full rounded-full" />
        <Card>
          <CardHeader />
          <CardContent className="space-y-6">
            <Skeleton className="h-6 w-full" />
            <Skeleton className="h-5 w-4/5" />
            <div className="space-y-3">
              {[1, 2, 3, 4].map((i) => (
                <Skeleton key={i} className="h-12 w-full rounded-md" />
              ))}
            </div>
          </CardContent>
        </Card>
        <div className="flex items-center justify-between">
          <Skeleton className="h-9 w-24" />
          <Skeleton className="h-9 w-24" />
        </div>
      </div>
    );
  }

  if (questions.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-16 text-center">
        <p className="text-sm text-muted-foreground">No questions found.</p>
        <Button
          variant="outline"
          size="sm"
          className="mt-4"
          onClick={() =>
            router.push(`/dashboard/courses/${courseId}/quizzes`)
          }
        >
          Back to Quizzes
        </Button>
      </div>
    );
  }

  const showCurrentFeedback =
    feedbackMode === "immediate" &&
    currentQuestion != null &&
    feedbackShown.has(currentQuestion.id);

  const progressPercent = Math.round(
    ((currentIndex + 1) / questions.length) * 100,
  );

  return (
    <div className="max-w-2xl mx-auto space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="text-sm font-medium">
          Question {currentIndex + 1} of {questions.length}
        </div>
        <QuizProgress
          totalQuestions={questions.length}
          currentIndex={currentIndex}
          answers={answers}
          questionIds={questions.map((q) => q.id)}
          onNavigate={setCurrentIndex}
        />
        <div className="text-sm text-muted-foreground tabular-nums">
          {progressPercent}%
        </div>
      </div>

      {/* Progress bar */}
      <div className="h-1.5 w-full overflow-hidden rounded-full bg-muted">
        <div
          className="h-full rounded-full bg-primary transition-all duration-300"
          style={{ width: `${progressPercent}%` }}
        />
      </div>

      {/* Question card */}
      <Card>
        <CardHeader />
        <CardContent className="space-y-6">
          {currentQuestion && (
            <QuestionView
              question={currentQuestion}
              selectedAnswer={currentAnswer}
              onAnswer={handleAnswer}
              showFeedback={showCurrentFeedback}
              courseId={courseId}
            />
          )}
        </CardContent>
      </Card>

      {/* Navigation */}
      <div className="flex items-center justify-between">
        <Button
          variant="outline"
          size="sm"
          onClick={handlePrevious}
          disabled={currentIndex === 0}
        >
          <ChevronLeft className="mr-1 h-4 w-4" />
          Previous
        </Button>

        <div className="flex items-center gap-2">
          <span className="text-xs text-muted-foreground tabular-nums">
            {formatTimer(currentTime)}
          </span>

          {!showCurrentFeedback &&
            currentIndex < questions.length - 1 && (
              <Button variant="ghost" size="sm" onClick={handleSkip}>
                <SkipForward className="mr-1 h-4 w-4" />
                Skip
              </Button>
            )}

          {(allAnswered || currentIndex === questions.length - 1) && (
            <Button
              size="sm"
              variant="default"
              onClick={() => setConfirmOpen(true)}
              disabled={submitting}
            >
              <Send className="mr-1 h-4 w-4" />
              Submit Quiz
            </Button>
          )}
        </div>

        <Button
          variant="outline"
          size="sm"
          onClick={handleNext}
          disabled={
            currentIndex === questions.length - 1 && !showCurrentFeedback
          }
        >
          {showCurrentFeedback ? "Next Question" : "Next"}
          <ChevronRight className="ml-1 h-4 w-4" />
        </Button>
      </div>

      {/* Submit confirmation dialog */}
      <Dialog open={confirmOpen} onOpenChange={setConfirmOpen}>
        <DialogContent className="sm:max-w-sm">
          <DialogHeader>
            <DialogTitle>Submit Quiz?</DialogTitle>
            <DialogDescription>
              You answered {answeredCount} of {questions.length} questions.
              {answeredCount < questions.length && (
                <span className="block mt-1 text-yellow-600">
                  {questions.length - answeredCount} question
                  {questions.length - answeredCount !== 1 ? "s" : ""} unanswered.
                </span>
              )}
            </DialogDescription>
          </DialogHeader>
          <div className="flex justify-end gap-2 pt-2">
            <Button
              variant="outline"
              onClick={() => setConfirmOpen(false)}
            >
              Cancel
            </Button>
            <Button onClick={handleSubmit} disabled={submitting}>
              {submitting && (
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              )}
              Submit
            </Button>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}
