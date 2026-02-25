"use client";

import { useState, useEffect } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { AssessmentTimeline } from "./AssessmentTimeline";
import { SemesterProgressBar } from "./SemesterProgressBar";
import { getPersonalizedMessage, getSemesterProgress } from "@/lib/api";
import type {
  OnboardingPath,
  PersonalizedMessage,
  SemesterProgress,
} from "@/types/database";

interface PersonalizedMessageStepProps {
  courseId: string;
  path: OnboardingPath;
  onContinue: () => void;
}

const CTA_TEXT: Record<OnboardingPath, string> = {
  just_starting: "See My Study Plan \u2192",
  mid_semester: "Let's Get Caught Up \u2192",
  course_complete: "Upload My Materials \u2192",
};

export function PersonalizedMessageStep({
  courseId,
  path,
  onContinue,
}: PersonalizedMessageStepProps) {
  const [message, setMessage] = useState<PersonalizedMessage | null>(null);
  const [progress, setProgress] = useState<SemesterProgress | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function load() {
      try {
        const [msg, prog] = await Promise.all([
          getPersonalizedMessage(courseId),
          getSemesterProgress(courseId),
        ]);
        setMessage(msg);
        setProgress(prog);
      } catch {
        toast.error("Failed to load personalized content");
      } finally {
        setLoading(false);
      }
    }
    load();
  }, [courseId]);

  if (loading) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-6 w-48" />
        <Skeleton className="h-32 w-full" />
        <Skeleton className="h-20 w-full" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Personalized message */}
      <Card
        className={
          path === "course_complete"
            ? "border-green-200 bg-gradient-to-br from-green-50/50 to-transparent"
            : undefined
        }
      >
        <CardContent className="pt-6">
          <p className="text-lg leading-relaxed">
            {message?.message ?? "Welcome! Let's get your course set up."}
          </p>
        </CardContent>
      </Card>

      {/* Path-specific content */}
      {path === "just_starting" && progress && (
        <AssessmentTimeline assessments={progress.upcoming_assessments} />
      )}

      {path === "mid_semester" && progress && (
        <div className="space-y-4">
          <SemesterProgressBar progressPct={progress.progress_pct} />
          {progress.next_assessment && (
            <Card>
              <CardContent className="flex items-center justify-between pt-6">
                <div>
                  <p className="text-sm font-medium">
                    {progress.next_assessment.title}
                  </p>
                  <p className="text-xs text-muted-foreground">
                    {progress.next_assessment.due_date ?? "Date TBD"}
                    {progress.next_assessment.weight_percent != null &&
                      ` \u00B7 ${progress.next_assessment.weight_percent}% of grade`}
                  </p>
                </div>
                {progress.next_assessment.due_date && (() => {
                  const days = Math.ceil(
                    (new Date(progress.next_assessment.due_date + "T00:00:00").getTime() - Date.now()) / 86400000
                  );
                  return days > 0 ? (
                    <span className="text-sm font-medium tabular-nums">
                      {days}d left
                    </span>
                  ) : null;
                })()}
              </CardContent>
            </Card>
          )}
        </div>
      )}

      {/* CTA */}
      <div className="flex justify-end">
        <Button onClick={onContinue}>{CTA_TEXT[path]}</Button>
      </div>
    </div>
  );
}
