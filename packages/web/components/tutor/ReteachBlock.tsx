"use client";

import { Lightbulb } from "lucide-react";
import { MarkdownContent } from "./MarkdownContent";

interface ReteachBlockProps {
  content: string;
}

export function ReteachBlock({ content }: ReteachBlockProps) {
  return (
    <div className="rounded-lg border border-amber-200 bg-amber-50 p-4 space-y-2 dark:border-amber-800 dark:bg-amber-950/20">
      <div className="flex items-center gap-2 text-amber-700 dark:text-amber-400">
        <Lightbulb className="h-4 w-4" />
        <p className="text-sm font-medium">Let me explain this differently...</p>
      </div>
      <MarkdownContent
        content={content}
        className="prose prose-sm max-w-none leading-relaxed text-amber-900 dark:text-amber-100"
      />
    </div>
  );
}
