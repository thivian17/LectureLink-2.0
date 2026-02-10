"use client";

import { Check, X } from "lucide-react";
import { cn } from "@/lib/utils";

interface TrueFalseOptionsProps {
  selectedAnswer: string | null;
  onSelect: (answer: string) => void;
  disabled?: boolean;
  correctAnswer?: string;
  showFeedback?: boolean;
}

export function TrueFalseOptions({
  selectedAnswer,
  onSelect,
  disabled,
  correctAnswer,
  showFeedback,
}: TrueFalseOptionsProps) {
  const options = ["True", "False"];

  return (
    <div className="flex gap-4">
      {options.map((option) => {
        const isSelected = selectedAnswer === option;
        const isCorrect = showFeedback && option === correctAnswer;
        const isWrong = showFeedback && isSelected && option !== correctAnswer;

        return (
          <button
            key={option}
            onClick={() => {
              if (disabled) return;
              onSelect(isSelected ? "" : option);
            }}
            disabled={disabled}
            className={cn(
              "flex flex-1 items-center justify-center gap-2 rounded-lg border-2 px-6 py-4 text-base font-medium transition-colors",
              !showFeedback && !isSelected && "border-border hover:border-primary/50 hover:bg-accent/50",
              !showFeedback && isSelected && "border-primary bg-primary/5",
              isCorrect && "border-green-500 bg-green-50",
              isWrong && "border-red-500 bg-red-50",
              disabled && !showFeedback && "opacity-50 cursor-not-allowed",
            )}
          >
            {showFeedback && isCorrect && (
              <Check className="h-5 w-5 text-green-600" />
            )}
            {showFeedback && isWrong && (
              <X className="h-5 w-5 text-red-600" />
            )}
            {!showFeedback && isSelected && (
              <Check className="h-5 w-5 text-primary" />
            )}
            {option}
          </button>
        );
      })}
    </div>
  );
}
