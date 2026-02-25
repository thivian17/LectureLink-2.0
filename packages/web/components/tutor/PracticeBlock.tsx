"use client";

import { useState } from "react";
import { ChevronDown, ChevronUp, Dumbbell } from "lucide-react";
import { Button } from "@/components/ui/button";
import { MarkdownContent } from "./MarkdownContent";

interface PracticeBlockProps {
  content: string;
  solution?: string;
}

export function PracticeBlock({ content, solution }: PracticeBlockProps) {
  const [showSolution, setShowSolution] = useState(false);

  return (
    <div className="rounded-lg border border-indigo-200 bg-indigo-50/50 p-4 space-y-3 dark:border-indigo-800 dark:bg-indigo-950/20">
      <div className="flex items-center gap-2 text-indigo-700 dark:text-indigo-400">
        <Dumbbell className="h-4 w-4" />
        <p className="text-sm font-medium">Practice</p>
      </div>
      <MarkdownContent content={content} />
      {solution && (
        <div>
          <Button
            variant="ghost"
            size="sm"
            onClick={() => setShowSolution(!showSolution)}
            className="text-xs"
          >
            {showSolution ? (
              <ChevronUp className="mr-1 h-3 w-3" />
            ) : (
              <ChevronDown className="mr-1 h-3 w-3" />
            )}
            {showSolution ? "Hide Solution" : "Show Solution"}
          </Button>
          {showSolution && (
            <div className="mt-2 rounded-md bg-muted/50 p-3">
              <MarkdownContent content={solution} />
            </div>
          )}
        </div>
      )}
    </div>
  );
}
