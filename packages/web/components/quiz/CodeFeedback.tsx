"use client";

import { useState } from "react";
import { ChevronDown, ChevronUp } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible";
import { CodeEditor } from "@/components/quiz/CodeEditor";
import { cn } from "@/lib/utils";
import type { CodeGradingResult } from "@/types/database";

interface CodeFeedbackProps {
  result: CodeGradingResult;
  referenceCode?: string;
  showReference: boolean;
  language?: string;
}

function ScoreBar({ score }: { score: number }) {
  const color =
    score > 70
      ? "bg-green-500"
      : score >= 40
        ? "bg-yellow-500"
        : "bg-red-500";

  return (
    <div className="space-y-2">
      <div className="flex items-baseline justify-between">
        <span className="text-3xl font-bold">{Math.round(score)}</span>
        <span className="text-lg text-muted-foreground">/ 100</span>
      </div>
      <div className="h-2.5 w-full overflow-hidden rounded-full bg-muted">
        <div
          className={cn("h-full rounded-full transition-all duration-500", color)}
          style={{ width: `${Math.min(score, 100)}%` }}
        />
      </div>
    </div>
  );
}

function RubricIcon({ ratio }: { ratio: number }) {
  if (ratio > 0.7) return <span title="Good">&#9989;</span>;
  if (ratio >= 0.4) return <span title="Needs work">&#9888;&#65039;</span>;
  return <span title="Poor">&#10060;</span>;
}

export function CodeFeedback({
  result,
  referenceCode,
  showReference,
  language = "python",
}: CodeFeedbackProps) {
  const [rubricOpen, setRubricOpen] = useState(true);
  const [improvementOpen, setImprovementOpen] = useState(false);
  const [referenceOpen, setReferenceOpen] = useState(false);

  return (
    <div className="space-y-4">
      {/* Score bar */}
      <Card>
        <CardContent className="pt-6">
          <ScoreBar score={result.overall_score} />
        </CardContent>
      </Card>

      {/* Rubric breakdown */}
      <Collapsible open={rubricOpen} onOpenChange={setRubricOpen}>
        <CollapsibleTrigger asChild>
          <Button
            variant="ghost"
            className="w-full justify-between px-3 font-medium"
          >
            Rubric Breakdown
            {rubricOpen ? (
              <ChevronUp className="h-4 w-4" />
            ) : (
              <ChevronDown className="h-4 w-4" />
            )}
          </Button>
        </CollapsibleTrigger>
        <CollapsibleContent>
          <div className="space-y-2 pt-1">
            {Object.entries(result.rubric_scores).map(
              ([criterion, data]) => {
                const ratio =
                  data.max_weight > 0 ? data.score / data.max_weight : 0;
                return (
                  <Card key={criterion}>
                    <CardContent className="py-3 px-4 space-y-1">
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-2">
                          <RubricIcon ratio={ratio} />
                          <span className="text-sm font-medium">
                            {criterion}
                          </span>
                        </div>
                        <span className="text-sm text-muted-foreground tabular-nums">
                          {data.score} / {data.max_weight}
                        </span>
                      </div>
                      <p className="text-sm text-muted-foreground">
                        {data.feedback}
                      </p>
                    </CardContent>
                  </Card>
                );
              },
            )}
          </div>
        </CollapsibleContent>
      </Collapsible>

      {/* Overall feedback */}
      <Card className="border-blue-200 bg-blue-50/50 dark:border-blue-900 dark:bg-blue-950/30">
        <CardContent className="py-4 px-4">
          <p className="text-sm font-medium mb-1">Feedback</p>
          <p className="text-sm text-muted-foreground">
            {result.overall_feedback}
          </p>
        </CardContent>
      </Card>

      {/* Concepts */}
      {(result.concepts_demonstrated.length > 0 ||
        result.concepts_lacking.length > 0) && (
        <div className="space-y-2">
          {result.concepts_demonstrated.length > 0 && (
            <div className="flex flex-wrap items-center gap-1.5">
              <span className="text-xs font-medium text-muted-foreground mr-1">
                Demonstrated:
              </span>
              {result.concepts_demonstrated.map((c) => (
                <Badge
                  key={c}
                  variant="outline"
                  className="border-green-300 text-green-700 dark:border-green-800 dark:text-green-400"
                >
                  {c}
                </Badge>
              ))}
            </div>
          )}
          {result.concepts_lacking.length > 0 && (
            <div className="flex flex-wrap items-center gap-1.5">
              <span className="text-xs font-medium text-muted-foreground mr-1">
                Needs work:
              </span>
              {result.concepts_lacking.map((c) => (
                <Badge
                  key={c}
                  variant="outline"
                  className="border-orange-300 text-orange-700 dark:border-orange-800 dark:text-orange-400"
                >
                  {c}
                </Badge>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Suggested improvement */}
      {result.suggested_improvement && (
        <Collapsible open={improvementOpen} onOpenChange={setImprovementOpen}>
          <CollapsibleTrigger asChild>
            <Button
              variant="ghost"
              className="w-full justify-between px-3 font-medium"
            >
              Suggested Improvement
              {improvementOpen ? (
                <ChevronUp className="h-4 w-4" />
              ) : (
                <ChevronDown className="h-4 w-4" />
              )}
            </Button>
          </CollapsibleTrigger>
          <CollapsibleContent>
            <div className="pt-1">
              <CodeEditor
                language={language}
                initialCode={result.suggested_improvement}
                readOnly
              />
            </div>
          </CollapsibleContent>
        </Collapsible>
      )}

      {/* Reference solution */}
      {showReference && referenceCode && (
        <Collapsible open={referenceOpen} onOpenChange={setReferenceOpen}>
          <CollapsibleTrigger asChild>
            <Button
              variant="ghost"
              className="w-full justify-between px-3 font-medium"
            >
              Reference Solution
              {referenceOpen ? (
                <ChevronUp className="h-4 w-4" />
              ) : (
                <ChevronDown className="h-4 w-4" />
              )}
            </Button>
          </CollapsibleTrigger>
          <CollapsibleContent>
            <div className="pt-1 space-y-2">
              <p className="text-xs text-muted-foreground italic px-1">
                This is one possible solution — your approach may be equally
                valid.
              </p>
              <CodeEditor
                language={language}
                initialCode={referenceCode}
                readOnly
              />
            </div>
          </CollapsibleContent>
        </Collapsible>
      )}
    </div>
  );
}
