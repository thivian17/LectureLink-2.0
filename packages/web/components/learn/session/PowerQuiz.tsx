"use client";

import { useState, useRef, useEffect } from "react";
import { CheckCircle2, XCircle } from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { cn } from "@/lib/utils";
import { ComboDisplay } from "./ComboDisplay";
import { XPPopup } from "./XPPopup";
import { submitLearnQuizAnswer } from "@/lib/api";
import type { PowerQuizQuestion, QuizAnswerResult } from "@/types/database";

interface PowerQuizProps {
  sessionId: string;
  questions: PowerQuizQuestion[];
  onComplete: () => void;
}

export function PowerQuiz({ sessionId, questions, onComplete }: PowerQuizProps) {
  const [currentIndex, setCurrentIndex] = useState(0);
  const [selectedAnswer, setSelectedAnswer] = useState<number | null>(null);
  const [result, setResult] = useState<QuizAnswerResult | null>(null);
  const [combo, setCombo] = useState(0);
  const [xpAmount, setXpAmount] = useState(0);
  const [xpTrigger, setXpTrigger] = useState(0);
  const startTime = useRef(0);
  const [elapsed, setElapsed] = useState(0);
  const [showingSummary, setShowingSummary] = useState(false);
  const [quizStats, setQuizStats] = useState({ correct: 0, total: 0, xpTotal: 0 });

  const question = questions[currentIndex];

  useEffect(() => {
    startTime.current = Date.now();
    setSelectedAnswer(null);
    setResult(null);
    setElapsed(0);
  }, [currentIndex]);

  useEffect(() => {
    const timer = setInterval(() => {
      setElapsed(Math.floor((Date.now() - startTime.current) / 1000));
    }, 1000);
    return () => clearInterval(timer);
  }, [currentIndex]);

  if (showingSummary) {
    return (
      <div className="max-w-lg mx-auto text-center py-12 space-y-4 animate-in fade-in zoom-in-95 duration-300">
        <div className="text-5xl">🎯</div>
        <h3 className="text-xl font-bold">Quiz Complete!</h3>
        <p className="text-2xl font-bold text-primary">
          {quizStats.correct}/{quizStats.total} correct
        </p>
        <p className="text-sm text-muted-foreground">+{quizStats.xpTotal} XP earned</p>
      </div>
    );
  }

  if (!question) {
    onComplete();
    return null;
  }

  async function handleSelect(index: number) {
    if (selectedAnswer !== null) return;
    setSelectedAnswer(index);
    // eslint-disable-next-line react-hooks/purity
    const timeMs = Math.round(Date.now() - startTime.current); // event handler, not render

    try {
      const res = await submitLearnQuizAnswer(sessionId, question.question_id, index, timeMs);
      setResult(res);
      setCombo(res.combo_count);
      setXpAmount(res.xp_earned);
      setXpTrigger((t) => t + 1);
      setQuizStats((prev) => ({
        correct: prev.correct + (res.correct ? 1 : 0),
        total: prev.total + 1,
        xpTotal: prev.xpTotal + res.xp_earned,
      }));
    } catch {
      setResult(null);
    }
  }

  function handleNext() {
    if (currentIndex >= questions.length - 1) {
      setShowingSummary(true);
      setTimeout(() => onComplete(), 2500);
      return;
    }
    setCurrentIndex((i) => i + 1);
  }

  const progressPct = ((currentIndex + 1) / questions.length) * 100;
  const mins = Math.floor(elapsed / 60);
  const secs = elapsed % 60;
  const timerBarWidth = Math.max(0, 100 - (elapsed / 60) * 100);

  return (
    <div className="max-w-lg mx-auto space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between text-sm">
        <span className="text-muted-foreground">
          Question {currentIndex + 1} of {questions.length}
        </span>
        <div className="flex items-center gap-3">
          <div className={cn("relative", combo >= 3 && "animate-pulse")}>
            <ComboDisplay combo={combo} />
            {combo >= 3 && (
              <span className="absolute -top-2 -right-2 text-sm animate-bounce">
                🔥
              </span>
            )}
          </div>
          <span className="text-muted-foreground tabular-nums">
            {mins}:{String(secs).padStart(2, "0")}
          </span>
        </div>
      </div>
      <Progress value={progressPct} className="h-1.5" />

      {/* Question card with transition */}
      <div
        key={currentIndex}
        className="animate-in fade-in slide-in-from-right-2 duration-200"
      >
        <Card className="relative overflow-hidden">
          <XPPopup xp={xpAmount} trigger={xpTrigger} />
          <CardContent className="p-5 space-y-4">
            {/* Timer bar */}
            <div className="h-1 w-full bg-muted rounded-full overflow-hidden mb-3">
              <div
                className="h-full bg-primary/40 rounded-full transition-all ease-linear"
                style={{
                  width: `${timerBarWidth}%`,
                  transitionDuration: "1s",
                }}
              />
            </div>

            <p className="text-xs text-muted-foreground">{question.concept_title}</p>
            <p className="text-base font-medium">{question.question_text}</p>
            <div className="space-y-2">
              {question.options.map((option, i) => {
                const isSelected = selectedAnswer === i;
                const showResult = result !== null;
                const isCorrectOption = showResult && result.correct_answer === option;

                return (
                  <button
                    key={i}
                    onClick={() => handleSelect(i)}
                    disabled={selectedAnswer !== null}
                    className={cn(
                      "w-full text-left rounded-lg border p-3 text-sm transition-all duration-200",
                      selectedAnswer === null &&
                        "hover:border-primary/50 hover:bg-muted/50 cursor-pointer",
                      showResult && isCorrectOption &&
                        "border-green-500 bg-green-50 text-green-800",
                      showResult && isSelected && !isCorrectOption &&
                        "border-red-500 bg-red-50 text-red-800",
                      showResult && !isSelected && !isCorrectOption &&
                        "opacity-50",
                    )}
                  >
                    {option}
                  </button>
                );
              })}
            </div>

            {/* Feedback */}
            {result && (
              <div
                className={cn(
                  "rounded-lg p-3 text-sm transition-all duration-300",
                  result.correct
                    ? "bg-green-50 border border-green-200"
                    : "bg-red-50 border border-red-200",
                )}
              >
                <div className="flex items-center gap-1.5 mb-1 font-medium">
                  {result.correct ? (
                    <><CheckCircle2 className="h-4 w-4 text-green-600" /> Correct!</>
                  ) : (
                    <><XCircle className="h-4 w-4 text-red-600" /> Incorrect</>
                  )}
                </div>
                <p className="text-muted-foreground">{result.explanation}</p>
                {result.source_citation && (
                  <p className="text-xs text-muted-foreground mt-1 italic">
                    Source: {result.source_citation}
                  </p>
                )}
              </div>
            )}

            {result && (
              <button
                onClick={handleNext}
                className="w-full rounded-lg bg-primary text-primary-foreground py-2.5 text-sm font-medium hover:bg-primary/90 transition-colors"
              >
                {currentIndex < questions.length - 1 ? "Next Question" : "Finish Quiz"}
              </button>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
