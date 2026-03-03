"use client";

import { cn } from "@/lib/utils";
import type { LearnSessionStep } from "@/types/database";

interface SessionProgressBarProps {
  currentStep: LearnSessionStep;
}

const STEPS: { key: LearnSessionStep; label: string }[] = [
  { key: "briefing", label: "Briefing" },
  { key: "flash_review", label: "Flash" },
  { key: "concept_brief", label: "Brief" },
  { key: "power_quiz", label: "Quiz" },
  { key: "celebration", label: "Done" },
];

export function SessionProgressBar({ currentStep }: SessionProgressBarProps) {
  const currentIndex = STEPS.findIndex((s) => s.key === currentStep);

  return (
    <div className="flex items-center gap-1 w-full">
      {STEPS.map((step, i) => {
        const isCompleted = i < currentIndex;
        const isCurrent = i === currentIndex;

        return (
          <div key={step.key} className="flex items-center gap-1 flex-1">
            <div className="flex flex-col items-center flex-1">
              <div
                className={cn(
                  "h-1.5 w-full rounded-full transition-colors duration-300",
                  isCompleted && "bg-primary",
                  isCurrent && "bg-primary/60",
                  !isCompleted && !isCurrent && "bg-muted",
                )}
              />
              <span
                className={cn(
                  "text-[10px] mt-1 transition-colors",
                  isCurrent ? "text-foreground font-medium" : "text-muted-foreground",
                )}
              >
                {step.label}
              </span>
            </div>
          </div>
        );
      })}
    </div>
  );
}
