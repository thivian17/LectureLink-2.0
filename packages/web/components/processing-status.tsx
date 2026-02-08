"use client";

import { Fragment } from "react";
import { Check, Circle, Loader2, AlertCircle, RotateCcw } from "lucide-react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

export type ProcessingStep = "upload" | "extract" | "validate" | "review";

type StepStatus = "pending" | "active" | "complete" | "error";

const STEPS: { key: ProcessingStep; label: string }[] = [
  { key: "upload", label: "Upload" },
  { key: "extract", label: "Extract" },
  { key: "validate", label: "Validate" },
  { key: "review", label: "Review" },
];

function getStepStatus(
  stepIndex: number,
  currentIndex: number,
  hasError: boolean,
): StepStatus {
  if (hasError && stepIndex === currentIndex) return "error";
  if (stepIndex < currentIndex) return "complete";
  if (stepIndex === currentIndex) return "active";
  return "pending";
}

function StepIcon({ status }: { status: StepStatus }) {
  switch (status) {
    case "complete":
      return <Check className="h-4 w-4" />;
    case "active":
      return <Loader2 className="h-4 w-4 animate-spin" />;
    case "error":
      return <AlertCircle className="h-4 w-4" />;
    default:
      return <Circle className="h-4 w-4" />;
  }
}

interface ProcessingStatusProps {
  currentStep: ProcessingStep;
  error?: string | null;
  onRetry?: () => void;
}

export function ProcessingStatus({
  currentStep,
  error,
  onRetry,
}: ProcessingStatusProps) {
  const currentIndex = STEPS.findIndex((s) => s.key === currentStep);

  return (
    <div className="space-y-4">
      <div className="flex items-center">
        {STEPS.map((step, i) => {
          const status = getStepStatus(i, currentIndex, !!error);
          return (
            <Fragment key={step.key}>
              <div className="flex flex-col items-center gap-2">
                <div
                  className={cn(
                    "flex h-8 w-8 items-center justify-center rounded-full border-2 transition-colors",
                    status === "complete" &&
                      "border-primary bg-primary text-primary-foreground",
                    status === "active" &&
                      "border-primary text-primary",
                    status === "error" &&
                      "border-destructive bg-destructive/10 text-destructive",
                    status === "pending" &&
                      "border-muted bg-muted text-muted-foreground",
                  )}
                >
                  <StepIcon status={status} />
                </div>
                <span
                  className={cn(
                    "text-xs font-medium",
                    status === "complete" && "text-primary",
                    status === "active" && "text-primary",
                    status === "error" && "text-destructive",
                    status === "pending" && "text-muted-foreground",
                  )}
                >
                  {step.label}
                </span>
              </div>
              {i < STEPS.length - 1 && (
                <div
                  className={cn(
                    "mb-6 h-0.5 flex-1 mx-2 transition-colors",
                    i < currentIndex ? "bg-primary" : "bg-border",
                  )}
                />
              )}
            </Fragment>
          );
        })}
      </div>
      {error && (
        <div className="flex items-center justify-between rounded-md border border-destructive/50 bg-destructive/10 px-4 py-3">
          <p className="text-sm text-destructive">{error}</p>
          {onRetry && (
            <Button variant="outline" size="sm" onClick={onRetry}>
              <RotateCcw className="mr-2 h-4 w-4" />
              Retry
            </Button>
          )}
        </div>
      )}
    </div>
  );
}
