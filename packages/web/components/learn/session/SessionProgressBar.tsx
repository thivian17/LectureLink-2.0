"use client";

import { cn } from "@/lib/utils";
import type { LearnSessionStep } from "@/types/database";

interface SessionProgressBarProps {
  currentStep: LearnSessionStep;
  conceptProgress?: { current: number; total: number };
  totalConcepts?: number;
  currentConceptIndex?: number;
}

const SEGMENTS: { key: LearnSessionStep; label: string; weight: number }[] = [
  { key: "flash_review", label: "Flash Review", weight: 20 },
  { key: "concept_brief", label: "Concepts", weight: 60 },
  { key: "power_quiz", label: "Power Quiz", weight: 20 },
];

function getPhaseLabel(
  currentStep: LearnSessionStep,
  currentConceptIndex?: number,
  totalConcepts?: number,
): string {
  switch (currentStep) {
    case "briefing":
      return "Getting ready...";
    case "flash_review":
      return "Flash Review";
    case "concept_brief":
      if (totalConcepts && currentConceptIndex !== undefined) {
        return `Concept ${currentConceptIndex + 1} of ${totalConcepts}`;
      }
      return "Concept Brief";
    case "power_quiz":
      return "Power Quiz";
    case "celebration":
      return "Complete!";
    default:
      return "";
  }
}

export function SessionProgressBar({
  currentStep,
  conceptProgress,
  totalConcepts,
  currentConceptIndex,
}: SessionProgressBarProps) {
  const stepOrder: LearnSessionStep[] = ["briefing", "flash_review", "concept_brief", "power_quiz", "celebration"];
  const currentStepIdx = stepOrder.indexOf(currentStep);

  function getSegmentFill(segKey: LearnSessionStep): number {
    const segIdx = stepOrder.indexOf(segKey);
    if (currentStepIdx > segIdx) return 100;
    if (currentStepIdx < segIdx) return 0;
    // We're currently in this segment
    if (segKey === "concept_brief" && conceptProgress && conceptProgress.total > 0) {
      return (conceptProgress.current / conceptProgress.total) * 100;
    }
    return 50; // currently active, show half-filled
  }

  const phaseLabel = getPhaseLabel(currentStep, currentConceptIndex, totalConcepts);

  // For briefing, show all segments empty; for celebration, show all full
  const isBriefing = currentStep === "briefing";
  const isCelebration = currentStep === "celebration";

  return (
    <div className="w-full space-y-1">
      <div className="flex items-center gap-1 w-full">
        {SEGMENTS.map((seg) => {
          const fill = isBriefing ? 0 : isCelebration ? 100 : getSegmentFill(seg.key);

          return (
            <div
              key={seg.key}
              className="h-1.5 rounded-full bg-muted overflow-hidden"
              style={{ flex: seg.weight }}
            >
              <div
                className={cn(
                  "h-full rounded-full transition-all duration-500 ease-out",
                  fill === 100 ? "bg-primary" : "bg-primary/60",
                )}
                style={{ width: `${fill}%` }}
              />
            </div>
          );
        })}
      </div>
      <p className="text-[10px] text-muted-foreground text-center">{phaseLabel}</p>
    </div>
  );
}
