"use client";

import { Info } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { cn } from "@/lib/utils";
import { getConfidenceLevel, getConfidenceBadgeClasses } from "@/types/extraction";

interface ConfidenceIndicatorProps {
  confidence: number;
  sourceText?: string | null;
  className?: string;
}

export function ConfidenceIndicator({
  confidence,
  sourceText,
  className,
}: ConfidenceIndicatorProps) {
  const level = getConfidenceLevel(confidence);
  const badgeClass = getConfidenceBadgeClasses(level);
  const label = `${Math.round(confidence * 100)}%`;

  return (
    <div className={cn("flex items-center gap-1", className)}>
      <Badge variant="outline" className={cn("text-xs", badgeClass)}>
        {label}
      </Badge>
      {sourceText && (
        <TooltipProvider delayDuration={200}>
          <Tooltip>
            <TooltipTrigger asChild>
              <Info className="h-3.5 w-3.5 text-muted-foreground cursor-help shrink-0" />
            </TooltipTrigger>
            <TooltipContent side="top" className="max-w-xs">
              <p className="text-xs">
                <span className="font-medium">Source: </span>
                &ldquo;{sourceText}&rdquo;
              </p>
            </TooltipContent>
          </Tooltip>
        </TooltipProvider>
      )}
    </div>
  );
}
