"use client";

import { Check, X } from "lucide-react";
import { cn } from "@/lib/utils";
import type { ConceptPerformance as ConceptPerf } from "@/types/database";

interface ConceptPerformanceProps {
  concepts: ConceptPerf[];
}

export function ConceptPerformance({ concepts }: ConceptPerformanceProps) {
  if (concepts.length === 0) return null;

  return (
    <div className="space-y-3">
      <h3 className="text-sm font-semibold">Concept Performance</h3>
      <div className="space-y-2">
        {concepts.map((c) => {
          const pct = c.total > 0 ? Math.round((c.correct / c.total) * 100) : 0;
          return (
            <div key={c.concept} className="flex items-center gap-3">
              <div className="flex-1 min-w-0">
                <div className="flex items-center justify-between mb-1">
                  <span className="text-sm truncate">{c.concept}</span>
                  <span className="text-xs text-muted-foreground shrink-0 ml-2">
                    {c.correct}/{c.total}
                    {pct === 100 && (
                      <Check className="inline ml-1 h-3 w-3 text-green-600" />
                    )}
                    {pct === 0 && (
                      <X className="inline ml-1 h-3 w-3 text-red-600" />
                    )}
                  </span>
                </div>
                <div className="h-2 w-full overflow-hidden rounded-full bg-muted">
                  <div
                    className={cn(
                      "h-full rounded-full transition-all",
                      pct === 100 && "bg-green-500",
                      pct > 0 && pct < 100 && "bg-yellow-500",
                      pct === 0 && "bg-red-500",
                    )}
                    style={{ width: `${pct}%` }}
                  />
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
