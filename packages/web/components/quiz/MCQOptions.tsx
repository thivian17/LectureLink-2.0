"use client";

import { Check } from "lucide-react";
import { cn } from "@/lib/utils";

const LABELS = ["A", "B", "C", "D"];

interface MCQOptionsProps {
  options: string[];
  selectedAnswer: string | null;
  onSelect: (answer: string) => void;
  disabled?: boolean;
  correctAnswer?: string;
  correctOptionIndex?: number | null;
  showFeedback?: boolean;
}

export function MCQOptions({
  options,
  selectedAnswer,
  onSelect,
  disabled,
  correctAnswer,
  correctOptionIndex,
  showFeedback,
}: MCQOptionsProps) {
  return (
    <div className="space-y-3">
      {options.map((option, i) => {
        const isSelected = selectedAnswer === option;
        const isCorrectOption =
          correctOptionIndex != null
            ? i === correctOptionIndex
            : option === correctAnswer;
        const isCorrect = showFeedback && isCorrectOption;
        const isWrong = showFeedback && isSelected && !isCorrectOption;

        return (
          <button
            key={i}
            onClick={() => {
              if (disabled) return;
              onSelect(isSelected ? "" : option);
            }}
            disabled={disabled}
            className={cn(
              "flex w-full items-center gap-3 rounded-lg border-2 px-4 py-3 text-left text-sm transition-colors",
              !showFeedback && !isSelected && "border-border hover:border-primary/50 hover:bg-accent/50",
              !showFeedback && isSelected && "border-primary bg-primary/5",
              isCorrect && "border-green-500 bg-green-50",
              isWrong && "border-red-500 bg-red-50",
              disabled && !showFeedback && "opacity-50 cursor-not-allowed",
            )}
          >
            <span
              className={cn(
                "flex h-7 w-7 shrink-0 items-center justify-center rounded-full border text-xs font-medium",
                !showFeedback && !isSelected && "border-border text-muted-foreground",
                !showFeedback && isSelected && "border-primary bg-primary text-primary-foreground",
                isCorrect && "border-green-500 bg-green-500 text-white",
                isWrong && "border-red-500 bg-red-500 text-white",
              )}
            >
              {showFeedback && isCorrect ? (
                <Check className="h-4 w-4" />
              ) : showFeedback && isWrong ? (
                "X"
              ) : (
                LABELS[i]
              )}
            </span>
            <span className="flex-1">{option}</span>
            {!showFeedback && isSelected && (
              <Check className="h-4 w-4 text-primary" />
            )}
          </button>
        );
      })}
    </div>
  );
}
