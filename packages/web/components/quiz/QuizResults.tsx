"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import {
  Trophy,
  ChevronDown,
  ChevronUp,
  Check,
  X,
  RotateCcw,
  Plus,
  ArrowLeft,
} from "lucide-react";

import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardHeader,
} from "@/components/ui/card";
import { CodeFeedback } from "@/components/quiz/CodeFeedback";
import { cn } from "@/lib/utils";
import type { QuizSubmissionResult, QuestionResult } from "@/types/database";

type Filter = "all" | "incorrect" | "correct";

interface QuizResultsProps {
  result: QuizSubmissionResult;
  courseId: string;
  quizId: string;
}

export function QuizResults({ result, courseId, quizId }: QuizResultsProps) {
  const router = useRouter();
  const [filter, setFilter] = useState<Filter>("all");
  const [expandedIds, setExpandedIds] = useState<Set<string>>(new Set());

  const filtered = result.results.filter((q) => {
    if (filter === "incorrect") return !q.is_correct;
    if (filter === "correct") return q.is_correct;
    return true;
  });

  function toggleExpand(id: string) {
    setExpandedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  return (
    <div className="space-y-6">
      {/* Score card */}
      <Card>
        <CardContent className="pt-6">
          <div className="flex flex-col items-center text-center space-y-2">
            <Trophy className="h-8 w-8 text-yellow-500" />
            <p className="text-sm text-muted-foreground">Your Score</p>
            <p className="text-5xl font-bold">{Math.round(result.score)}%</p>
            <p className="text-sm text-muted-foreground">
              {result.correct_count} of {result.total_questions} correct
            </p>
          </div>
        </CardContent>
      </Card>

      {/* Filter buttons */}
      <div className="flex gap-2">
        {(["all", "incorrect", "correct"] as Filter[]).map((f) => (
          <Button
            key={f}
            variant={filter === f ? "default" : "outline"}
            size="sm"
            onClick={() => setFilter(f)}
          >
            {f === "all"
              ? "All"
              : f === "incorrect"
                ? "Incorrect only"
                : "Correct only"}
          </Button>
        ))}
      </div>

      {/* Per-question review */}
      <div className="space-y-2">
        {filtered.map((q, idx) => (
          <QuestionReviewItem
            key={q.question_id}
            question={q}
            questionNumber={idx + 1}
            expanded={expandedIds.has(q.question_id)}
            onToggle={() => toggleExpand(q.question_id)}
          />
        ))}
        {filtered.length === 0 && (
          <p className="text-sm text-muted-foreground text-center py-8">
            No questions match this filter.
          </p>
        )}
      </div>

      {/* Action buttons */}
      <div className="flex flex-wrap gap-2">
        <Button
          onClick={() =>
            router.push(`/dashboard/courses/${courseId}/quiz/${quizId}?retake=1`)
          }
        >
          <RotateCcw className="mr-2 h-4 w-4" />
          Retake Quiz
        </Button>
        <Button
          variant="outline"
          onClick={() =>
            router.push(
              `/dashboard/courses/${courseId}/quizzes?generate=1`,
            )
          }
        >
          <Plus className="mr-2 h-4 w-4" />
          Generate New Quiz
        </Button>
        <Button
          variant="outline"
          onClick={() =>
            router.push(`/dashboard/courses/${courseId}/quizzes`)
          }
        >
          <ArrowLeft className="mr-2 h-4 w-4" />
          Back to Quizzes
        </Button>
      </div>
    </div>
  );
}

function QuestionReviewItem({
  question,
  questionNumber,
  expanded,
  onToggle,
}: {
  question: QuestionResult;
  questionNumber: number;
  expanded: boolean;
  onToggle: () => void;
}) {
  const questionText = question.question_text ?? "";

  return (
    <Card>
      <button
        onClick={onToggle}
        className="w-full text-left"
      >
        <CardHeader className="py-3 px-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              {question.is_correct ? (
                <Check className="h-4 w-4 text-green-600 shrink-0" />
              ) : (
                <X className="h-4 w-4 text-red-600 shrink-0" />
              )}
              <span className="text-sm font-medium">
                Q{questionNumber}.
              </span>
              <span className="text-sm truncate">
                {questionText.length > 80
                  ? questionText.slice(0, 80) + "..."
                  : questionText}
              </span>
            </div>
            {expanded ? (
              <ChevronUp className="h-4 w-4 shrink-0 text-muted-foreground" />
            ) : (
              <ChevronDown className="h-4 w-4 shrink-0 text-muted-foreground" />
            )}
          </div>
        </CardHeader>
      </button>
      {expanded && (
        <CardContent className="pt-0 px-4 pb-4 space-y-3">
          {questionText && <p className="text-sm">{questionText}</p>}

          {question.options && (
            <div className="space-y-1">
              {question.options.map((opt, i) => (
                <div
                  key={i}
                  className={cn(
                    "text-sm px-3 py-1.5 rounded",
                    opt === question.correct_answer && "bg-green-50 text-green-700 font-medium",
                    opt === question.student_answer &&
                      opt !== question.correct_answer &&
                      "bg-red-50 text-red-700 line-through",
                  )}
                >
                  {String.fromCharCode(65 + i)}) {opt}
                  {opt === question.correct_answer && " \u2713"}
                  {opt === question.student_answer &&
                    opt !== question.correct_answer &&
                    " (your answer)"}
                </div>
              ))}
            </div>
          )}

          {!question.options && !question.code_grading_result && (
            <div className="space-y-1 text-sm">
              <div
                className={cn(
                  "px-3 py-1.5 rounded",
                  question.is_correct
                    ? "bg-green-50 text-green-700"
                    : "bg-red-50 text-red-700",
                )}
              >
                Your answer: {question.student_answer || "(skipped)"}
              </div>
              {!question.is_correct && (
                <div className="px-3 py-1.5 rounded bg-green-50 text-green-700">
                  Correct answer: {question.correct_answer}
                </div>
              )}
            </div>
          )}

          {question.code_grading_result && (
            <CodeFeedback
              result={question.code_grading_result}
              showReference={true}
            />
          )}

          {question.explanation && !question.code_grading_result && (
            <p className="text-sm text-muted-foreground">
              {question.explanation}
            </p>
          )}
        </CardContent>
      )}
    </Card>
  );
}
