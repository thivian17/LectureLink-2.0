"use client";

import { ArrowRight } from "lucide-react";
import { Button } from "@/components/ui/button";

interface TransitionBlockProps {
  content: string;
  nextConceptTitle: string;
  estimatedMinutes?: number;
  onStart?: () => void;
}

export function TransitionBlock({
  content,
  nextConceptTitle,
  estimatedMinutes,
  onStart,
}: TransitionBlockProps) {
  return (
    <div className="rounded-lg border border-dashed border-muted-foreground/25 bg-muted/30 px-4 py-4 space-y-3">
      <div className="flex items-center gap-4">
        <ArrowRight className="h-4 w-4 shrink-0 text-muted-foreground" />
        <div className="space-y-0.5 min-w-0">
          {content && (
            <p className="text-sm text-muted-foreground">{content}</p>
          )}
          <p className="text-sm font-medium">
            Next up: {nextConceptTitle}
            {estimatedMinutes != null && (
              <span className="text-muted-foreground font-normal">
                {" "}
                (~{estimatedMinutes} min)
              </span>
            )}
          </p>
        </div>
      </div>
      {onStart && (
        <Button onClick={onStart} className="w-full gap-2" size="sm">
          Start next concept
          <ArrowRight className="h-3 w-3" />
        </Button>
      )}
    </div>
  );
}
