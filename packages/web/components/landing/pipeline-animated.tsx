"use client";

import { useEffect, useState } from "react";
import { Download, FileText, GitMerge, Sparkles, Check } from "lucide-react";
import { useIntersectionObserver } from "@/hooks/use-intersection-observer";

const STEPS = [
  { label: "Upload", sub: "Syllabus + slides", icon: Download },
  { label: "Extract", sub: "Concepts + chunks", icon: FileText },
  { label: "Align", sub: "Semantic model", icon: GitMerge },
  { label: "Plan", sub: "Study schedule", icon: Sparkles },
];

const STEP_DELAYS = [0, 1400, 3000, 5000];

const EVENTS = [
  {
    label: "Course loaded \u2014 Intro to Comp Sci",
    meta: "Syllabus parsed \u00b7 12 lectures \u00b7 3 assessments detected",
  },
  {
    label: "224 concepts extracted",
    meta: "Difficulty estimated per concept \u00b7 exam weights applied",
  },
  {
    label: "Semantic alignment complete",
    meta: "Slides linked to lecture segments \u00b7 hybrid search index built",
  },
  {
    label: "Mastery model initialised",
    meta: "Bayesian knowledge priors set for 224 concepts",
  },
  {
    label: "Assessment links created",
    meta: "Final Exam \u00b7 67 concepts mapped \u00b7 readiness tracking active",
  },
  {
    label: "Study plan ready",
    meta: "Priority topics: OOP \u00b7 Complexity \u00b7 Sorting algorithms",
  },
];

const EVENT_DELAYS = [200, 1100, 2000, 3200, 4200, 5400];

export function PipelineAnimated() {
  const { ref, isVisible } = useIntersectionObserver({ threshold: 0.2 });
  const [lineProgress, setLineProgress] = useState(0);
  const [activeSteps, setActiveSteps] = useState<boolean[]>([false, false, false, false]);
  const [visibleEvents, setVisibleEvents] = useState<boolean[]>(
    new Array(EVENTS.length).fill(false)
  );

  useEffect(() => {
    if (!isVisible) return;

    // Animate connector line
    setLineProgress(100);

    // Activate steps progressively
    const stepTimers = STEP_DELAYS.map((delay, i) =>
      setTimeout(() => {
        setActiveSteps((prev) => {
          const next = [...prev];
          next[i] = true;
          return next;
        });
      }, delay)
    );

    // Show event cards sequentially
    const eventTimers = EVENT_DELAYS.map((delay, i) =>
      setTimeout(() => {
        setVisibleEvents((prev) => {
          const next = [...prev];
          next[i] = true;
          return next;
        });
      }, delay)
    );

    return () => {
      stepTimers.forEach(clearTimeout);
      eventTimers.forEach(clearTimeout);
    };
  }, [isVisible]);

  return (
    <div ref={ref as React.RefObject<HTMLDivElement>}>
      {/* Pipeline steps */}
      <div className="relative flex justify-between items-start mb-12 px-4">
        {/* Connector line */}
        <div
          className="absolute left-[calc(12.5%+17px)] right-[calc(12.5%+17px)] border-border bg-border"
          style={{ top: "17px", height: "2px" }}
        >
          <div
            className="h-full"
            style={{
              backgroundColor: "#185FA5",
              width: `${lineProgress}%`,
              transition: "width 7s linear",
            }}
          />
        </div>

        {STEPS.map((step, i) => {
          const Icon = step.icon;
          const active = activeSteps[i];
          return (
            <div
              key={step.label}
              className="relative flex flex-col items-center text-center"
              style={{ width: "25%" }}
            >
              <div
                className="flex h-[34px] w-[34px] items-center justify-center rounded-full border-2 relative z-10 transition-all duration-300"
                style={{
                  backgroundColor: active ? "#185FA5" : "var(--background)",
                  borderColor: active ? "#185FA5" : "var(--border)",
                }}
              >
                <Icon
                  className="h-4 w-4 transition-colors duration-300"
                  style={{ color: active ? "white" : "var(--muted-foreground)" }}
                />
              </div>
              <p className="text-xs font-medium mt-2">{step.label}</p>
              <p className="text-[10px] text-muted-foreground">{step.sub}</p>
            </div>
          );
        })}
      </div>

      {/* Event cards */}
      <div className="space-y-2">
        {EVENTS.map((event, i) => (
          <div
            key={i}
            className="bg-background border border-border rounded-xl p-2.5 flex gap-2.5"
            style={{
              opacity: visibleEvents[i] ? 1 : 0,
              transform: visibleEvents[i] ? "translateY(0)" : "translateY(6px)",
              transition: "opacity 350ms ease, transform 350ms ease",
            }}
          >
            <div
              className="flex h-6 w-6 shrink-0 items-center justify-center rounded-lg"
              style={{ backgroundColor: "#E1F5EE" }}
            >
              <Check className="h-3.5 w-3.5" style={{ color: "#0F6E56" }} />
            </div>
            <div className="min-w-0">
              <p className="text-xs font-medium leading-snug">{event.label}</p>
              <p className="text-[10px] text-muted-foreground leading-snug">
                {event.meta}
              </p>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
