"use client";

import { useMemo, useState } from "react";
import { BookOpen, Clock, Target, SlidersHorizontal, Check } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible";
import { cn } from "@/lib/utils";
import type {
  DailyBriefing as DailyBriefingType,
  AvailableConcept,
} from "@/types/database";

interface DailyBriefingProps {
  briefing: DailyBriefingType;
  timeBudget: number;
  onTimeBudgetChange: (minutes: number) => void;
  onStart: () => void;
  onCustomize?: (options: {
    targetAssessmentId?: string;
    targetLectureId?: string;
    targetConceptIds?: string[];
  }) => void;
  starting?: boolean;
  streak?: number;
  lectures?: { lecture_id: string; title: string; avg_mastery: number; concept_count: number }[];
}

const TIME_OPTIONS = [10, 15, 20, 25];

function getMotivationalMessage(
  streak: number,
  conceptCount: number,
  hour: number,
): string {
  if (hour < 12) {
    const morningMsgs = [
      "Early bird catches the grade! Let's make this count.",
      "Morning study sessions are proven to boost retention.",
    ];
    return morningMsgs[Math.floor(Math.random() * morningMsgs.length)];
  }
  if (streak >= 7) return "Week-long streak! You're building serious momentum.";
  if (streak >= 3) return `${streak}-day streak going strong! Keep it up.`;
  if (conceptCount >= 3)
    return "Big session planned \u2014 let's tackle this step by step.";
  return "Ready to level up? Let's dive in.";
}

