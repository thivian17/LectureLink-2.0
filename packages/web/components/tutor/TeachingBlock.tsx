"use client";

import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import { MarkdownContent } from "./MarkdownContent";

interface TeachingBlockProps {
  content: string;
  approach?: "foundational" | "application" | "synthesis";
  sourceLabel?: string;
}

const APPROACH_STYLES: Record<string, { label: string; className: string }> = {
  foundational: {
    label: "Foundational",
    className: "border-blue-200 text-blue-700 bg-blue-50",
  },
  application: {
    label: "Application",
    className: "border-emerald-200 text-emerald-700 bg-emerald-50",
  },
  synthesis: {
    label: "Synthesis",
    className: "border-purple-200 text-purple-700 bg-purple-50",
  },
};

export function TeachingBlock({
  content,
  approach,
  sourceLabel,
}: TeachingBlockProps) {
  const approachInfo = approach ? APPROACH_STYLES[approach] : null;

  return (
    <div className="space-y-2">
      {(approachInfo || sourceLabel) && (
        <div className="flex items-center gap-2">
          {approachInfo && (
            <Badge
              variant="outline"
              className={cn("text-[10px]", approachInfo.className)}
            >
              {approachInfo.label}
            </Badge>
          )}
          {sourceLabel && (
            <Badge variant="secondary" className="text-[10px]">
              {sourceLabel}
            </Badge>
          )}
        </div>
      )}
      <MarkdownContent content={content} />
    </div>
  );
}
