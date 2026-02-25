"use client";

import { useState, useCallback, useEffect } from "react";
import { Lightbulb, Play, Loader2, ChevronDown, ChevronUp } from "lucide-react";
import { toast } from "sonner";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible";
import { CodeEditor } from "@/components/quiz/CodeEditor";
import { CodeFeedback } from "@/components/quiz/CodeFeedback";
import { getHint, AuthError, RateLimitError } from "@/lib/api";
import type { QuizQuestion, CodeGradingResult } from "@/types/database";

interface CodeQuestionProps {
  question: QuizQuestion;
  quizId: string;
  selectedAnswer: string | null;
  onAnswer: (answer: string) => void;
  showFeedback: boolean;
  gradingResult?: CodeGradingResult;
  isSubmitting?: boolean;
  timeElapsed?: number;
}

const TYPE_LABELS: Record<string, string> = {
  code_writing: "Code Writing",
  code_fix: "Bug Fix",
  code_explain: "Code Analysis",
};

export function CodeQuestion({
  question,
  quizId,
  selectedAnswer,
  onAnswer,
  showFeedback,
  gradingResult,
  isSubmitting = false,
  timeElapsed = 0,
}: CodeQuestionProps) {
  const meta = question.code_metadata;
  const isExplainType = question.question_type === "code_explain";

  const [currentCode, setCurrentCode] = useState(
    isExplainType ? meta?.starter_code ?? "" : selectedAnswer ?? meta?.starter_code ?? "",
  );
  const [explanation, setExplanation] = useState(
    isExplainType ? selectedAnswer ?? "" : "",
  );
  const [revealedHints, setRevealedHints] = useState<string[]>([]);
  const [nextHintIndex, setNextHintIndex] = useState(0);
  const [loadingHint, setLoadingHint] = useState(false);
  const [hintsRemaining, setHintsRemaining] = useState(
    meta?.hints.length ?? 0,
  );
  const [hintsOpen, setHintsOpen] = useState(false);

  // Reset state when question changes
  useEffect(() => {
    const newMeta = question.code_metadata;
    const explain = question.question_type === "code_explain";
    setCurrentCode(
      explain ? newMeta?.starter_code ?? "" : selectedAnswer ?? newMeta?.starter_code ?? "",
    );
    setExplanation(explain ? selectedAnswer ?? "" : "");
    setRevealedHints([]);
    setNextHintIndex(0);
    setHintsRemaining(newMeta?.hints.length ?? 0);
    setHintsOpen(false);
  }, [question.id]); // eslint-disable-line react-hooks/exhaustive-deps

  const formatTime = useCallback((seconds: number): string => {
    const m = Math.floor(seconds / 60);
    const s = seconds % 60;
    return `${m}:${String(s).padStart(2, "0")}`;
  }, []);

  async function handleRequestHint() {
    if (!meta || loadingHint) return;
    setLoadingHint(true);
    try {
      const resp = await getHint(quizId, question.id, nextHintIndex);
      setRevealedHints((prev) => [...prev, resp.hint]);
      setNextHintIndex(resp.hint_index + 1);
      setHintsRemaining(resp.hints_remaining);
      setHintsOpen(true);
    } catch (err) {
      if (err instanceof AuthError) {
        toast.error("Session expired. Please log in again.");
        return;
      }
      if (err instanceof RateLimitError) {
        toast.error(
          `Rate limit reached. Try again in ${Math.ceil(err.retryAfterSeconds / 60)} min.`,
        );
        return;
      }
      toast.error(
        err instanceof Error ? err.message : "Failed to get hint",
      );
    } finally {
      setLoadingHint(false);
    }
  }

  function handleSubmit() {
    if (question.question_type === "code_explain") {
      onAnswer(explanation);
    } else {
      onAnswer(currentCode);
    }
  }

  if (!meta) {
    return (
      <p className="text-sm text-muted-foreground">
        Missing code metadata for this question.
      </p>
    );
  }

  return (
    <div className="space-y-5">
      {/* Question header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Badge variant="secondary">
            {TYPE_LABELS[question.question_type] ?? question.question_type}
          </Badge>
          <Badge variant="outline" className="text-xs">
            {meta.language}
          </Badge>
        </div>
        {meta.time_limit_minutes > 0 && (
          <span className="text-sm text-muted-foreground tabular-nums">
            {formatTime(timeElapsed)}
            {" / "}
            {meta.time_limit_minutes}m
          </span>
        )}
      </div>

      {/* Problem description */}
      <div className="space-y-2">
        <p className="text-base leading-relaxed whitespace-pre-wrap">
          {question.question_text}
        </p>
        {question.concept && (
          <Badge variant="secondary" className="text-xs">
            {question.concept}
          </Badge>
        )}
      </div>

      {/* Example I/O (for code_writing) */}
      {question.question_type === "code_writing" &&
        meta.example_inputs_outputs.length > 0 && (
          <Card>
            <CardContent className="py-3 px-4">
              <p className="text-sm font-medium mb-2">Examples</p>
              <div className="space-y-2">
                {meta.example_inputs_outputs.map((ex, i) => (
                  <div
                    key={i}
                    className="grid grid-cols-2 gap-3 text-sm font-mono"
                  >
                    <div className="rounded bg-muted px-3 py-2">
                      <span className="text-xs text-muted-foreground block mb-0.5">
                        Input
                      </span>
                      <pre className="whitespace-pre-wrap">{ex.input}</pre>
                    </div>
                    <div className="rounded bg-muted px-3 py-2">
                      <span className="text-xs text-muted-foreground block mb-0.5">
                        Expected
                      </span>
                      <pre className="whitespace-pre-wrap">{ex.expected}</pre>
                    </div>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        )}

      {/* Code editor — key forces remount so defaultValue picks up new starter code */}
      <CodeEditor
        key={question.id}
        language={meta.language}
        initialCode={isExplainType ? meta.starter_code : currentCode}
        maxLines={meta.max_lines > 0 ? meta.max_lines : undefined}
        readOnly={isExplainType || showFeedback}
        onChange={isExplainType ? undefined : setCurrentCode}
        lineAnnotations={
          showFeedback && gradingResult
            ? gradingResult.line_feedback
            : undefined
        }
      />

      {/* Text area for code_explain */}
      {isExplainType && (
        <div className="space-y-1">
          <label
            htmlFor="code-explanation"
            className="text-sm font-medium"
          >
            Your explanation
          </label>
          <textarea
            id="code-explanation"
            className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm resize-y min-h-[100px] focus:outline-none focus:ring-2 focus:ring-ring"
            placeholder="Explain what this code does..."
            value={explanation}
            onChange={(e) => setExplanation(e.target.value)}
            disabled={showFeedback}
          />
        </div>
      )}

      {/* Revealed hints */}
      {revealedHints.length > 0 && (
        <Collapsible open={hintsOpen} onOpenChange={setHintsOpen}>
          <CollapsibleTrigger asChild>
            <Button
              variant="ghost"
              size="sm"
              className="w-full justify-between text-xs"
            >
              Hints ({revealedHints.length})
              {hintsOpen ? (
                <ChevronUp className="h-3 w-3" />
              ) : (
                <ChevronDown className="h-3 w-3" />
              )}
            </Button>
          </CollapsibleTrigger>
          <CollapsibleContent>
            <div className="space-y-1.5 pt-1">
              {revealedHints.map((hint, i) => (
                <Card key={i}>
                  <CardContent className="py-2 px-3">
                    <p className="text-sm">
                      <span className="text-muted-foreground font-medium mr-1">
                        Hint {i + 1}:
                      </span>
                      {hint}
                    </p>
                  </CardContent>
                </Card>
              ))}
            </div>
          </CollapsibleContent>
        </Collapsible>
      )}

      {/* Action bar */}
      {!showFeedback && (
        <div className="flex items-center gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={handleRequestHint}
            disabled={loadingHint || hintsRemaining <= 0}
          >
            {loadingHint ? (
              <Loader2 className="mr-1 h-4 w-4 animate-spin" />
            ) : (
              <Lightbulb className="mr-1 h-4 w-4" />
            )}
            Hint ({hintsRemaining} left)
          </Button>
          <div className="flex-1" />
          <Button
            size="sm"
            onClick={handleSubmit}
            disabled={isSubmitting}
          >
            {isSubmitting ? (
              <Loader2 className="mr-1 h-4 w-4 animate-spin" />
            ) : (
              <Play className="mr-1 h-4 w-4" />
            )}
            Submit Solution
          </Button>
        </div>
      )}

      {/* Feedback panel */}
      {showFeedback && gradingResult && (
        <CodeFeedback
          result={gradingResult}
          referenceCode={meta.reference_solution}
          showReference={showFeedback}
          language={meta.language}
        />
      )}
    </div>
  );
}