export function DailyBriefing({
  briefing,
  timeBudget,
  onTimeBudgetChange,
  onStart,
  onCustomize,
  starting,
  streak = 0,
  lectures,
}: DailyBriefingProps) {
  const [customizeOpen, setCustomizeOpen] = useState(false);
  const [selectedLectureId, setSelectedLectureId] = useState<string | null>(null);
  const [selectedConceptIds, setSelectedConceptIds] = useState<Set<string>>(new Set());
  const [customizeMode, setCustomizeMode] = useState<"lecture" | "concepts" | null>(null);

  const motivationalMsg = useMemo(
    () =>
      getMotivationalMessage(
        streak,
        briefing.concepts_planned.length,
        new Date().getHours(),
      ),
    [streak, briefing.concepts_planned.length],
  );

  const hasOptions =
    (briefing.available_assessments?.length ?? 0) > 0 ||
    (briefing.available_concepts?.length ?? 0) > 0;

  function toggleConcept(conceptId: string) {
    setSelectedConceptIds((prev) => {
      const next = new Set(prev);
      if (next.has(conceptId)) next.delete(conceptId);
      else next.add(conceptId);
      return next;
    });
  }

  function handleApplyCustom() {
    if (!onCustomize) return;
    if (customizeMode === "lecture" && selectedLectureId) {
      onCustomize({ targetLectureId: selectedLectureId });
    } else if (customizeMode === "concepts" && selectedConceptIds.size > 0) {
      onCustomize({ targetConceptIds: Array.from(selectedConceptIds) });
    }
    setCustomizeOpen(false);
  }

  function handleResetToRecommended() {
    setCustomizeMode(null);
    setSelectedLectureId(null);
    setSelectedConceptIds(new Set());
    if (onCustomize) onCustomize({});
    setCustomizeOpen(false);
  }

  return (
    <Card className="max-w-lg mx-auto">
      <CardHeader className="text-center pb-3">
        <CardTitle className="text-xl">{briefing.course_name}</CardTitle>
        <p className="text-sm text-muted-foreground">
          {briefing.is_custom ? "Custom session" : briefing.focus_description}
        </p>
        <p className="text-xs text-muted-foreground/80 mt-1 italic">
          {motivationalMsg}
        </p>
      </CardHeader>
      <CardContent className="space-y-5">
        {briefing.assessment_context && (
          <div className="flex items-start gap-2 rounded-lg bg-amber-50 dark:bg-amber-950/30 border border-amber-200 dark:border-amber-800 p-3 text-sm">
            <Target className="h-4 w-4 text-amber-600 mt-0.5 shrink-0" />
            <span className="text-amber-800 dark:text-amber-200">
              {briefing.assessment_context}
            </span>
          </div>
        )}

        <div>
          <p className="text-sm font-medium mb-2 flex items-center gap-1.5">
            <BookOpen className="h-4 w-4 text-muted-foreground" />
            {briefing.is_custom ? "Selected concepts" : "Today\u2019s concepts"}
          </p>
          {briefing.concepts_planned.length === 0 ? (
            <p className="text-sm text-muted-foreground italic">
              No concepts loaded yet &mdash; upload lectures or complete a quiz
              to get started.
            </p>
          ) : (
            <div className="flex flex-wrap gap-1.5">
              {briefing.concepts_planned.map((c, i) => (
                <Badge
                  key={c.concept_id}
                  variant="secondary"
                  className="text-xs animate-in fade-in slide-in-from-bottom-1 duration-300"
                  style={{
                    animationDelay: `${i * 75}ms`,
                    animationFillMode: "both",
                  }}
                >
                  {c.title}
                  <span className="ml-1 text-muted-foreground">
                    {(c.total_attempts ?? 0) > 0
                      ? `${Math.round(c.mastery * 100)}%`
                      : "New"}
                  </span>
                </Badge>
              ))}
            </div>
          )}
        </div>

        {/* Customize Focus */}
        {hasOptions && onCustomize && (
          <Collapsible open={customizeOpen} onOpenChange={setCustomizeOpen}>
            <CollapsibleTrigger asChild>
              <Button variant="ghost" size="sm" className="w-full justify-center gap-1.5 text-muted-foreground">
                <SlidersHorizontal className="h-3.5 w-3.5" />
                {customizeOpen ? "Hide options" : "Customize focus"}
              </Button>
            </CollapsibleTrigger>
            <CollapsibleContent className="pt-3 space-y-4">
              {/* Mode selector */}
              <div className="flex gap-2">
                <Button
                  size="sm"
                  variant={customizeMode === "lecture" ? "default" : "outline"}
                  className="flex-1"
                  onClick={() => {
                    setCustomizeMode("lecture");
                    setSelectedConceptIds(new Set());
                  }}
                >
                  By lecture
                </Button>
                <Button
                  size="sm"
                  variant={customizeMode === "concepts" ? "default" : "outline"}
                  className="flex-1"
                  onClick={() => {
                    setCustomizeMode("concepts");
                    setSelectedLectureId(null);
                  }}
                >
                  By concept
                </Button>
              </div>

              {/* Lecture picker */}
              {customizeMode === "lecture" && (lectures?.length ?? 0) > 0 && (
                <div className="space-y-1.5 max-h-48 overflow-y-auto">
                  {lectures!.map((lec) => (
                    <button
                      key={lec.lecture_id}
                      type="button"
                      className={cn(
                        "w-full text-left rounded-lg border p-2.5 text-sm transition-colors",
                        selectedLectureId === lec.lecture_id
                          ? "border-primary bg-primary/5"
                          : "hover:bg-muted/50",
                      )}
                      onClick={() => setSelectedLectureId(lec.lecture_id)}
                    >
                      <div className="flex items-center justify-between">
                        <span className="font-medium">{lec.title}</span>
                        {selectedLectureId === lec.lecture_id && (
                          <Check className="h-4 w-4 text-primary" />
                        )}
                      </div>
                      <div className="flex gap-2 mt-0.5">
                        <span className="text-xs text-muted-foreground">
                          {lec.concept_count} concepts
                        </span>
                        <span className="text-xs text-muted-foreground">
                          {Math.round(lec.avg_mastery * 100)}% mastery
                        </span>
                      </div>
                    </button>
                  ))}
                </div>
              )}

              {/* Concept picker */}
              {customizeMode === "concepts" && (briefing.available_concepts?.length ?? 0) > 0 && (
                <div className="space-y-1 max-h-48 overflow-y-auto">
                  {briefing.available_concepts!.map((c) => (
                    <button
                      key={c.concept_id}
                      type="button"
                      className={cn(
                        "w-full text-left rounded-lg border p-2 text-sm transition-colors flex items-center gap-2",
                        selectedConceptIds.has(c.concept_id)
                          ? "border-primary bg-primary/5"
                          : "hover:bg-muted/50",
                      )}
                      onClick={() => toggleConcept(c.concept_id)}
                    >
                      <div className={cn(
                        "h-4 w-4 rounded border-2 shrink-0 flex items-center justify-center",
                        selectedConceptIds.has(c.concept_id)
                          ? "border-primary bg-primary"
                          : "border-muted-foreground/30",
                      )}>
                        {selectedConceptIds.has(c.concept_id) && (
                          <Check className="h-3 w-3 text-primary-foreground" />
                        )}
                      </div>
                      <span className="flex-1 truncate">{c.title}</span>
                      <span className="text-xs text-muted-foreground shrink-0">
                        {c.total_attempts > 0 ? `${Math.round(c.mastery * 100)}%` : "New"}
                      </span>
                    </button>
                  ))}
                </div>
              )}

              {/* Apply / Reset buttons */}
              {customizeMode && (
                <div className="flex gap-2">
                  <Button
                    variant="outline"
                    size="sm"
                    className="flex-1"
                    onClick={handleResetToRecommended}
                  >
                    Reset to recommended
                  </Button>
                  <Button
                    size="sm"
                    className="flex-1"
                    onClick={handleApplyCustom}
                    disabled={
                      (customizeMode === "lecture" && !selectedLectureId) ||
                      (customizeMode === "concepts" && selectedConceptIds.size === 0)
                    }
                  >
                    Apply
                  </Button>
                </div>
              )}
            </CollapsibleContent>
          </Collapsible>
        )}

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
