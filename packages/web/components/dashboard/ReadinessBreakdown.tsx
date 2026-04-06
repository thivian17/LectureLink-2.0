"use client";

import { ReadinessRing } from "./ReadinessRing";
import type { ReadinessBreakdownV2 } from "@/types/database";

interface ReadinessBreakdownProps {
  breakdown: ReadinessBreakdownV2;
  /** Use smaller rings for compact contexts */
  compact?: boolean;
}

const SIGNALS = [
  { key: "coverage" as const, label: "Coverage", color: "#2563EB" },
  { key: "practice" as const, label: "Practice", color: "#F59E0B" },
  { key: "freshness" as const, label: "Freshness", color: "#16A34A" },
  { key: "effort" as const, label: "Effort", color: "#8B5CF6" },
] as const;

export function ReadinessBreakdown({
  breakdown,
  compact,
}: ReadinessBreakdownProps) {
  const ringSize = compact ? 48 : 64;
  const strokeWidth = compact ? 4 : 5;

  return (
    <div className="flex items-center justify-around py-2">
      {SIGNALS.map(({ key, label, color }) => (
        <ReadinessRing
          key={key}
          value={breakdown[key]}
          label={label}
          color={color}
          size={ringSize}
          strokeWidth={strokeWidth}
        />
      ))}
    </div>
  );
}
