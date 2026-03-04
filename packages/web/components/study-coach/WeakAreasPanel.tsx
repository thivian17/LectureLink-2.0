"use client";

import { useRouter } from "next/navigation";
import { AlertTriangle, Zap, TrendingDown } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import type { ConceptMastery } from "@/types/database";

interface WeakAreasPanelProps {
  concepts: ConceptMastery[];
  weakConceptIds: string[];
  courseId: string;
}

export function WeakAreasPanel({
  concepts,
  weakConceptIds,
  courseId,
}: WeakAreasPanelProps) {
  const router = useRouter();
  const weakConcepts = concepts
    .filter((c) => weakConceptIds.includes(c.concept_id))
    .sort((a, b) => a.mastery - b.mastery)
    .slice(0, 8);

  const declining = concepts
    .filter(
      (c) => c.trend === "declining" && !weakConceptIds.includes(c.concept_id),
    )
    .slice(0, 3);

  if (weakConcepts.length === 0 && declining.length === 0) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Focus Areas</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-muted-foreground">
            No weak areas detected. Keep up the great work!
          </p>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between">
        <CardTitle className="text-base">Focus Areas</CardTitle>
        <Button
          size="sm"
          onClick={() =>
            router.push(
              `/dashboard/courses/${courseId}/quizzes?difficulty=adaptive`,
            )
          }
        >
          <Zap className="mr-1 h-3 w-3" />
          Adaptive Quiz
        </Button>
      </CardHeader>
      <CardContent className="space-y-3">
        {weakConcepts.map((c) => (
          <div key={c.concept_id} className="flex items-start gap-2 text-sm">
            <AlertTriangle className="h-4 w-4 text-orange-500 shrink-0 mt-0.5" />
            <div className="min-w-0">
              <p className="font-medium truncate">{c.title}</p>
              <p className="text-xs text-muted-foreground">
                {c.total_attempts > 0 ? (
                  <>Mastery: {Math.round(c.mastery * 100)}% ({c.correct_attempts}/{c.total_attempts} correct)</>
                ) : (
                  <>Not Yet Assessed</>
                )}
              </p>
              {c.linked_assessments.length > 0 && (
                <div className="flex flex-wrap gap-1 mt-1">
                  {c.linked_assessments.slice(0, 2).map((a) => (
                    <Badge
                      key={a.assessment_id}
                      variant="outline"
                      className="text-xs"
                    >
                      {a.title}
                    </Badge>
                  ))}
                </div>
              )}
            </div>
          </div>
        ))}
        {declining.map((c) => (
          <div key={c.concept_id} className="flex items-start gap-2 text-sm">
            <TrendingDown className="h-4 w-4 text-red-500 shrink-0 mt-0.5" />
            <div className="min-w-0">
              <p className="font-medium truncate">{c.title}</p>
              <p className="text-xs text-muted-foreground">
                Declining &mdash; was at {Math.round(c.accuracy * 100)}%, now{" "}
                {Math.round(c.recent_accuracy * 100)}%
              </p>
            </div>
          </div>
        ))}
      </CardContent>
    </Card>
  );
}
