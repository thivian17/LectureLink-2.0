"use client";

import { useEffect, useState } from "react";
import { cn } from "@/lib/utils";

interface ReadinessRingProps {
  /** Value between 0 and 1 */
  value: number;
  /** Label shown below the ring */
  label: string;
  /** Ring color (hex) */
  color: string;
  /** Ring size in pixels (desktop). Scales to 52px on mobile via CSS. */
  size?: number;
  /** Stroke width */
  strokeWidth?: number;
  className?: string;
}

export function ReadinessRing({
  value,
  label,
  color,
  size = 64,
  strokeWidth = 5,
  className,
}: ReadinessRingProps) {
  const radius = (size - strokeWidth) / 2;
  const circumference = 2 * Math.PI * radius;
  const [offset, setOffset] = useState(circumference);
  const percentage = Math.round(value * 100);

  useEffect(() => {
    const timer = setTimeout(() => {
      setOffset(circumference - value * circumference);
    }, 100);
    return () => clearTimeout(timer);
  }, [value, circumference]);

  return (
    <div className={cn("flex flex-col items-center gap-1.5", className)}>
      <div className="relative" style={{ width: size, height: size }}>
        <svg width={size} height={size} className="-rotate-90">
          <circle
            cx={size / 2}
            cy={size / 2}
            r={radius}
            fill="none"
            stroke={`${color}20`}
            strokeWidth={strokeWidth}
          />
          <circle
            cx={size / 2}
            cy={size / 2}
            r={radius}
            fill="none"
            stroke={color}
            strokeWidth={strokeWidth}
            strokeDasharray={circumference}
            strokeDashoffset={offset}
            strokeLinecap="round"
            className="transition-[stroke-dashoffset] duration-[1.5s] ease-[cubic-bezier(0.16,1,0.3,1)]"
          />
        </svg>
        <div className="absolute inset-0 flex items-center justify-center">
          <span className="text-sm font-bold tabular-nums text-foreground">
            {percentage}%
          </span>
        </div>
      </div>
      <span className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
        {label}
      </span>
    </div>
  );
}
