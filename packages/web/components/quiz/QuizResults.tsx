"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import {
  Trophy,
  Clock,
  ChevronDown,
  ChevronUp,
  Check,
  X,
  BookOpen,
  RotateCcw,
  Plus,
  ArrowLeft,
} from "lucide-react";

import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { ConceptPerformance } from "@/components/quiz/ConceptPerformance";
import { cn } from "@/lib/utils";
import type { QuizSubmissionResult, QuestionResult } from "@/types/database";

function formatTime(seconds: number): string {
  const m = Math.floor(seconds / 60);
  const s = seconds % 60;
  return `${m}:${String(s).padStart(2, "0")}`;
}

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

  const filtered = result.per_question.filter((q) => {
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
            <p className="text-5xl font-bold">{result.score}%</p>
            <p className="text-sm text-muted-foreground">
              {result.correct_count} of {result.total_questions} correct
            </p>
            <div className="flex gap-6 pt-2 text-sm text-muted-foreground">
              <span className="flex items-center gap-1">
                <Clock className="h-4 w-4" />
                {formatTime(result.time_total_seconds)}
              </span>
              <span>Attempt #{result.attempt_number}</span>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Concept performance */}
      <Card>
        <CardContent className="pt-6">
          <ConceptPerformance concepts={result.concept_performance} />
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
        {filtered.map((q) => (
          <QuestionReviewItem
            key={q.question_id}
            question={q}
            expanded={expandedIds.has(q.question_id)}
            onToggle={() => toggleExpand(q.question_id)}
            courseId={courseId}
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
  expanded,
  onToggle,
  courseId,
}: {
  question: QuestionResult;
  expanded: boolean;
  onToggle: () => void;
  courseId: string;
}) {
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
                Q{question.question_number}.
              </span>
              <span className="text-sm truncate">
                {question.question_text.length > 80
                  ? question.question_text.slice(0, 80) + "..."
                  : question.question_text}
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
          <p className="text-sm">{question.question_text}</p>

          {question.options && (
            <div className="space-y-1">
              {question.options.map((opt, i) => (
                <div
                  key={i}
                  className={cn(
                    "text-sm px-3 py-1.5 rounded",
                    opt === question.correct_answer && "bg-green-50 text-green-700 font-medium",
                    opt === question.selected_answer &&
                      opt !== question.correct_answer &&
                      "bg-red-50 text-red-700 line-through",
                  )}
                >
                  {String.fromCharCode(65 + i)}) {opt}
                  {opt === question.correct_answer && " ✓"}
                  {opt === question.selected_answer &&
                    opt !== question.correct_answer &&
                    " (your answer)"}
                </div>
              ))}
            </div>
          )}

          {!question.options && (
            <div className="space-y-1 text-sm">
              <div
                className={cn(
                  "px-3 py-1.5 rounded",
                  question.is_correct
                    ? "bg-green-50 text-green-700"
                    : "bg-red-50 text-red-700",
                )}
              >
                Your answer: {question.selected_answer ?? "(skipped)"}
              </div>
              {!question.is_correct && (
                <div className="px-3 py-1.5 rounded bg-green-50 text-green-700">
                  Correct answer: {question.correct_answer}
                </div>
              )}
            </div>
          )}

          <p className="text-sm text-muted-foreground">
            {question.explanation}
          </p>

          <div className="flex items-center gap-3">
            {question.concept && (
              <Badge variant="secondary" className="text-xs">
                {question.concept}
              </Badge>
            )}
            {question.source_lecture_id && question.source_lecture_title && (
              <a
                href={`/dashboard/courses/${courseId}/lectures/${question.source_lecture_id}${
                  question.source_timestamp_seconds != null
                    ? `?t=${question.source_timestamp_seconds}`
                    : ""
                }`}
                className="inline-flex items-center gap-1 text-xs text-primary hover:underline"
              >
                <BookOpen className="h-3 w-3" />
                {question.source_lecture_title}
                {question.source_timestamp_seconds != null &&
                  ` at ${Math.floor(question.source_timestamp_seconds / 60)}:${String(question.source_timestamp_seconds % 60).padStart(2, "0")}`}
              </a>
            )}
          </div>
        </CardContent>
      )}
    </Card>
  );
}
