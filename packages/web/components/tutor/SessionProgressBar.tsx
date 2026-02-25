"use client";

import { Pause, Square } from "lucide-react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

interface SessionProgressBarProps {
  currentConceptIndex: number;
  totalConcepts: number;
  conceptTitle: string;
  elapsedSeconds: number;
  onPause: () => void;
  onEnd: () => void;
}

function formatTime(seconds: number): string {
  const m = Math.floor(seconds / 60);
  const s = seconds % 60;
  return `${m}:${s.toString().padStart(2, "0")}`;
}

export function SessionProgressBar({
  currentConceptIndex,
  totalConcepts,
  conceptTitle,
  elapsedSeconds,
  onPause,
  onEnd,
}: SessionProgressBarProps) {
  const pct =
    totalConcepts > 0
      ? Math.round((currentConceptIndex / totalConcepts) * 100)
      : 0;

  return (
    <div className="sticky top-0 z-10 border-b bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/80">
      <div className="flex items-center justify-between gap-4 px-4 py-2">
        <div className="min-w-0 flex-1">
          <p className="text-sm font-medium truncate">
            Concept {currentConceptIndex + 1} of {totalConcepts} &mdash;{" "}
            {conceptTitle}
          </p>
          {/* Segmented progress bar */}
          <div className="mt-1 flex gap-0.5">
            {Array.from({ length: totalConcepts }, (_, i) => (
              <div
                key={i}
                className={cn(
                  "h-1 flex-1 rounded-full transition-colors",
                  i < currentConceptIndex
                    ? "bg-green-500"
                    : i === currentConceptIndex
                      ? "bg-primary"
                      : "bg-muted",
                )}
              />
            ))}
          </div>
        </div>
        <div className="flex items-center gap-2 shrink-0">
          <span className="text-sm tabular-nums text-muted-foreground">
            {formatTime(elapsedSeconds)}
          </span>
          <Button variant="ghost" size="icon" onClick={onPause} title="Pause">
            <Pause className="h-4 w-4" />
          </Button>
          <Button
            variant="ghost"
            size="icon"
            onClick={onEnd}
            title="End session"
          >
            <Square className="h-4 w-4" />
          </Button>
        </div>
      </div>
    </div>
  );
}
