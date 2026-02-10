"use client";

import { useRef, useEffect, useCallback, useMemo } from "react";
import { useVirtualizer } from "@tanstack/react-virtual";
import { Search, X } from "lucide-react";

import { cn } from "@/lib/utils";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { formatTimestamp } from "@/lib/format";
import { ConceptTag } from "@/components/lectures/concept-tag";
import type { TranscriptSegment, LectureConcept } from "@/types/database";

interface TranscriptViewerProps {
  segments: TranscriptSegment[];
  concepts: LectureConcept[];
  activeSegmentIndex: number;
  onSegmentClick: (index: number) => void;
  onConceptClick: (conceptId: string) => void;
  searchQuery: string;
  onSearchChange: (q: string) => void;
  onClearSearch: () => void;
  filteredIndices: number[];
  isSearching: boolean;
  className?: string;
}

function highlightText(text: string, query: string) {
  if (!query.trim()) return text;
  const regex = new RegExp(`(${query.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")})`, "gi");
  const parts = text.split(regex);
  return parts.map((part, i) =>
    regex.test(part) ? (
      <mark key={i} className="bg-yellow-200 rounded-sm">
        {part}
      </mark>
    ) : (
      part
    ),
  );
}

export function TranscriptViewer({
  segments,
  concepts,
  activeSegmentIndex,
  onSegmentClick,
  onConceptClick,
  searchQuery,
  onSearchChange,
  onClearSearch,
  filteredIndices,
  isSearching,
  className,
}: TranscriptViewerProps) {
  const parentRef = useRef<HTMLDivElement>(null);

  const conceptsBySegment = useMemo(() => {
    const map = new Map<number, LectureConcept[]>();
    for (const concept of concepts) {
      for (const idx of concept.segment_indices) {
        const existing = map.get(idx) ?? [];
        existing.push(concept);
        map.set(idx, existing);
      }
    }
    return map;
  }, [concepts]);

  const displayIndices = useMemo(() => {
    if (!isSearching) return segments.map((_, i) => i);
    return filteredIndices;
  }, [segments, filteredIndices, isSearching]);

  const virtualizer = useVirtualizer({
    count: displayIndices.length,
    getScrollElement: () => parentRef.current,
    estimateSize: () => 72,
    overscan: 20,
  });

  // Auto-scroll to active segment during playback
  const prevActiveRef = useRef(activeSegmentIndex);
  useEffect(() => {
    if (
      activeSegmentIndex >= 0 &&
      activeSegmentIndex !== prevActiveRef.current &&
      !isSearching
    ) {
      const virtualIndex = displayIndices.indexOf(activeSegmentIndex);
      if (virtualIndex >= 0) {
        virtualizer.scrollToIndex(virtualIndex, { align: "center", behavior: "smooth" });
      }
    }
    prevActiveRef.current = activeSegmentIndex;
  }, [activeSegmentIndex, displayIndices, virtualizer, isSearching]);

  const shouldShowSlideBoundary = useCallback(
    (displayIdx: number) => {
      if (displayIdx === 0) return false;
      const currSegIdx = displayIndices[displayIdx];
      const prevSegIdx = displayIndices[displayIdx - 1];
      const curr = segments[currSegIdx];
      const prev = segments[prevSegIdx];
      return (
        curr.slide_number !== null &&
        prev.slide_number !== null &&
        curr.slide_number !== prev.slide_number
      );
    },
    [displayIndices, segments],
  );

  return (
    <div className={cn("flex flex-col min-h-0", className)}>
      {/* Search bar */}
      <div className="flex items-center gap-2 border-b px-3 py-2">
        <Search className="h-4 w-4 text-muted-foreground shrink-0" />
        <Input
          placeholder="Search transcript..."
          value={searchQuery}
          onChange={(e) => onSearchChange(e.target.value)}
          className="h-7 text-sm border-0 shadow-none focus-visible:ring-0 px-0"
        />
        {isSearching && (
          <div className="flex items-center gap-1 shrink-0">
            <span className="text-xs text-muted-foreground">
              {filteredIndices.length} match{filteredIndices.length !== 1 ? "es" : ""}
            </span>
            <Button
              variant="ghost"
              size="sm"
              onClick={onClearSearch}
              className="h-6 w-6 p-0"
            >
              <X className="h-3 w-3" />
            </Button>
          </div>
        )}
      </div>

      {/* Virtualized segment list */}
      <div ref={parentRef} className="flex-1 overflow-auto">
        <div
          style={{
            height: `${virtualizer.getTotalSize()}px`,
            width: "100%",
            position: "relative",
          }}
        >
          {virtualizer.getVirtualItems().map((virtualItem) => {
            const segmentIndex = displayIndices[virtualItem.index];
            const segment = segments[segmentIndex];
            const segmentConcepts = conceptsBySegment.get(segmentIndex) ?? [];
            const isActive = segmentIndex === activeSegmentIndex;
            const showBoundary = shouldShowSlideBoundary(virtualItem.index);

            return (
              <div
                key={virtualItem.key}
                data-index={virtualItem.index}
                ref={virtualizer.measureElement}
                style={{
                  position: "absolute",
                  top: 0,
                  left: 0,
                  width: "100%",
                  transform: `translateY(${virtualItem.start}px)`,
                }}
              >
                {showBoundary && (
                  <div className="flex items-center gap-2 px-3 py-1">
                    <div className="flex-1 border-t border-dashed" />
                    <Badge variant="outline" className="text-[10px] px-1.5 py-0">
                      Slide {segment.slide_number}
                    </Badge>
                    <div className="flex-1 border-t border-dashed" />
                  </div>
                )}
                <button
                  type="button"
                  onClick={() => onSegmentClick(segmentIndex)}
                  className={cn(
                    "w-full text-left px-3 py-2 flex gap-3 transition-colors",
                    "hover:bg-accent/50 cursor-pointer",
                    isActive && "bg-accent border-l-2 border-l-primary",
                    !isActive && "border-l-2 border-l-transparent",
                  )}
                >
                  {/* Timestamp */}
                  <span className="text-xs font-mono text-muted-foreground shrink-0 pt-0.5 w-10 text-right">
                    {segment.start !== null
                      ? `[${formatTimestamp(segment.start)}]`
                      : ""}
                  </span>

                  {/* Content */}
                  <div className="min-w-0 flex-1 space-y-1">
                    <div className="flex items-baseline gap-2">
                      <span
                        className={cn(
                          "text-[10px] uppercase font-medium shrink-0",
                          segment.speaker === "student"
                            ? "text-green-600"
                            : "text-muted-foreground",
                        )}
                      >
                        {segment.speaker}
                      </span>
                    </div>
                    <p className="text-sm leading-relaxed">
                      {highlightText(segment.text, searchQuery)}
                    </p>
                    {segmentConcepts.length > 0 && (
                      <div className="flex flex-wrap gap-1 pt-1">
                        {segmentConcepts.map((concept) => (
                          <ConceptTag
                            key={concept.id}
                            concept={concept}
                            onClick={onConceptClick}
                          />
                        ))}
                      </div>
                    )}
                  </div>
                </button>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
