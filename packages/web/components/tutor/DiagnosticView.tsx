"use client";

import { useState, useEffect, useRef } from "react";
import { Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import {
  startDiagnostic,
  submitDiagnostic,
  getAssessmentReadiness,
} from "@/lib/api";
import { toast } from "sonner";
import { PreDiagnosticView } from "@/components/tutor/PreDiagnosticView";
import { PostDiagnosticView } from "@/components/tutor/PostDiagnosticView";
import type {
  TutorQuestion,
  DiagnosticResult,
  AssessmentReadiness,
} from "@/types/database";

interface DiagnosticViewProps {
  sessionId: string;
  courseId: string;
  targetAssessmentId: string | null;
  onComplete: (result: DiagnosticResult) => void;
  onFillGaps?: () => void;
  onBackToCourse?: () => void;
}

export function DiagnosticView({
  sessionId,
  courseId,
  targetAssessmentId,
  onComplete,
  onFillGaps,
  onBackToCourse,
}: DiagnosticViewProps) {
  const [phase, setPhase] = useState<"pre" | "questions" | "results">("pre");
  const [readiness, setReadiness] = useState<AssessmentReadiness | null>(null);
  const [readinessLoading, setReadinessLoading] = useState(true);

  const [questions, setQuestions] = useState<TutorQuestion[]>([]);
  const [currentIdx, setCurrentIdx] = useState(0);
  const [answers, setAnswers] = useState<
    Map<string, { answer: string; time: number }>
  >(new Map());
  const [currentAnswer, setCurrentAnswer] = useState("");
  const [questionsLoading, setQuestionsLoading] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [result, setResult] = useState<DiagnosticResult | null>(null);
  const startTime = useRef(Date.now());

  // Fetch readiness data on mount (if we have an assessment)
  useEffect(() => {
    if (!targetAssessmentId) {
      setReadinessLoading(false);
      return;
    }
    let cancelled = false;
    async function load() {
      try {
        const data = await getAssessmentReadiness(
          courseId,
          targetAssessmentId!,
        );
        if (!cancelled) setReadiness(data);
      } catch {
        // Readiness data is optional — don't block the flow
      } finally {
        if (!cancelled) setReadinessLoading(false);
      }
    }
    load();
    return () => {
      cancelled = true;
    };
  }, [courseId, targetAssessmentId]);

  // Reset question timer when navigating between questions
  useEffect(() => {
    startTime.current = Date.now();
    setCurrentAnswer("");
  }, [currentIdx]);

  async function handleBeginDiagnostic() {
    setQuestionsLoading(true);
    try {
      const { questions: qs } = await startDiagnostic(sessionId);
      setQuestions(qs);
      setPhase("questions");
    } catch {
      toast.error("Failed to load diagnostic questions");
    } finally {
      setQuestionsLoading(false);
    }
  }

  function saveAndAdvance() {
    const q = questions[currentIdx];
    if (!q || !currentAnswer.trim()) return;
    const elapsed = Math.round((Date.now() - startTime.current) / 1000);
    setAnswers((prev) => {
      const next = new Map(prev);
      next.set(q.question_id, { answer: currentAnswer, time: elapsed });
      return next;
    });
    if (currentIdx < questions.length - 1) {
      setCurrentIdx((i) => i + 1);
    }
  }

  async function handleSubmitAll() {
    const q = questions[currentIdx];
    // Save current answer first
    if (q && currentAnswer.trim()) {
      const elapsed = Math.round((Date.now() - startTime.current) / 1000);
      answers.set(q.question_id, { answer: currentAnswer, time: elapsed });
    }

    const payload = questions.map((question) => {
      const a = answers.get(question.question_id);
      return {
        question_id: question.question_id,
        question,
        student_answer: a?.answer ?? "",
        time_spent_seconds: a?.time ?? 0,
      };
    });

    setSubmitting(true);
    try {
      const res = await submitDiagnostic(sessionId, payload);
      setResult(res);
      onComplete(res);

      // Re-fetch readiness after submitting (mastery may have changed)
      if (targetAssessmentId) {
        setReadinessLoading(true);
        try {
          const updated = await getAssessmentReadiness(
            courseId,
            targetAssessmentId,
          );
          setReadiness(updated);
        } catch {
          // Not critical
        } finally {
          setReadinessLoading(false);
        }
      }

      setPhase("results");
    } catch {
      toast.error("Failed to submit diagnostic");
    } finally {
      setSubmitting(false);
    }
  }

  // --- Phase: Pre-diagnostic ---
  if (phase === "pre") {
    return (
      <PreDiagnosticView
        readiness={readiness}
        loading={readinessLoading}
        onBegin={handleBeginDiagnostic}
        beginning={questionsLoading}
      />
    );
  }

  // --- Phase: Results ---
  if (phase === "results" && result) {
    return (
      <PostDiagnosticView
        diagnosticResult={result}
        readiness={readiness}
        readinessLoading={readinessLoading}
        onFillGaps={onFillGaps}
        onBackToCourse={onBackToCourse}
      />
    );
  }

  // --- Phase: Questions ---
  if (questionsLoading || questions.length === 0) {
    return (
      <div className="flex items-center justify-center py-12">
        <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
      </div>
    );
  }

  const q = questions[currentIdx];
  if (!q) return null;

  const isLast = currentIdx === questions.length - 1;
  const progressPct = ((currentIdx + 1) / questions.length) * 100;

  return (
    <div className="space-y-6 max-w-2xl mx-auto">
      <div className="space-y-2">
        <div className="flex items-center justify-between text-sm text-muted-foreground">
          <span>
            Question {currentIdx + 1} of {questions.length}
          </span>
          {q.concept_title && (
            <Badge variant="secondary" className="text-[10px]">
              {q.concept_title}
            </Badge>
          )}
        </div>
        <Progress value={progressPct} className="h-1.5" />
      </div>

      <p className="text-base font-medium leading-relaxed">
        {q.question_text}
      </p>

      {/* MCQ */}
      {q.question_type === "mcq" && q.options && (
        <div className="space-y-2">
          {q.options.map((opt, i) => {
            const label = String.fromCharCode(65 + i);
            const selected = currentAnswer === label;
            return (
              <button
                key={i}
                onClick={() => setCurrentAnswer(label)}
                className={cn(
                  "flex w-full items-center gap-3 rounded-lg border p-3 text-left text-sm transition-colors",
                  selected
                    ? "border-primary bg-primary/5"
                    : "border-border hover:bg-muted/50",
                )}
              >
                <span
                  className={cn(
                    "flex h-6 w-6 shrink-0 items-center justify-center rounded-full border text-xs font-medium",
                    selected
                      ? "border-primary bg-primary text-primary-foreground"
                      : "border-muted-foreground/30",
                  )}
                >
                  {label}
                </span>
                <span>{opt}</span>
              </button>
            );
          })}
        </div>
      )}

      {/* True/False */}
      {q.question_type === "true_false" && (
        <div className="flex gap-3">
          {["True", "False"].map((opt) => (
            <button
              key={opt}
              onClick={() => setCurrentAnswer(opt)}
              className={cn(
                "flex-1 rounded-lg border p-3 text-center text-sm font-medium transition-colors",
                currentAnswer === opt
                  ? "border-primary bg-primary/5"
                  : "border-border hover:bg-muted/50",
              )}
            >
              {opt}
            </button>
          ))}
        </div>
      )}

      {/* Short answer / fill-in-blank */}
      {(q.question_type === "short_answer" ||
        q.question_type === "fill_in_blank") && (
        <textarea
          value={currentAnswer}
          onChange={(e) => setCurrentAnswer(e.target.value)}
          placeholder="Type your answer..."
          rows={q.question_type === "fill_in_blank" ? 1 : 3}
          className="w-full resize-none rounded-md border bg-background px-3 py-2 text-sm"
        />
      )}

      <div className="flex items-center justify-between">
        <Button
          variant="outline"
          size="sm"
          onClick={() => setCurrentIdx((i) => Math.max(0, i - 1))}
          disabled={currentIdx === 0}
        >
          Previous
        </Button>
        {isLast ? (
          <Button onClick={handleSubmitAll} disabled={submitting} size="sm">
            {submitting && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
            Submit Diagnostic
          </Button>
        ) : (
          <Button
            onClick={saveAndAdvance}
            disabled={!currentAnswer.trim()}
            size="sm"
          >
            Next
          </Button>
        )}
      </div>
    </div>
  );
}
