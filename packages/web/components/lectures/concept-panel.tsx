"use client";

import { format } from "date-fns";
import { BookOpen, Target } from "lucide-react";

import { cn } from "@/lib/utils";
import { Badge } from "@/components/ui/badge";
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet";
import { getConceptColor } from "@/lib/concept-colors";
import type { LectureConcept } from "@/types/database";

interface ConceptPanelProps {
  concept: LectureConcept | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

function DifficultyBar({ value }: { value: number }) {
  const label =
    value < 0.33 ? "Beginner" : value < 0.66 ? "Intermediate" : "Advanced";
  const color =
    value < 0.33
      ? "bg-green-500"
      : value < 0.66
        ? "bg-amber-500"
        : "bg-red-500";

  return (
    <div className="space-y-1">
      <div className="flex justify-between text-xs text-muted-foreground">
        <span>Difficulty</span>
        <span>{label}</span>
      </div>
      <div className="h-1.5 rounded-full bg-muted">
        <div
          className={cn("h-full rounded-full transition-all", color)}
          style={{ width: `${value * 100}%` }}
        />
      </div>
    </div>
  );
}

function RelevanceBar({ score }: { score: number }) {
  return (
    <div className="h-1 rounded-full bg-muted flex-1 max-w-20">
      <div
        className="h-full rounded-full bg-primary transition-all"
        style={{ width: `${score * 100}%` }}
      />
    </div>
  );
}

export function ConceptPanel({
  concept,
  open,
  onOpenChange,
}: ConceptPanelProps) {
  if (!concept) return null;

  const colors = getConceptColor(concept.category);

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent className="w-[400px] sm:w-[400px] overflow-auto">
        <SheetHeader>
          <div className="flex items-center gap-2">
            <Badge className={cn("text-xs", colors.bg, colors.text)}>
              {concept.category}
            </Badge>
          </div>
          <SheetTitle className="text-xl">{concept.title}</SheetTitle>
          {concept.description && (
            <SheetDescription className="text-sm leading-relaxed">
              {concept.description}
            </SheetDescription>
          )}
        </SheetHeader>

        <div className="space-y-6 mt-6">
          {/* Difficulty */}
          <DifficultyBar value={concept.difficulty_estimate} />

          {/* Segment mentions */}
          <div className="flex items-center gap-2 text-sm text-muted-foreground">
            <BookOpen className="h-4 w-4" />
            <span>
              Mentioned in {concept.segment_indices.length} segment
              {concept.segment_indices.length !== 1 ? "s" : ""}
            </span>
          </div>

          {/* Related assessments */}
          {concept.linked_assessments.length > 0 && (
            <div className="space-y-3">
              <div className="flex items-center gap-2 text-sm font-medium">
                <Target className="h-4 w-4" />
                Related Assessments
              </div>
              <div className="space-y-2">
                {concept.linked_assessments.map((assessment) => (
                  <div
                    key={assessment.id}
                    className="flex items-center justify-between gap-2 rounded-lg border p-3"
                  >
                    <div className="min-w-0">
                      <p className="text-sm font-medium truncate">
                        {assessment.title}
                      </p>
                      {assessment.due_date && (
                        <p className="text-xs text-muted-foreground">
                          Due{" "}
                          {format(new Date(assessment.due_date), "MMM d, yyyy")}
                        </p>
                      )}
                    </div>
                    <div className="flex items-center gap-2 shrink-0">
                      <span className="text-xs text-muted-foreground">
                        {Math.round(assessment.relevance_score * 100)}%
                      </span>
                      <RelevanceBar score={assessment.relevance_score} />
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      </SheetContent>
    </Sheet>
  );
}
