"use client";

import { useState, useEffect } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { SyllabusReviewClient } from "@/components/syllabus-review/syllabus-review-client";
import { getSyllabus, getAssessments } from "@/lib/api";
import { createClient } from "@/lib/supabase/client";
import type { Syllabus, Assessment } from "@/types/database";
import type { SyllabusExtraction } from "@/types/extraction";

interface ExtractionReviewStepProps {
  courseId: string;
  syllabusId: string;
  onComplete: () => void;
}

export function ExtractionReviewStep({
  courseId,
  syllabusId,
  onComplete,
}: ExtractionReviewStepProps) {
  const [syllabus, setSyllabus] = useState<Syllabus | null>(null);
  const [assessments, setAssessments] = useState<Assessment[]>([]);
  const [pdfUrl, setPdfUrl] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function load() {
      try {
        const [syl, assess] = await Promise.all([
          getSyllabus(syllabusId),
          getAssessments(courseId),
        ]);
        setSyllabus(syl);
        setAssessments(assess);

        // Get signed URL for PDF preview
        if (syl.file_url) {
          const supabase = createClient();
          const { data } = await supabase.storage
            .from("syllabi")
            .createSignedUrl(syl.file_url, 3600);
          if (data?.signedUrl) setPdfUrl(data.signedUrl);
        }
      } catch {
        toast.error("Failed to load syllabus data");
      } finally {
        setLoading(false);
      }
    }
    load();
  }, [syllabusId, courseId]);

  if (loading || !syllabus) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-8 w-64" />
        <Skeleton className="h-4 w-96" />
        <Skeleton className="h-64 w-full" />
      </div>
    );
  }

  const extraction = syllabus.raw_extraction as unknown as SyllabusExtraction | null;

  if (!extraction) {
    return (
      <div className="space-y-4">
        <p className="text-muted-foreground">
          No extraction data available. Continuing...
        </p>
        <Button onClick={onComplete}>Continue &rarr;</Button>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="space-y-2">
        <h2 className="text-xl font-semibold tracking-tight">
          Here&apos;s what I found in your syllabus
        </h2>
        <p className="text-sm text-muted-foreground">
          Review the extracted information and make any corrections.
        </p>
      </div>

      <SyllabusReviewClient
        courseId={courseId}
        syllabus={syllabus}
        extraction={extraction}
        assessments={assessments}
        pdfUrl={pdfUrl}
        hideConfidence
        onSaveComplete={onComplete}
      />
    </div>
  );
}
