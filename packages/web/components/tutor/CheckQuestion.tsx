"use client";

import { useState, useEffect, useRef } from "react";
import { Loader2, GripVertical } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import { submitTutorAnswer } from "@/lib/api";
import { FeedbackBlock } from "@/components/tutor/FeedbackBlock";
import type { TutorQuestion, GradingResult, TutorQuestionType } from "@/types/database";

interface CheckQuestionProps {
  question: TutorQuestion;
  sessionId: string;
  onAnswered: (result: GradingResult) => void;
  disabled?: boolean;
}

export function CheckQuestion({
  question,
  sessionId,
  onAnswered,
  disabled,
}: CheckQuestionProps) {
  const [answer, setAnswer] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [result, setResult] = useState<GradingResult | null>(null);
  const startTime = useRef(Date.now());
  const [orderItems, setOrderItems] = useState<string[]>([]);
  const [dragIdx, setDragIdx] = useState<number | null>(null);

  useEffect(() => {
    startTime.current = Date.now();
    setAnswer("");
    setResult(null);
    if (
      question.question_type === "ordering" &&
      question.options
    ) {
      setOrderItems([...question.options]);
    }
  }, [question.question_id, question.question_type, question.options]);

  async function handleSubmit() {
    const elapsed = Math.round((Date.now() - startTime.current) / 1000);
    const studentAnswer =
      question.question_type === "ordering"
        ? orderItems.join(" → ")
        : answer;

    setSubmitting(true);
    try {
      const res = await submitTutorAnswer(sessionId, {
        question_id: question.question_id,
        student_answer: studentAnswer,
        time_spent_seconds: elapsed,
      });
      setResult(res);
      onAnswered(res);
    } catch {
      // Error is handled by fetchWithAuth
    } finally {
      setSubmitting(false);
    }
  }

  const hasAnswer =
    question.question_type === "ordering"
      ? orderItems.length > 0
      : answer.trim().length > 0;

  function handleDragOver(e: React.DragEvent, targetIdx: number) {
    e.preventDefault();
    if (dragIdx == null || dragIdx === targetIdx) return;
    setOrderItems((prev) => {
      const next = [...prev];
      const [moved] = next.splice(dragIdx, 1);
      next.splice(targetIdx, 0, moved);
      return next;
    });
    setDragIdx(targetIdx);
  }

  return (
    <div className="space-y-4">
      <div className="space-y-2">
        <p className="text-sm font-medium leading-relaxed">
          {question.question_text}
        </p>
        {question.concept_title && (
          <Badge variant="secondary" className="text-[10px]">
            {question.concept_title}
          </Badge>
        )}
        {question.question_type === "long_answer" && (
          <Badge variant="outline" className="text-[10px]">
            AI-Graded (Beta)
          </Badge>
        )}
      </div>

      {/* MCQ */}
      {question.question_type === "mcq" && question.options && (
        <div className="space-y-2">
          {question.options.map((opt, i) => {
            const label = String.fromCharCode(65 + i);
            const selected = answer === label;
            return (
              <button
                key={i}
                onClick={() => !result && setAnswer(label)}
                disabled={!!result || disabled}
                className={cn(
                  "flex w-full items-center gap-3 rounded-lg border p-3 text-left text-sm transition-colors",
                  selected
                    ? "border-primary bg-primary/5"
                    : "border-border hover:bg-muted/50",
                  (result || disabled) && "cursor-default opacity-80",
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
      {question.question_type === "true_false" && (
        <div className="flex gap-3">
          {["True", "False"].map((opt) => (
            <button
              key={opt}
              onClick={() => !result && setAnswer(opt)}
              disabled={!!result || disabled}
              className={cn(
                "flex-1 rounded-lg border p-3 text-center text-sm font-medium transition-colors",
                answer === opt
                  ? "border-primary bg-primary/5"
                  : "border-border hover:bg-muted/50",
                (result || disabled) && "cursor-default opacity-80",
              )}
            >
              {opt}
            </button>
          ))}
        </div>
      )}

      {/* Fill-in-blank */}
      {question.question_type === "fill_in_blank" && (
        <input
          type="text"
          value={answer}
          onChange={(e) => setAnswer(e.target.value)}
          placeholder="Type your answer..."
          disabled={!!result || disabled}
          className="w-full rounded-md border bg-background px-3 py-2 text-sm"
        />
      )}

      {/* Short answer */}
      {question.question_type === "short_answer" && (
        <textarea
          value={answer}
          onChange={(e) => setAnswer(e.target.value)}
          placeholder="Type your answer..."
          rows={3}
          disabled={!!result || disabled}
          className="w-full resize-none rounded-md border bg-background px-3 py-2 text-sm"
        />
      )}

      {/* Long answer */}
      {question.question_type === "long_answer" && (
        <div className="space-y-1">
          <textarea
            value={answer}
            onChange={(e) => setAnswer(e.target.value)}
            placeholder="Write your detailed answer..."
            rows={6}
            disabled={!!result || disabled}
            className="w-full resize-y rounded-md border bg-background px-3 py-2 text-sm"
          />
          <p className="text-xs text-muted-foreground text-right">
            {answer.split(/\s+/).filter(Boolean).length} words
          </p>
        </div>
      )}

      {/* Ordering */}
      {question.question_type === "ordering" && (
        <div className="space-y-1">
          {orderItems.map((item, i) => (
            <div
              key={`${item}-${i}`}
              draggable={!result && !disabled}
              onDragStart={() => setDragIdx(i)}
              onDragOver={(e) => handleDragOver(e, i)}
              onDragEnd={() => setDragIdx(null)}
              className={cn(
                "flex items-center gap-2 rounded-md border bg-background px-3 py-2 text-sm",
                dragIdx === i && "opacity-50",
                !result && !disabled && "cursor-grab active:cursor-grabbing",
              )}
            >
              <GripVertical className="h-4 w-4 shrink-0 text-muted-foreground" />
              <span className="text-xs text-muted-foreground font-medium w-5">
                {i + 1}.
              </span>
              {item}
            </div>
          ))}
        </div>
      )}

      {/* Submit button */}
      {!result && (
        <Button
          onClick={handleSubmit}
          disabled={!hasAnswer || submitting || disabled}
          size="sm"
        >
          {submitting && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
          Submit Answer
        </Button>
      )}

      {/* Feedback */}
      {result && (
        <FeedbackBlock
          result={result}
          sessionId={sessionId}
          eventId={question.question_id}
        />
      )}
    </div>
  );
}
