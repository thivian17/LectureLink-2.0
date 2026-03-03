"use client";

import { BookOpen, Clock, Target } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import type { DailyBriefing as DailyBriefingType } from "@/types/database";

interface DailyBriefingProps {
  briefing: DailyBriefingType;
  timeBudget: number;
  onTimeBudgetChange: (minutes: number) => void;
  onStart: () => void;
  starting?: boolean;
}

const TIME_OPTIONS = [10, 15, 20, 25];

export function DailyBriefing({
  briefing,
  timeBudget,
  onTimeBudgetChange,
  onStart,
  starting,
}: DailyBriefingProps) {
  return (
    <Card className="max-w-lg mx-auto">
      <CardHeader className="text-center pb-3">
        <CardTitle className="text-xl">{briefing.course_name}</CardTitle>
        <p className="text-sm text-muted-foreground">{briefing.focus_description}</p>
      </CardHeader>
      <CardContent className="space-y-5">
        {briefing.assessment_context && (
          <div className="flex items-start gap-2 rounded-lg bg-amber-50 border border-amber-200 p-3 text-sm">
            <Target className="h-4 w-4 text-amber-600 mt-0.5 shrink-0" />
            <span className="text-amber-800">{briefing.assessment_context}</span>
          </div>
        )}

        <div>
          <p className="text-sm font-medium mb-2 flex items-center gap-1.5">
            <BookOpen className="h-4 w-4 text-muted-foreground" />
            Today&apos;s concepts
          </p>
          {briefing.concepts_planned.length === 0 ? (
            <p className="text-sm text-muted-foreground italic">
              No concepts loaded yet — upload lectures or complete a quiz to get started.
            </p>
          ) : (
            <div className="flex flex-wrap gap-1.5">
              {briefing.concepts_planned.map((c) => (
                <Badge key={c.concept_id} variant="secondary" className="text-xs">
                  {c.title || "Untitled concept"}
                  <span className="ml-1 text-muted-foreground">
                    {Math.round(c.mastery * 100)}%
                  </span>
                </Badge>
              ))}
            </div>
          )}
        </div>

        <div>
          <p className="text-sm font-medium mb-2 flex items-center gap-1.5">
            <Clock className="h-4 w-4 text-muted-foreground" />
            Time budget
          </p>
          <div className="flex gap-2">
            {TIME_OPTIONS.map((mins) => (
              <Button
                key={mins}
                size="sm"
                variant={timeBudget === mins ? "default" : "outline"}
                className={cn("flex-1", timeBudget === mins && "shadow-sm")}
                onClick={() => onTimeBudgetChange(mins)}
              >
                {mins} min
              </Button>
            ))}
          </div>
        </div>

        <Button
          size="lg"
          className="w-full h-12 text-base"
          onClick={onStart}
          disabled={starting}
        >
          {starting ? "Starting..." : "Start Session"}
        </Button>
      </CardContent>
    </Card>
  );
}
