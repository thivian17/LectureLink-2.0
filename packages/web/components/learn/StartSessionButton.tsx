"use client";

import Link from "next/link";
import { Play, Clock } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import type { GamificationReadiness } from "@/types/database";

interface StartSessionButtonProps {
  topAssessment: GamificationReadiness | null;
  courseId: string | null;
  loading?: boolean;
}

export function StartSessionButton({ topAssessment, courseId, loading }: StartSessionButtonProps) {
  if (loading) {
    return <Skeleton className="h-14 w-full rounded-xl" />;
  }

  if (!courseId) {
    return null;
  }

  const label = topAssessment
    ? `${topAssessment.title.split(":")[0]}`
    : "Today's Focus";

  return (
    <Button
      asChild
      size="lg"
      className="w-full h-14 text-base gap-2 rounded-xl shadow-md hover:shadow-lg transition-shadow"
    >
      <Link href={`/dashboard/courses/${courseId}/learn`}>
        <Play className="h-5 w-5" />
        <span>Start Today&apos;s Session</span>
        <span className="text-primary-foreground/70 flex items-center gap-1 ml-1">
          <Clock className="h-3.5 w-3.5" />
          15 min
        </span>
        <span className="text-primary-foreground/70 ml-1">· {label}</span>
      </Link>
    </Button>
  );
}
