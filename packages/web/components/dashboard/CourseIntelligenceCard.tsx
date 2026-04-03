"use client";

import Link from "next/link";
import { ArrowRight, BookOpen, Clock, Zap } from "lucide-react";
import { motion } from "framer-motion";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import type { CourseIntelligenceV2 } from "@/types/database";

/* ------------------------------------------------------------------ */
/*  Risk / readiness mappings                                         */
/* ------------------------------------------------------------------ */

const RISK_CONFIG: Record<
  string,
  { gradient: string; ringColor: string; label: string; badgeClass: string }
> = {
  high: {
    gradient: "from-red-500/20 via-red-400/10 to-transparent",
    ringColor: "stroke-red-500",
    label: "High Risk",
    badgeClass: "bg-red-500/10 text-red-600 border-red-200/60",
  },
  medium: {
    gradient: "from-amber-500/20 via-amber-400/10 to-transparent",
    ringColor: "stroke-amber-500",
    label: "Needs Attention",
    badgeClass: "bg-amber-500/10 text-amber-600 border-amber-200/60",
  },
  low: {
    gradient: "from-emerald-500/20 via-emerald-400/10 to-transparent",
    ringColor: "stroke-emerald-500",
    label: "On Track",
    badgeClass: "bg-emerald-500/10 text-emerald-600 border-emerald-200/60",
  },
};

function readinessColor(pct: number): string {
  if (pct >= 80) return "text-emerald-600";
  if (pct >= 60) return "text-amber-500";
  return "text-red-500";
}

/* ------------------------------------------------------------------ */
/*  Circular progress ring (SVG)                                      */
/* ------------------------------------------------------------------ */

function ProgressRing({
  pct,
  riskClass,
}: {
  pct: number;
  riskClass: string;
}) {
  const radius = 28;
  const circumference = 2 * Math.PI * radius;
  const offset = circumference - (pct / 100) * circumference;

  return (
    <svg
      width="72"
      height="72"
      viewBox="0 0 72 72"
      className="shrink-0 -rotate-90"
    >
      {/* Track */}
      <circle
        cx="36"
        cy="36"
        r={radius}
        fill="none"
        strokeWidth="5"
        className="stroke-muted/40"
      />
      {/* Progress arc */}
      <motion.circle
        cx="36"
        cy="36"
        r={radius}
        fill="none"
        strokeWidth="5"
        strokeLinecap="round"
        className={riskClass}
        strokeDasharray={circumference}
        initial={{ strokeDashoffset: circumference }}
        animate={{ strokeDashoffset: offset }}
        transition={{ duration: 1, ease: "easeOut", delay: 0.3 }}
      />
    </svg>
  );
}

/* ------------------------------------------------------------------ */
/*  Main card component                                               */
/* ------------------------------------------------------------------ */

interface CourseIntelligenceCardProps {
  course: CourseIntelligenceV2;
  index?: number;
}

