"use client";

import { cn } from "@/lib/utils";

interface QuizProgressProps {
  totalQuestions: number;
  currentIndex: number;
  answers: Map<string, string | null>;
  questionIds: string[];
  onNavigate: (index: number) => void;
}

export function QuizProgress({
  totalQuestions,
  currentIndex,
  answers,
  questionIds,
  onNavigate,
}: QuizProgressProps) {
  return (
    <div className="flex items-center gap-1.5 flex-wrap">
      {Array.from({ length: totalQuestions }, (_, i) => {
        const qId = questionIds[i];
        const hasAnswer = qId ? answers.has(qId) && answers.get(qId) != null : false;
        const isCurrent = i === currentIndex;
        return (
          <button
            key={i}
            onClick={() => onNavigate(i)}
            className={cn(
              "h-2.5 w-2.5 rounded-full transition-colors",
              isCurrent && "ring-2 ring-primary ring-offset-1",
              hasAnswer && !isCurrent && "bg-green-500",
              !hasAnswer && !isCurrent && "bg-gray-300",
              isCurrent && hasAnswer && "bg-green-500",
              isCurrent && !hasAnswer && "bg-primary",
            )}
            aria-label={`Go to question ${i + 1}`}
          />
        );
      })}
    </div>
  );
}
