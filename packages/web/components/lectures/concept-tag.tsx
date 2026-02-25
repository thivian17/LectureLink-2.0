"use client";

import { cn } from "@/lib/utils";
import { getConceptColor } from "@/lib/concept-colors";
import type { LectureConcept } from "@/types/database";

interface ConceptTagProps {
  concept: LectureConcept;
  onClick: (conceptId: string) => void;
}

export function ConceptTag({ concept, onClick }: ConceptTagProps) {
  const colors = getConceptColor(concept.category);

  return (
    <span
      role="button"
      tabIndex={0}
      onClick={(e) => {
        e.stopPropagation();
        onClick(concept.id);
      }}
      onKeyDown={(e) => {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          e.stopPropagation();
          onClick(concept.id);
        }
      }}
      className={cn(
        "inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium",
        "transition-colors hover:opacity-80 cursor-pointer",
        colors.bg,
        colors.text,
      )}
    >
      <span className={cn("h-1.5 w-1.5 rounded-full", colors.dot)} />
      {concept.title}
    </span>
  );
}
