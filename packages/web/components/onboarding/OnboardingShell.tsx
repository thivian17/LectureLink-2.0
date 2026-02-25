"use client";

import { ArrowLeft } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";
import { cn } from "@/lib/utils";

interface OnboardingShellProps {
  courseId: string;
  currentStep: number;
  totalSteps: number;
  stepLabels: string[];
  children: React.ReactNode;
  onBack?: () => void;
}

export function OnboardingShell({
  currentStep,
  totalSteps,
  stepLabels,
  children,
  onBack,
}: OnboardingShellProps) {
  const progressPct = totalSteps > 1 ? (currentStep / (totalSteps - 1)) * 100 : 0;

  return (
    <div className="mx-auto max-w-2xl space-y-6 py-6">
      {/* Progress bar */}
      <div className="space-y-3">
        <div className="flex items-center justify-between text-xs text-muted-foreground">
          <span>
            Step {currentStep + 1} of {totalSteps}
          </span>
          <span>{Math.round(progressPct)}%</span>
        </div>
        <Progress value={progressPct} className="h-2" />

        {/* Step labels */}
        <div className="flex gap-1 overflow-x-auto">
          {stepLabels.map((label, i) => (
            <span
              key={label}
              className={cn(
                "whitespace-nowrap rounded-full px-2 py-0.5 text-xs transition-colors",
                i === currentStep
                  ? "bg-primary text-primary-foreground font-medium"
                  : i < currentStep
                    ? "text-muted-foreground"
                    : "text-muted-foreground/50",
              )}
            >
              {label}
            </span>
          ))}
        </div>
      </div>

      {/* Back button */}
      {onBack && currentStep > 0 && (
        <Button variant="ghost" size="sm" onClick={onBack}>
          <ArrowLeft className="mr-1 h-4 w-4" />
          Back
        </Button>
      )}

      {/* Content area with fade-in */}
      <div
        key={currentStep}
        className="animate-in fade-in duration-300"
      >
        {children}
      </div>
    </div>
  );
}
