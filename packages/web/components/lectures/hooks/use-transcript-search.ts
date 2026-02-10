"use client";

import { useState, useMemo, useCallback } from "react";
import type { TranscriptSegment } from "@/types/database";

export interface TranscriptSearchState {
  query: string;
  setQuery: (q: string) => void;
  filteredIndices: number[];
  clearSearch: () => void;
  isSearching: boolean;
}

export function useTranscriptSearch(
  segments: TranscriptSegment[],
): TranscriptSearchState {
  const [query, setQuery] = useState("");

  const filteredIndices = useMemo(() => {
    if (!query.trim()) return [];
    const lower = query.toLowerCase();
    const indices: number[] = [];
    for (let i = 0; i < segments.length; i++) {
      if (segments[i].text.toLowerCase().includes(lower)) {
        indices.push(i);
      }
    }
    return indices;
  }, [segments, query]);

  const clearSearch = useCallback(() => setQuery(""), []);

  return {
    query,
    setQuery,
    filteredIndices,
    clearSearch,
    isSearching: query.trim().length > 0,
  };
}
