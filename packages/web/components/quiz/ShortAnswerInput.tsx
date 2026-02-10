"use client";

import { Input } from "@/components/ui/input";
import { cn } from "@/lib/utils";

const MAX_CHARS = 200;

interface ShortAnswerInputProps {
  value: string;
  onChange: (value: string) => void;
  disabled?: boolean;
  correctAnswer?: string;
  showFeedback?: boolean;
  isCorrect?: boolean;
}

export function ShortAnswerInput({
  value,
  onChange,
  disabled,
  correctAnswer,
  showFeedback,
  isCorrect,
}: ShortAnswerInputProps) {
  return (
    <div className="space-y-2">
      <Input
        value={value}
        onChange={(e) => {
          if (e.target.value.length <= MAX_CHARS) {
            onChange(e.target.value);
          }
        }}
        placeholder="Type your answer..."
        disabled={disabled}
        className={cn(
          "text-base",
          showFeedback && isCorrect && "border-green-500",
          showFeedback && !isCorrect && "border-red-500",
        )}
      />
      <div className="flex items-center justify-between text-xs text-muted-foreground">
        <span>
          {value.length}/{MAX_CHARS}
        </span>
        {showFeedback && correctAnswer && (
          <span className="text-green-600 font-medium">
            Correct answer: {correctAnswer}
          </span>
        )}
      </div>
    </div>
  );
}
