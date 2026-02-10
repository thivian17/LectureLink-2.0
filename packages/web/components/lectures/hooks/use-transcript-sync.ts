"use client";

import { useMemo } from "react";
import type { TranscriptSegment } from "@/types/database";

export interface TranscriptSyncState {
  activeSegmentIndex: number;
  activeSlideNumber: number | null;
}

export function useTranscriptSync(
  segments: TranscriptSegment[],
  currentTime: number,
): TranscriptSyncState {
  const activeSegmentIndex = useMemo(() => {
    if (segments.length === 0) return -1;
    for (let i = 0; i < segments.length; i++) {
      const seg = segments[i];
      if (
        seg.start !== null &&
        seg.end !== null &&
        seg.start <= currentTime &&
        currentTime < seg.end
      ) {
        return i;
      }
    }
    return -1;
  }, [segments, currentTime]);

  const activeSlideNumber = useMemo(() => {
    if (activeSegmentIndex < 0) return null;
    return segments[activeSegmentIndex].slide_number;
  }, [segments, activeSegmentIndex]);

  return { activeSegmentIndex, activeSlideNumber };
}
