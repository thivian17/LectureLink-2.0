"use client";

import { useState, useEffect, useCallback } from "react";
import { useRouter } from "next/navigation";
import { toast } from "sonner";
import { AlertCircle, AlertTriangle, FileText } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import { CourseInfo } from "./course-info";
import { GradeBreakdown } from "./grade-breakdown";
import { AssessmentTable } from "./assessment-table";
import { ActionBar } from "./action-bar";
import {
  reviewSyllabus,
  bulkUpdateAssessments,
  type UpdateAssessmentInput,
} from "@/lib/api";
import type { Syllabus, Assessment } from "@/types/database";
import {
  CONFIDENCE_HIGH,
  type SyllabusExtraction,
  type ExtractedField,
} from "@/types/extraction";

interface SyllabusReviewClientProps {
  courseId: string;
  syllabus: Syllabus;
  extraction: SyllabusExtraction;
  assessments: Assessment[];
  pdfUrl: string | null;
  hideConfidence?: boolean;
  onSaveComplete?: () => void;
}

export function SyllabusReviewClient({
  courseId,
  syllabus,
  extraction: initialExtraction,
  assessments: initialAssessments,
  pdfUrl,
  hideConfidence,
  onSaveComplete,
}: SyllabusReviewClientProps) {
  const router = useRouter();
  const [extraction, setExtraction] =
    useState<SyllabusExtraction>(initialExtraction);
  const [assessments, setAssessments] =
    useState<Assessment[]>(initialAssessments);
  const [editedIndices, setEditedIndices] = useState<Set<number>>(new Set());
  const [isSaving, setIsSaving] = useState(false);
  const [isDirty, setIsDirty] = useState(false);

  // Warn on navigation with unsaved changes
  useEffect(() => {
    function handleBeforeUnload(e: BeforeUnloadEvent) {
      if (isDirty) {
        e.preventDefault();
      }
    }
    window.addEventListener("beforeunload", handleBeforeUnload);
    return () => window.removeEventListener("beforeunload", handleBeforeUnload);
  }, [isDirty]);

  // --- Course info ---
  const handleCourseInfoChange = useCallback(
    (field: string, value: string) => {
      setExtraction((prev) => {
        const fieldKey = field as keyof SyllabusExtraction;
        const existing = prev[fieldKey] as ExtractedField<string | null> | null;
        if (!existing) return prev;
        return {
          ...prev,
          [field]: { ...existing, value },
        };
      });
      setIsDirty(true);
    },
    [],
  );

  // --- Grade breakdown ---
  const handleGradeChange = useCallback(
    (
      index: number,
      field: "name" | "weight_percent" | "drop_policy",
      value: string | number | null,
    ) => {
      setExtraction((prev) => {
        const updated = [...prev.grade_breakdown];
        const component = { ...updated[index] };

        if (field === "drop_policy") {
          component.drop_policy = component.drop_policy
            ? { ...component.drop_policy, value: value as string | null }
            : { value: value as string | null, confidence: 1.0, source_text: null };
        } else if (field === "name") {
          component.name = { ...component.name, value: value as string };
        } else {
          component.weight_percent = {
            ...component.weight_percent,
            value: value as number | null,
          };
        }

        updated[index] = component;
        return { ...prev, grade_breakdown: updated };
      });
      setIsDirty(true);
    },
    [],
  );

  // --- Assessments ---
  const handleAssessmentUpdate = useCallback(
    (index: number, updates: UpdateAssessmentInput) => {
      // Update the DB-shaped assessments
      setAssessments((prev) => {
        const updated = [...prev];
        updated[index] = { ...updated[index], ...updates };
        return updated;
      });

      // Update the extraction-shaped assessments to keep confidence indicators in sync
      setExtraction((prev) => {
        const updatedAssessments = [...prev.assessments];
        const current = { ...updatedAssessments[index] };

        if (updates.title !== undefined) {
          current.title = { ...current.title, value: updates.title };
        }
        if (updates.type !== undefined) {
          current.type = { ...current.type, value: updates.type };
        }
        if (updates.due_date !== undefined) {
          current.due_date_resolved = {
            ...current.due_date_resolved,
            value: updates.due_date,
          };
        }
        if (updates.weight_percent !== undefined) {
          current.weight_percent = {
            ...current.weight_percent,
            value: updates.weight_percent,
          };
        }
        if (updates.topics !== undefined) {
          current.topics = updates.topics ?? [];
        }

        updatedAssessments[index] = current;
        return { ...prev, assessments: updatedAssessments };
      });

      setEditedIndices((prev) => new Set(prev).add(index));
      setIsDirty(true);
    },
    [],
  );

  const handleAcceptRow = useCallback((index: number) => {
    setEditedIndices((prev) => new Set(prev).add(index));
    toast.success(`Assessment "${assessments[index]?.title}" accepted`);
  }, [assessments]);

  // --- Accept all high confidence ---
  const handleAcceptAllHigh = useCallback(() => {
    const newEdited = new Set(editedIndices);
    let accepted = 0;

    extraction.assessments.forEach((a, i) => {
      const allHigh =
        a.title.confidence >= CONFIDENCE_HIGH &&
        a.type.confidence >= CONFIDENCE_HIGH &&
        a.weight_percent.confidence >= CONFIDENCE_HIGH &&
        (a.due_date_resolved.value === null ||
          a.due_date_resolved.confidence >= CONFIDENCE_HIGH);

      if (allHigh) {
        newEdited.add(i);
        accepted++;
      }
    });

    setEditedIndices(newEdited);
    toast.success(`Accepted ${accepted} high-confidence assessment${accepted !== 1 ? "s" : ""}`);
  }, [extraction.assessments, editedIndices]);

  // --- Save ---
  const handleSave = useCallback(async () => {
    setIsSaving(true);
    try {
      // Bulk update all edited assessments
      const updates = Array.from(editedIndices)
        .filter((i) => assessments[i])
        .map((i) => ({
          id: assessments[i].id,
          data: {
            title: assessments[i].title,
            type: assessments[i].type,
            due_date: assessments[i].due_date,
            due_date_raw: assessments[i].due_date_raw,
            is_date_ambiguous: assessments[i].is_date_ambiguous,
            weight_percent: assessments[i].weight_percent,
            topics: assessments[i].topics,
          } satisfies UpdateAssessmentInput,
        }));

      if (updates.length > 0) {
        await bulkUpdateAssessments(updates);
      }

      // Mark syllabus as reviewed
      await reviewSyllabus(syllabus.id, {
        grade_breakdown: extraction.grade_breakdown.map((c) => ({
          component: String(c.name.value ?? ""),
          weight: Number(c.weight_percent.value ?? 0),
          drop_policy: c.drop_policy?.value ?? null,
        })),
        course_info: {
          instructor_name: extraction.instructor_name?.value ?? null,
          instructor_email: extraction.instructor_email?.value ?? null,
          office_hours: extraction.office_hours?.value ?? null,
        },
      });

      setIsDirty(false);
      toast.success("Syllabus review saved!");
      if (onSaveComplete) {
        onSaveComplete();
      } else {
        router.push(`/dashboard/courses/${courseId}`);
        router.refresh();
      }
    } catch (err) {
      toast.error(
        `Failed to save: ${err instanceof Error ? err.message : "Unknown error"}`,
      );
    } finally {
      setIsSaving(false);
    }
  }, [
    editedIndices,
    assessments,
    syllabus.id,
    extraction,
    courseId,
    router,
  ]);

  // --- Re-extract ---
  const handleReExtract = useCallback(() => {
    router.push(`/dashboard/courses/${courseId}`);
  }, [router, courseId]);

  // --- Computed stats ---
  const highConfidenceCount = extraction.assessments.filter(
    (a) =>
      a.title.confidence >= CONFIDENCE_HIGH &&
      a.type.confidence >= CONFIDENCE_HIGH &&
      a.weight_percent.confidence >= CONFIDENCE_HIGH,
  ).length;

  const ambiguousDateCount = assessments.filter(
    (a) => a.is_date_ambiguous,
  ).length;

  const needsReviewCount =
    extraction.assessments.length - highConfidenceCount;

  const isPdf = syllabus.file_name?.toLowerCase().endsWith(".pdf");

  return (
    <div className="space-y-4">
      {/* Header */}
      <div>
        <h1 className="text-xl font-bold tracking-tight">
          Review Syllabus Extraction
        </h1>
        <p className="text-sm text-muted-foreground">
          {hideConfidence
            ? "Review the extracted data below. Edit anything that looks incorrect."
            : "AI-extracted data is shown below with confidence scores. Review, edit, and accept the results."}
        </p>
      </div>

      {/* Low confidence warning */}
      {!hideConfidence && (syllabus.extraction_confidence !== null && syllabus.extraction_confidence < 0.5) && (
        <div className="rounded-lg border border-red-200 bg-red-50 p-4 flex items-start gap-3">
          <AlertCircle className="h-5 w-5 text-red-600 shrink-0 mt-0.5" />
          <div>
            <p className="text-sm font-medium text-red-800">
              Low extraction confidence — please review carefully
            </p>
            <p className="text-sm text-red-700 mt-1">
              The AI had difficulty reading this syllabus (confidence:{" "}
              {Math.round((syllabus.extraction_confidence || 0) * 100)}%).
              This often happens with scanned PDFs or image-based documents.
              Please verify all dates, weights, and assessment titles before continuing.
            </p>
          </div>
        </div>
      )}

      {/* Overall confidence */}
      {!hideConfidence && (
        <div className="flex items-center gap-3 flex-wrap">
          <Badge variant="outline" className="text-sm">
            Overall confidence:{" "}
            {Math.round(extraction.extraction_confidence * 100)}%
          </Badge>
          {extraction.missing_sections.length > 0 && (
            <Badge
              variant="outline"
              className="text-amber-700 border-amber-300 bg-amber-50"
            >
              <AlertTriangle className="mr-1 h-3 w-3" />
              Missing: {extraction.missing_sections.join(", ")}
            </Badge>
          )}
        </div>
      )}

      {/* Two-column layout: course info + grade breakdown with PDF */}
      <div className="flex flex-col lg:flex-row gap-6 overflow-hidden">
        {/* LEFT: Course info & grade breakdown */}
        <div className="flex-1 space-y-6 min-w-0">
          <CourseInfo
            extraction={extraction}
            onChange={handleCourseInfoChange}
            hideConfidence={hideConfidence}
          />
          <GradeBreakdown
            components={extraction.grade_breakdown}
            onChange={handleGradeChange}
            hideConfidence={hideConfidence}
          />
        </div>

        {/* RIGHT: PDF viewer (desktop only) */}
        <div className="hidden lg:block lg:w-[40%] lg:shrink-0 lg:min-w-0">
          <div className="sticky top-4">
            {pdfUrl && isPdf ? (
              <iframe
                src={pdfUrl}
                className="w-full h-[calc(100vh-8rem)] rounded-lg border"
                title="Syllabus PDF"
              />
            ) : (
              <Card>
                <CardContent className="flex flex-col items-center justify-center py-16 text-center">
                  <FileText className="h-12 w-12 text-muted-foreground mb-3" />
                  <p className="text-sm font-medium">
                    {!pdfUrl
                      ? "No file preview available"
                      : "Preview not available for DOCX files"}
                  </p>
                  <p className="text-xs text-muted-foreground mt-1">
                    {syllabus.file_name ?? "Unknown file"}
                  </p>
                </CardContent>
              </Card>
            )}
          </div>
        </div>
      </div>

      {/* Assessments — full width below the two-column layout */}
      <div className="pb-24">
        <AssessmentTable
          assessments={extraction.assessments}
          dbAssessments={assessments}
          onUpdate={handleAssessmentUpdate}
          onAcceptRow={handleAcceptRow}
          hideConfidence={hideConfidence}
        />
      </div>

      {/* Action bar */}
      <ActionBar
        totalAssessments={assessments.length}
        highConfidenceCount={highConfidenceCount}
        needsReviewCount={needsReviewCount}
        ambiguousDateCount={ambiguousDateCount}
        isSaving={isSaving}
        onAcceptHighConfidence={handleAcceptAllHigh}
        onSave={handleSave}
        onReExtract={handleReExtract}
        hideConfidence={hideConfidence}
      />
    </div>
  );
}
