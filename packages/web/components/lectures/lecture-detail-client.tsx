"use client";

import { useState, useEffect, useCallback } from "react";
import { Loader2, AlertCircle } from "lucide-react";

import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { getLectureDetail } from "@/lib/api";
import { useAudioPlayer } from "@/components/lectures/hooks/use-audio-player";
import { useTranscriptSync } from "@/components/lectures/hooks/use-transcript-sync";
import { useTranscriptSearch } from "@/components/lectures/hooks/use-transcript-search";
import { LectureSummary } from "@/components/lectures/lecture-summary";
import { TranscriptViewer } from "@/components/lectures/transcript-viewer";
import { SlideViewer } from "@/components/lectures/slide-viewer";
import { AudioPlayerBar } from "@/components/lectures/audio-player-bar";
import { ConceptPanel } from "@/components/lectures/concept-panel";
import { QAChatButton } from "@/components/lectures/qa-chat-button";
import type { LectureDetail, LectureConcept } from "@/types/database";

interface LectureDetailClientProps {
  courseId: string;
  lectureId: string;
}

export function LectureDetailClient({
  courseId,
  lectureId,
}: LectureDetailClientProps) {
  const [lecture, setLecture] = useState<LectureDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Concept panel state
  const [selectedConcept, setSelectedConcept] = useState<LectureConcept | null>(
    null,
  );
  const [conceptPanelOpen, setConceptPanelOpen] = useState(false);

  // Hooks
  const audioPlayer = useAudioPlayer();
  const segments = lecture?.transcript_segments ?? [];
  const { activeSegmentIndex, activeSlideNumber } = useTranscriptSync(
    segments,
    audioPlayer.currentTime,
  );
  const search = useTranscriptSearch(segments);

  // Fetch lecture detail
  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);

    getLectureDetail(lectureId)
      .then((data) => {
        if (!cancelled) setLecture(data);
      })
      .catch((err) => {
        if (!cancelled) setError(err.message || "Failed to load lecture");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [lectureId]);

  // Handlers
  const handleSegmentClick = useCallback(
    (index: number) => {
      const segment = segments[index];
      if (segment?.start !== null) {
        audioPlayer.seek(segment.start!);
      }
    },
    [segments, audioPlayer],
  );

  const handleConceptClick = useCallback(
    (conceptId: string) => {
      const concept = lecture?.concepts.find((c) => c.id === conceptId) ?? null;
      setSelectedConcept(concept);
      setConceptPanelOpen(true);
    },
    [lecture],
  );

  const handleSlideChange = useCallback(
    (slideNumber: number) => {
      // Find first segment with this slide number and seek to it
      const segIndex = segments.findIndex(
        (s) => s.slide_number === slideNumber,
      );
      if (segIndex >= 0 && segments[segIndex].start !== null) {
        audioPlayer.seek(segments[segIndex].start!);
      }
    },
    [segments, audioPlayer],
  );

  // Loading state
  if (loading) {
    return (
      <div className="flex items-center justify-center h-[calc(100vh-4rem)]">
        <div className="flex flex-col items-center gap-3">
          <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
          <p className="text-sm text-muted-foreground">Loading lecture...</p>
        </div>
      </div>
    );
  }

  // Error state
  if (error || !lecture) {
    return (
      <div className="flex items-center justify-center h-[calc(100vh-4rem)]">
        <div className="flex flex-col items-center gap-3 text-center">
          <AlertCircle className="h-8 w-8 text-destructive" />
          <p className="text-sm text-muted-foreground">
            {error || "Lecture not found"}
          </p>
          <Button
            variant="outline"
            size="sm"
            onClick={() => window.location.reload()}
          >
            Retry
          </Button>
        </div>
      </div>
    );
  }

  const hasAudio =
    lecture.processing_path !== "slides_only" && lecture.audio_url;
  const hasSlides =
    lecture.processing_path !== "audio_only" && (lecture.slides?.length ?? 0) > 0;

  return (
    <div className="flex flex-col h-[calc(100vh-4rem)]">
      {/* Summary header */}
      <LectureSummary
        title={lecture.title}
        summary={lecture.summary}
        lectureDate={lecture.lecture_date}
        lectureNumber={lecture.lecture_number}
        durationSeconds={lecture.duration_seconds}
        conceptCount={lecture.concepts?.length ?? 0}
        slideCount={lecture.slide_count ?? lecture.slides?.length ?? 0}
        segmentCount={lecture.transcript_segments?.length ?? 0}
        courseId={courseId}
      />

      {/* Main content area */}
      <div
        className={cn(
          "flex flex-1 min-h-0",
          hasAudio && "pb-16", // space for fixed audio player
        )}
      >
        {/* Transcript panel */}
        <TranscriptViewer
          segments={segments}
          concepts={lecture.concepts}
          activeSegmentIndex={activeSegmentIndex}
          onSegmentClick={handleSegmentClick}
          onConceptClick={handleConceptClick}
          searchQuery={search.query}
          onSearchChange={search.setQuery}
          onClearSearch={search.clearSearch}
          filteredIndices={search.filteredIndices}
          isSearching={search.isSearching}
          className={cn(
            "flex-1 min-w-0",
            hasSlides && "lg:w-3/5 lg:flex-none",
          )}
        />

        {/* Slide panel */}
        {hasSlides && (
          <SlideViewer
            slides={lecture.slides}
            activeSlideNumber={activeSlideNumber}
            onSlideChange={handleSlideChange}
            className="hidden lg:flex lg:w-2/5 border-l"
          />
        )}
      </div>

      {/* Audio player */}
      {hasAudio && (
        <AudioPlayerBar audioUrl={lecture.audio_url!} player={audioPlayer} />
      )}

      {/* Concept side panel */}
      <ConceptPanel
        concept={selectedConcept}
        open={conceptPanelOpen}
        onOpenChange={setConceptPanelOpen}
      />

      {/* Q&A chat stub */}
      <QAChatButton />
    </div>
  );
}
