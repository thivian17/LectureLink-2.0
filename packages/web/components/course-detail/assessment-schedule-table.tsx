"use client";

import { useEffect, useState } from "react";
import { format } from "date-fns";
import { FileText } from "lucide-react";

import { Card, CardContent } from "@/components/ui/card";
import { cn } from "@/lib/utils";
import { getAssessments, getGamificationReadiness } from "@/lib/api";
import type { Assessment } from "@/types/database";

interface AssessmentScheduleTableProps {
  courseId: string;
  syllabusFileName?: string | null;
  reviewedAt?: string | null;
  instructorName?: string | null;
  gradeBreakdown?: { component: string; weight: number }[];
}

export function AssessmentScheduleTable({
  courseId,
  syllabusFileName,
  reviewedAt,
  instructorName,
  gradeBreakdown,
}: AssessmentScheduleTableProps) {
  const [assessments, setAssessments] = useState<Assessment[]>([]);
  const [readinessMap, setReadinessMap] = useState<Map<string, number>>(
    new Map(),
  );
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;

    async function load() {
      try {
        const data = await getAssessments(courseId);
        if (cancelled) return;
        setAssessments(data);
      } catch {
        // Assessments not available
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    async function loadReadiness() {
      try {
        const data = await getGamificationReadiness(courseId);
        if (cancelled) return;
        const map = new Map<string, number>();
        for (const r of data) {
          if (r.assessment_id && r.readiness_score != null) {
            map.set(r.assessment_id, Math.round(r.readiness_score * 100));
          }
        }
        setReadinessMap(map);
      } catch {
        // Readiness not available — show dashes
      }
    }

    load();
    loadReadiness();
    return () => {
      cancelled = true;
    };
  }, [courseId]);

  const sorted = [...assessments].sort((a, b) => {
    if (!a.due_date && !b.due_date) return 0;
    if (!a.due_date) return 1;
    if (!b.due_date) return -1;
    return new Date(a.due_date).getTime() - new Date(b.due_date).getTime();
  });

  return (
    <Card>
      <CardContent className="pt-6">
        {/* Header */}
        <div className="flex items-center justify-between mb-1">
          <div>
            <h3 className="text-base font-semibold">Assessment Schedule</h3>
            {instructorName && (
              <p className="text-sm text-muted-foreground">{instructorName}</p>
            )}
          </div>
          <span className="text-[10px] font-semibold text-primary bg-primary/10 px-2.5 py-1 rounded-full">
            Auto-extracted
          </span>
        </div>
        <p className="text-xs text-muted-foreground mb-4">
          {syllabusFileName ? `From ${syllabusFileName}` : "Extracted from syllabus"}
          {reviewedAt ? " \u00b7 Reviewed and confirmed" : ""}
        </p>

        {loading ? (
          <div className="space-y-2">
            {[1, 2, 3].map((i) => (
              <div key={i} className="h-10 rounded-lg bg-muted/50 animate-pulse" />
            ))}
          </div>
        ) : sorted.length === 0 ? (
          <p className="text-sm text-muted-foreground py-4 text-center">
            No assessments extracted yet.
          </p>
        ) : (
          <>
            {/* Table header — hidden on small screens */}
            <div className="hidden sm:grid grid-cols-[2fr_1fr_0.8fr_1.2fr] gap-3 px-3 mb-2">
              <span className="text-[11px] font-semibold text-muted-foreground uppercase tracking-wider">
                Assessment
              </span>
              <span className="text-[11px] font-semibold text-muted-foreground uppercase tracking-wider">
                Date
              </span>
              <span className="text-[11px] font-semibold text-muted-foreground uppercase tracking-wider">
                Weight
              </span>
              <span className="text-[11px] font-semibold text-muted-foreground uppercase tracking-wider">
                Readiness
              </span>
            </div>

            {/* Rows */}
            <div className="space-y-1">
              {sorted.map((assessment, i) => {
                const readinessPct = readinessMap.get(assessment.id) ?? null;
                const formattedDate = assessment.due_date
                  ? format(new Date(assessment.due_date), "MMM d")
                  : "Ongoing";

                return (
                  <div
                    key={assessment.id}
                    className={cn(
                      "sm:grid sm:grid-cols-[2fr_1fr_0.8fr_1.2fr] gap-3 px-3 py-2.5 rounded-lg items-center",
                      "flex flex-col sm:flex-row",
                      i % 2 === 0 ? "bg-muted/50" : "bg-background",
                    )}
                  >
                    {/* Name */}
                    <span className="text-sm font-medium text-foreground truncate w-full sm:w-auto">
                      {assessment.title}
                    </span>

                    {/* Date */}
                    <span className="text-sm text-muted-foreground">
                      {formattedDate}
                    </span>

                    {/* Weight */}
                    <span className="text-sm text-muted-foreground font-medium">
                      {assessment.weight_percent != null
                        ? `${assessment.weight_percent}%`
                        : "\u2014"}
                    </span>

                    {/* Readiness */}
                    <div className="flex items-center gap-2 w-full sm:w-auto">
                      {readinessPct != null ? (
                        <>
                          <div className="flex-1 h-1.5 rounded-full bg-muted overflow-hidden">
                            <div
                              className={cn(
                                "h-full rounded-full transition-all",
                                readinessPct >= 70
                                  ? "bg-green-500"
                                  : readinessPct >= 40
                                    ? "bg-amber-500"
                                    : "bg-red-500",
                              )}
                              style={{ width: `${readinessPct}%` }}
                            />
                          </div>
                          <span
                            className={cn(
                              "text-xs font-semibold tabular-nums min-w-[28px] text-right",
                              readinessPct >= 70
                                ? "text-green-600"
                                : readinessPct >= 40
                                  ? "text-amber-600"
                                  : "text-red-600",
                            )}
                          >
                            {readinessPct}%
                          </span>
                        </>
                      ) : (
                        <span className="text-xs text-muted-foreground">
                          {"\u2014"}
                        </span>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          </>
        )}

        {/* Grade breakdown collapsible */}
        {gradeBreakdown && gradeBreakdown.length > 0 && (
          <details className="mt-3">
            <summary className="text-xs font-medium text-muted-foreground cursor-pointer hover:text-foreground transition-colors">
              View grade component weights
            </summary>
            <div className="mt-2 space-y-1.5 pl-2">
              {gradeBreakdown.map((item, i) => (
                <div
                  key={i}
                  className="flex items-center justify-between text-sm"
                >
                  <span className="text-muted-foreground">
                    {item.component}
                  </span>
                  <span className="font-medium tabular-nums">
                    {item.weight}%
                  </span>
                </div>
              ))}
            </div>
          </details>
        )}

        {/* Footer */}
        <div className="flex items-center gap-2 mt-4 pt-3 border-t border-border">
          <FileText className="h-3.5 w-3.5 text-primary" />
          <span className="text-xs text-primary font-medium">
            Concepts linked to assessments automatically
          </span>
        </div>
      </CardContent>
    </Card>
  );
}
