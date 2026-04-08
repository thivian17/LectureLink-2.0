"use client";

import { useEffect, useState } from "react";
import { useIntersectionObserver } from "@/hooks/use-intersection-observer";

const SIGNALS = [
  { name: "Coverage", target: 78, color: "#185FA5" },
  { name: "Practice", target: 62, color: "#1D9E75" },
  { name: "Freshness", target: 71, color: "#EF9F27" },
  { name: "Effort", target: 55, color: "#D4537E" },
];

const CIRCUMFERENCE = 2 * Math.PI * 57; // ≈ 358.14

export function ReadinessRingAnimated() {
  const { ref, isVisible } = useIntersectionObserver({ threshold: 0.25 });
  const [counter, setCounter] = useState(0);
  const [animated, setAnimated] = useState(false);

  useEffect(() => {
    if (!isVisible) return;
    setAnimated(true);

    // Animate counter 0→67 over 1.6s
    const target = 67;
    const duration = 1600;
    const steps = 40;
    const stepTime = duration / steps;
    let current = 0;
    const interval = setInterval(() => {
      current += target / steps;
      if (current >= target) {
        current = target;
        clearInterval(interval);
      }
      setCounter(Math.round(current));
    }, stepTime);

    return () => clearInterval(interval);
  }, [isVisible]);

  const offset = animated
    ? CIRCUMFERENCE * (1 - 0.67)
    : CIRCUMFERENCE;

  return (
    <div ref={ref as React.RefObject<HTMLDivElement>} className="flex flex-col sm:flex-row items-center gap-10">
      {/* Ring */}
      <div className="shrink-0">
        <svg viewBox="0 0 140 140" className="h-36 w-36">
          {/* Background ring */}
          <circle
            cx="70"
            cy="70"
            r="57"
            fill="none"
            stroke="var(--border)"
            strokeWidth="9"
          />
          {/* Fill ring */}
          <circle
            cx="70"
            cy="70"
            r="57"
            fill="none"
            stroke="#185FA5"
            strokeWidth="9"
            strokeLinecap="round"
            strokeDasharray={CIRCUMFERENCE}
            strokeDashoffset={offset}
            style={{
              transition: "stroke-dashoffset 1.6s cubic-bezier(0.4,0,0.2,1)",
              transform: "rotate(-90deg)",
              transformOrigin: "center",
            }}
          />
          {/* Center text */}
          <text
            x="70"
            y="65"
            textAnchor="middle"
            dominantBaseline="central"
            className="fill-foreground"
            style={{ fontSize: "28px", fontWeight: 800 }}
          >
            {counter}%
          </text>
          <text
            x="70"
            y="88"
            textAnchor="middle"
            dominantBaseline="central"
            className="fill-muted-foreground"
            style={{ fontSize: "11px" }}
          >
            Final Exam
          </text>
        </svg>
      </div>

      {/* Signal bars */}
      <div className="grid grid-cols-2 gap-x-8 gap-y-4 flex-1 w-full">
        {SIGNALS.map((signal) => (
          <div key={signal.name}>
            <div className="flex items-center justify-between mb-1">
              <span className="text-xs text-muted-foreground">{signal.name}</span>
              <span className="text-xs font-medium">
                {animated ? signal.target : 0}%
              </span>
            </div>
            <div
              className="h-[3px] rounded-[3px] w-full"
              style={{ backgroundColor: "var(--border)" }}
            >
              <div
                className="h-full rounded-[3px]"
                style={{
                  backgroundColor: signal.color,
                  width: animated ? `${signal.target}%` : "0%",
                  transition: "width 1.6s cubic-bezier(0.4,0,0.2,1)",
                }}
              />
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
