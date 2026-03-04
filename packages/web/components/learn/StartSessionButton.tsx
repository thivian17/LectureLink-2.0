"use client";

import Link from "next/link";
import { Play, ArrowRight } from "lucide-react";
import { Skeleton } from "@/components/ui/skeleton";
import type { GamificationReadiness } from "@/types/database";

interface StartSessionButtonProps {
  topAssessment: GamificationReadiness | null;
  courseId: string | null;
  loading?: boolean;
}

export function StartSessionButton({ topAssessment, courseId, loading }: StartSessionButtonProps) {
  if (loading) {
    return <Skeleton className="h-20 w-full rounded-2xl" />;
  }

  if (!courseId) {
    return null;
  }

  const label = topAssessment
    ? `${topAssessment.title.split(":")[0]} prep`
    : "Today's Focus";

  return (
    <Link
      href={`/dashboard/courses/${courseId}/learn`}
      className="flex items-center gap-4 rounded-2xl bg-primary px-5 py-4 text-primary-foreground shadow-lg hover:opacity-95 transition-opacity"
    >
      <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-white/20">
        <Play className="h-5 w-5 fill-current" />
      </div>
      <div className="flex-1 min-w-0">
        <p className="text-lg font-semibold">Start Today&apos;s Session</p>
        <p className="text-sm text-primary-foreground/70">
          15 min &middot; {label}
        </p>
      </div>
      <ArrowRight className="h-5 w-5 shrink-0 text-primary-foreground/70" />
    </Link>
  );
}
