"use client";

import { useState } from "react";
import { ChevronDown, ChevronRight } from "lucide-react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import { Skeleton } from "@/components/ui/skeleton";
import { Checkbox } from "@/components/ui/checkbox";
import { cn } from "@/lib/utils";
import type { AssessmentReadiness, ConceptReadiness } from "@/types/database";

interface AssessmentConceptsPanelProps {
  readiness: AssessmentReadiness | null;
  loading: boolean;
  selectable: boolean;
  selectedIds: Set<string>;
  onToggle: (conceptId: string) => void;
  highlightedIds?: Set<string>;
}

interface LectureGroup {
  lectureTitle: string;
  concepts: ConceptReadiness[];
  avgMastery: number;
}

function groupByLecture(concepts: ConceptReadiness[]): LectureGroup[] {
  const groups = new Map<string, ConceptReadiness[]>();
  for (const c of concepts) {
    const key = c.lecture_title ?? "Other";
    const list = groups.get(key);
    if (list) {
      list.push(c);
    } else {
      groups.set(key, [c]);
    }
  }

  return Array.from(groups.entries())
    .map(([lectureTitle, concepts]) => ({
      lectureTitle,
      concepts: concepts.sort((a, b) => a.mastery - b.mastery),
      avgMastery:
        concepts.reduce((s, c) => s + c.mastery, 0) / concepts.length,
    }))
    .sort((a, b) => a.avgMastery - b.avgMastery);
}