export function CourseIntelligenceCard({
  course,
  index = 0,
}: CourseIntelligenceCardProps) {
  const pct = Math.round(course.readiness * 100);
  const risk = RISK_CONFIG[course.risk] ?? RISK_CONFIG.low;
  const next = course.next_assessment;
  const action = course.recommended_action;

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4, delay: index * 0.08, ease: "easeOut" }}
    >
      <Link
        href={`/dashboard/courses/${course.course_id}`}
        className="group block h-full"
      >
        <div
          className={cn(
            "relative h-full overflow-hidden rounded-2xl border border-border/60 bg-card",
            "transition-all duration-300",
            "hover:border-primary/40 hover:shadow-lg hover:shadow-primary/5",
            "hover:-translate-y-0.5",
          )}
        >
          {/* Gradient accent glow at top */}
          <div
            className={cn(
              "absolute inset-x-0 top-0 h-24 bg-gradient-to-b opacity-60 transition-opacity duration-300 group-hover:opacity-100",
              risk.gradient,
            )}
          />

          <div className="relative px-5 pt-5 pb-5 space-y-4">
            {/* Header row — title + risk badge */}
            <div className="flex items-start justify-between gap-3">
              <div className="min-w-0 flex-1">
                {course.course_code && (
                  <span className="text-[11px] font-semibold uppercase tracking-wider text-muted-foreground/70">
                    {course.course_code}
                  </span>
                )}
                <h3 className="font-semibold text-sm leading-snug truncate">
                  {course.course_name}
                </h3>
              </div>
              <Badge
                variant="outline"
                className={cn(
                  "text-[10px] shrink-0 font-medium px-2 py-0.5 rounded-full",
                  risk.badgeClass,
                )}
              >
                {risk.label}
              </Badge>
            </div>

            {/* Readiness ring + stats */}
            <div className="flex items-center gap-4">
              <div className="relative">
                <ProgressRing pct={pct} riskClass={risk.ringColor} />
                <div className="absolute inset-0 flex items-center justify-center">
                  <span
                    className={cn(
                      "text-base font-bold tabular-nums",
                      readinessColor(pct),
                    )}
                  >
                    {pct}
                  </span>
                </div>
              </div>

              <div className="flex-1 min-w-0 space-y-1.5">
                <p className="text-xs text-muted-foreground font-medium">
                  Readiness Score
                </p>
                {/* Mini bar */}
                <div className="h-1.5 w-full rounded-full bg-muted/50 overflow-hidden">
                  <motion.div
                    className={cn(
                      "h-full rounded-full",
                      pct >= 80
                        ? "bg-emerald-500"
                        : pct >= 60
                          ? "bg-amber-500"
                          : "bg-red-500",
                    )}
                    initial={{ width: 0 }}
                    animate={{ width: `${pct}%` }}
                    transition={{ duration: 0.8, ease: "easeOut", delay: 0.4 }}
                  />
                </div>
                <div className="flex items-center gap-2 text-[11px] text-muted-foreground">
                  <BookOpen className="h-3 w-3" />
                  <span>
                    {course.assessment_count} assessment
                    {course.assessment_count !== 1 ? "s" : ""}
                  </span>
                </div>
              </div>
            </div>

            {/* Divider */}
            <div className="h-px bg-border/50" />

            {/* Next assessment */}
            {next ? (
              <div className="flex items-center gap-2.5">
                <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-muted/60">
                  <Clock className="h-3.5 w-3.5 text-muted-foreground" />
                </div>
                <div className="min-w-0 flex-1">
                  <p className="text-xs font-medium truncate">{next.title}</p>
                  <div className="flex items-center gap-1.5 mt-0.5">
                    <Badge
                      variant="outline"
                      className="text-[10px] px-1.5 py-0 rounded-full capitalize"
                    >
                      {next.type}
                    </Badge>
                    {next.days_until != null && (
                      <span className="text-[10px] text-muted-foreground">
                        in {next.days_until}d
                      </span>
                    )}
                  </div>
                </div>
              </div>
            ) : (
              <div className="flex items-center gap-2.5">
                <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-muted/60">
                  <Clock className="h-3.5 w-3.5 text-muted-foreground" />
                </div>
                <p className="text-xs text-muted-foreground">
                  No upcoming assessments
                </p>
              </div>
            )}

            {/* Recommended action */}
            {action && (
              <div className="flex items-center gap-2 rounded-lg bg-primary/5 px-3 py-2 transition-colors group-hover:bg-primary/10">
                <Zap className="h-3.5 w-3.5 text-primary shrink-0" />
                <span className="text-xs font-medium text-primary truncate">
                  {action.title}
                </span>
                <ArrowRight className="h-3 w-3 text-primary shrink-0 ml-auto transition-transform group-hover:translate-x-0.5" />
              </div>
            )}
          </div>
        </div>
      </Link>
    </motion.div>
  );
}
