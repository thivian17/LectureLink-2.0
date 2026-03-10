"use client";

import { useState } from "react";
import { ChevronDown, Dumbbell, Eye, CheckCircle2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import { MarkdownContent } from "./MarkdownContent";

interface PracticeBlockProps {
  content: string;
  solution?: string;
}

/**
 * Split a solution string into logical steps.
 * Looks for numbered patterns like "1.", "Step 1:", "**Step 1**", etc.
 * Falls back to a single block if no steps are detected.
 */
function parseSolutionSteps(solution: string): { title: string; body: string }[] {
  // Match lines starting with: "1.", "Step 1:", "**Step 1:**", "**1.**", "### Step 1", etc.
  const stepPattern = /^(?:#{1,4}\s+)?(?:\*{0,2})(?:Step\s+)?(\d+)[.):]\s*\*{0,2}\s*/im;

  // Split on step boundaries (lookahead keeps the delimiter in the next segment)
  const segments = solution.split(/\n(?=(?:#{1,4}\s+)?(?:\*{0,2})(?:Step\s+)?\d+[.):]\s)/i);

  if (segments.length <= 1) {
    // No numbered steps found — try splitting on markdown headings
    const headingSegments = solution.split(/\n(?=#{2,4}\s+)/);
    if (headingSegments.length > 1) {
      return headingSegments.map((seg) => {
        const lines = seg.trim().split("\n");
        const firstLine = lines[0].replace(/^#{2,4}\s+/, "").trim();
        return {
          title: firstLine,
          body: lines.length > 1 ? lines.slice(1).join("\n").trim() : "",
        };
      });
    }
    // No structure found — return as single block
    return [{ title: "Solution", body: solution }];
  }

  return segments.map((seg) => {
    const trimmed = seg.trim();
    const match = trimmed.match(stepPattern);
    if (match) {
      const afterMatch = trimmed.slice(match[0].length);
      const lines = afterMatch.split("\n");
      const title = lines[0].replace(/\*{1,2}/g, "").trim();
      const body = lines.length > 1 ? lines.slice(1).join("\n").trim() : "";
      return { title: `Step ${match[1]}: ${title}`, body };
    }
    return { title: "Solution", body: trimmed };
  });
}

export function PracticeBlock({ content, solution }: PracticeBlockProps) {
  const [revealedCount, setRevealedCount] = useState(0);
  const steps = solution ? parseSolutionSteps(solution) : [];
  const totalSteps = steps.length;
  const allRevealed = revealedCount >= totalSteps;

  return (
    <div className="rounded-lg border border-indigo-200 bg-indigo-50/50 p-4 space-y-4 dark:border-indigo-800 dark:bg-indigo-950/20">
      {/* Header */}
      <div className="flex items-center gap-2 text-indigo-700 dark:text-indigo-400">
        <Dumbbell className="h-4 w-4" />
        <p className="text-sm font-medium">Practice Problem</p>
      </div>

      {/* Problem statement */}
      <MarkdownContent content={content} />

      {/* Interactive solution */}
      {solution && (
        <div className="space-y-4 pt-3 border-t border-indigo-200 dark:border-indigo-800">
          {/* Revealed steps */}
          {steps.slice(0, revealedCount).map((step, i) => (
            <div
              key={i}
              className="animate-in fade-in slide-in-from-bottom-2 duration-300"
            >
              <div className="flex items-start gap-3 rounded-md bg-white/60 dark:bg-white/5 border border-indigo-100 dark:border-indigo-900/50 p-3">
                <Badge
                  variant="secondary"
                  className={cn(
                    "shrink-0 h-6 min-w-[1.5rem] p-0 justify-center text-xs mt-0.5",
                    totalSteps > 1 && "bg-indigo-100 text-indigo-700 dark:bg-indigo-900 dark:text-indigo-300"
                  )}
                >
                  {totalSteps > 1 ? i + 1 : <Eye className="h-3 w-3" />}
                </Badge>
                <div className="flex-1 min-w-0">
                  {totalSteps > 1 && (
                    <p className="text-sm font-semibold mb-1.5">{step.title}</p>
                  )}
                  {step.body && (
                    <MarkdownContent
                      content={step.body}
                      className="text-sm prose prose-sm max-w-none dark:prose-invert leading-relaxed text-muted-foreground"
                    />
                  )}
                </div>
              </div>
            </div>
          ))}

          {/* Reveal button */}
          {!allRevealed && (
            <Button
              variant="outline"
              size="sm"
              className="w-full gap-2 text-indigo-700 border-indigo-200 hover:bg-indigo-100 dark:text-indigo-400 dark:border-indigo-800 dark:hover:bg-indigo-950"
              onClick={() => setRevealedCount((c) => c + 1)}
            >
              <ChevronDown className="h-3 w-3" />
              {revealedCount === 0
                ? totalSteps > 1
                  ? "Show first step"
                  : "Show Solution"
                : `Show step ${revealedCount + 1} of ${totalSteps}`}
            </Button>
          )}

          {/* Completion marker */}
          {allRevealed && totalSteps > 1 && (
            <div className="flex items-center gap-2 text-green-600 dark:text-green-400 pt-1">
              <CheckCircle2 className="h-4 w-4" />
              <p className="text-xs font-medium">All steps revealed</p>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