export function AssessmentConceptsPanel({
  readiness,
  loading,
  selectable,
  selectedIds,
  onToggle,
  highlightedIds,
}: AssessmentConceptsPanelProps) {
  // Track which lecture groups are expanded — default all open
  const [collapsed, setCollapsed] = useState<Set<string>>(new Set());

  if (loading) {
    return (
      <Card>
        <CardHeader className="pb-3">
          <Skeleton className="h-6 w-48" />
          <Skeleton className="h-4 w-32 mt-1" />
        </CardHeader>
        <CardContent className="space-y-3">
          {Array.from({ length: 5 }).map((_, i) => (
            <div key={i} className="space-y-1">
              <div className="flex items-center justify-between">
                <Skeleton className="h-4 w-40" />
                <Skeleton className="h-4 w-12" />
              </div>
              <Skeleton className="h-1.5 w-full rounded-full" />
            </div>
          ))}
        </CardContent>
      </Card>
    );
  }

  if (!readiness) return null;

  const readyCount = readiness.concepts.filter((c) => c.mastery >= 0.7).length;
  const hasLectureGroups = readiness.concepts.some((c) => c.lecture_title);
  const groups = hasLectureGroups
    ? groupByLecture(readiness.concepts)
    : null;

  function toggleGroup(title: string) {
    setCollapsed((prev) => {
      const next = new Set(prev);
      if (next.has(title)) {
        next.delete(title);
      } else {
        next.add(title);
      }
      return next;
    });
  }

  function statusLabel(mastery: number) {
    if (mastery < 0.4) return "Weak";
    if (mastery <= 0.7) return "Developing";
    return "Strong";
  }

  function statusColor(mastery: number) {
    if (mastery < 0.4) return "text-red-600 border-red-200";
    if (mastery <= 0.7) return "text-yellow-600 border-yellow-200";
    return "text-green-600 border-green-200";
  }

  function barColor(masteryPct: number) {
    if (masteryPct < 40) return "[&>div]:bg-red-500";
    if (masteryPct < 70) return "[&>div]:bg-amber-500";
    return "[&>div]:bg-green-500";
  }

  function renderConcept(concept: ConceptReadiness) {
    const masteryPct = Math.round(concept.mastery * 100);
    const key = concept.concept_id ?? concept.title;
    const isHighlighted = highlightedIds?.has(key);
    const isDimmed =
      highlightedIds && highlightedIds.size > 0 && !isHighlighted;
    return (
      <div
        key={key}
        className={cn(
          "space-y-1 rounded-md px-2 py-1.5 -mx-2 transition-colors",
          isHighlighted && "bg-primary/5 ring-1 ring-primary/20",
          isDimmed && "opacity-50",
        )}
      >
        <div className="flex items-center gap-2 text-sm">
          {selectable && (
            <Checkbox
              checked={selectedIds.has(key)}
              onCheckedChange={() => onToggle(key)}
            />
          )}
          <span className="flex-1 min-w-0 truncate">{concept.title}</span>
          <div className="flex items-center gap-2 shrink-0">
            {isHighlighted && (
              <Badge
                variant="outline"
                className="text-primary border-primary/30 text-[10px]"
              >
                Included
              </Badge>
            )}
            <Badge
              variant="outline"
              className={statusColor(concept.mastery)}
            >
              {statusLabel(concept.mastery)}
            </Badge>
            <span className="text-muted-foreground w-10 text-right">
              {masteryPct}%
            </span>
          </div>
        </div>
        <Progress
          value={masteryPct}
          className={`h-1.5 ${barColor(masteryPct)}`}
        />
      </div>
    );
  }

  return (
    <Card>
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between">
          <CardTitle className="text-base">
            {readiness.assessment_title}
          </CardTitle>
          {readiness.days_remaining != null && (
            <Badge
              variant={
                readiness.days_remaining <= 3 ? "destructive" : "secondary"
              }
            >
              {readiness.days_remaining} day
              {readiness.days_remaining !== 1 ? "s" : ""} remaining
            </Badge>
          )}
        </div>
        {highlightedIds && highlightedIds.size > 0 && (
          <CardDescription>
            The auto plan will cover {highlightedIds.size} concept
            {highlightedIds.size !== 1 ? "s" : ""} this session
          </CardDescription>
        )}
        {selectable && (
          <CardDescription>
            Select the concepts you want to study
          </CardDescription>
        )}
      </CardHeader>
      <CardContent className="space-y-4">
        {groups ? (
          // Grouped by lecture
          <div className="space-y-3">
            {groups.map((group) => {
              const isOpen = !collapsed.has(group.lectureTitle);
              const groupMasteryPct = Math.round(group.avgMastery * 100);
              return (
                <div key={group.lectureTitle}>
                  <button
                    type="button"
                    onClick={() => toggleGroup(group.lectureTitle)}
                    className="flex w-full items-center gap-2 rounded-md px-1 py-1.5 text-left text-sm hover:bg-accent/50 transition-colors"
                  >
                    {isOpen ? (
                      <ChevronDown className="h-4 w-4 shrink-0 text-muted-foreground" />
                    ) : (
                      <ChevronRight className="h-4 w-4 shrink-0 text-muted-foreground" />
                    )}
                    <span className="font-medium flex-1 min-w-0 truncate">
                      {group.lectureTitle}
                    </span>
                    <Badge
                      variant="outline"
                      className={cn(
                        "text-[10px] shrink-0",
                        statusColor(group.avgMastery),
                      )}
                    >
                      {groupMasteryPct}%
                    </Badge>
                    <span className="text-xs text-muted-foreground shrink-0">
                      {group.concepts.length} concept
                      {group.concepts.length !== 1 ? "s" : ""}
                    </span>
                  </button>
                  {isOpen && (
                    <div className="ml-6 mt-1 space-y-2 border-l-2 border-muted pl-3">
                      {group.concepts.map(renderConcept)}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        ) : (
          // Flat list (no lecture info)
          <div className="space-y-3">
            {[...readiness.concepts]
              .sort((a, b) => a.mastery - b.mastery)
              .map(renderConcept)}
          </div>
        )}

        <p className="text-sm text-muted-foreground text-center pt-1">
          {readyCount} of {readiness.concepts.length} concepts at 70%+ mastery
        </p>
      </CardContent>
    </Card>
  );
}
