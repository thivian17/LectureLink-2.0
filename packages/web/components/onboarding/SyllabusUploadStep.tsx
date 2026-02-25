"use client";

import { useCallback } from "react";

import { SyllabusUpload } from "@/components/syllabus-upload";
import type { Syllabus } from "@/types/database";

interface SyllabusUploadStepProps {
  courseId: string;
  onComplete: (syllabusId: string) => void;
  onSkip: () => void;
}

export function SyllabusUploadStep({
  courseId,
  onComplete,
  onSkip,
}: SyllabusUploadStepProps) {
  const handleUploadComplete = useCallback(
    (syllabus: Syllabus) => {
      onComplete(syllabus.id);
    },
    [onComplete],
  );

  return (
    <div className="space-y-6">
      {/* Welcome message */}
      <div className="space-y-2">
        <h2 className="text-xl font-semibold tracking-tight">
          Welcome to LectureLink!
        </h2>
        <p className="text-muted-foreground">
          To get started, upload your syllabus so I can map out your course —
          deadlines, assessments, grade weights, and the topics you&apos;ll be
          covering. This takes about 30 seconds.
        </p>
      </div>

      {/* Existing syllabus upload component */}
      <SyllabusUpload
        courseId={courseId}
        onUploadComplete={handleUploadComplete}
      />

      {/* Skip link */}
      <div className="text-center">
        <button
          type="button"
          onClick={onSkip}
          className="text-sm text-muted-foreground hover:text-foreground transition-colors"
        >
          Skip for Now &rarr;
        </button>
      </div>
    </div>
  );
}
