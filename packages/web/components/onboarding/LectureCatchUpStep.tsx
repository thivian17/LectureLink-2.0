"use client";

import { useState, useEffect, useCallback, useRef } from "react";
import { toast } from "sonner";
import { Upload, Check, X, ChevronDown } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  getLectureChecklist,
  getSemesterProgress,
  uploadLecture,
} from "@/lib/api";
import type { LectureChecklistItem } from "@/types/database";
import { cn } from "@/lib/utils";

interface LectureCatchUpStepProps {
  courseId: string;
  onContinue: () => void;
}

type ChecklistRow = LectureChecklistItem & {
  localStatus: "pending" | "uploading" | "uploaded" | "skipped";
  fileName?: string;
};

// Try to extract lecture number from filename
function suggestLectureNumber(filename: string): number | null {
  const match = filename.match(/lec(?:ture)?[_\s-]?(\d+)/i);
  return match ? parseInt(match[1], 10) : null;
}

export function LectureCatchUpStep({
  courseId,
  onContinue,
}: LectureCatchUpStepProps) {
  const [rows, setRows] = useState<ChecklistRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [bulkOpen, setBulkOpen] = useState(false);
  const [bulkFiles, setBulkFiles] = useState<
    { file: File; assignedLecture: number | null }[]
  >([]);
  const [bulkUploading, setBulkUploading] = useState(false);
  const fileInputRefs = useRef<Record<number, HTMLInputElement | null>>({});
  const bulkFileInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    async function load() {
      try {
        const checklist = await getLectureChecklist(courseId);
        setRows(
          checklist.map((item) => ({
            ...item,
            localStatus: item.status === "uploaded" ? "uploaded" : item.status,
          })),
        );
      } catch {
        toast.error("Failed to load lecture checklist");
      } finally {
        setLoading(false);
      }
    }
    load();
  }, [courseId]);

  const uploadedCount = rows.filter((r) => r.localStatus === "uploaded").length;

  const handleFileUpload = useCallback(
    async (lectureNumber: number, file: File) => {
      setRows((prev) =>
        prev.map((r) =>
          r.lecture_number === lectureNumber
            ? { ...r, localStatus: "uploading", fileName: file.name }
            : r,
        ),
      );

      try {
        const formData = new FormData();
        formData.append("files", file);
        formData.append("lecture_number", String(lectureNumber));

        await uploadLecture(courseId, formData);

        setRows((prev) =>
          prev.map((r) =>
            r.lecture_number === lectureNumber
              ? { ...r, localStatus: "uploaded" }
              : r,
          ),
        );
        toast.success(`Lecture ${lectureNumber} uploaded`);
      } catch {
        setRows((prev) =>
          prev.map((r) =>
            r.lecture_number === lectureNumber
              ? { ...r, localStatus: "pending", fileName: undefined }
              : r,
          ),
        );
        toast.error(`Failed to upload lecture ${lectureNumber}`);
      }
    },
    [courseId],
  );

  const handleSkip = useCallback((lectureNumber: number) => {
    setRows((prev) =>
      prev.map((r) =>
        r.lecture_number === lectureNumber
          ? { ...r, localStatus: "skipped" }
          : r,
      ),
    );
  }, []);

  const addBulkFiles = useCallback((files: File[]) => {
    const newEntries = files.map((file) => {
      const suggested = suggestLectureNumber(file.name);
      return { file, assignedLecture: suggested };
    });
    setBulkFiles((prev) => [...prev, ...newEntries]);
  }, []);

  const handleBulkDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      addBulkFiles(Array.from(e.dataTransfer.files));
    },
    [addBulkFiles],
  );

  const handleBulkUpload = useCallback(async () => {
    const toUpload = bulkFiles.filter((bf) => bf.assignedLecture != null);
    if (toUpload.length === 0) {
      toast.error("Please assign lecture numbers before uploading");
      return;
    }

    setBulkUploading(true);

    // Upload with concurrency limit of 3
    const results: Promise<void>[] = [];
    for (let i = 0; i < toUpload.length; i += 3) {
      const batch = toUpload.slice(i, i + 3);
      const batchPromises = batch.map(async (bf) => {
        const formData = new FormData();
        formData.append("files", bf.file);
        formData.append("lecture_number", String(bf.assignedLecture));
        await uploadLecture(courseId, formData);

        setRows((prev) =>
          prev.map((r) =>
            r.lecture_number === bf.assignedLecture
              ? { ...r, localStatus: "uploaded", fileName: bf.file.name }
              : r,
          ),
        );
      });
      results.push(...batchPromises);
      await Promise.allSettled(batchPromises);
    }

    setBulkUploading(false);
    setBulkFiles([]);
    toast.success("Bulk upload complete");
  }, [bulkFiles, courseId]);

  if (loading) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-8 w-48" />
        {Array.from({ length: 5 }).map((_, i) => (
          <Skeleton key={i} className="h-12 w-full" />
        ))}
      </div>
    );
  }

  const hasProcessing = rows.some((r) => r.localStatus === "uploading");

  return (
    <div className="space-y-6">
      <div className="space-y-2">
        <h2 className="text-xl font-semibold tracking-tight">
          Catch Up on Lectures
        </h2>
        <p className="text-sm text-muted-foreground">
          {uploadedCount} of {rows.length} lectures uploaded
        </p>
      </div>

      {/* Checklist */}
      <div className="space-y-2">
        {rows.map((row) => (
          <div
            key={row.lecture_number}
            className={cn(
              "flex items-center gap-3 rounded-lg border p-3 transition-colors",
              row.localStatus === "skipped" && "opacity-50",
              row.localStatus === "uploaded" && "bg-green-50/50 border-green-200",
            )}
          >
            {/* Status icon */}
            <div className="shrink-0">
              {row.localStatus === "uploaded" ? (
                <Check className="h-4 w-4 text-green-600" />
              ) : row.localStatus === "skipped" ? (
                <X className="h-4 w-4 text-muted-foreground" />
              ) : (
                <div className="h-4 w-4 rounded border-2 border-muted-foreground/30" />
              )}
            </div>

            {/* Info */}
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2">
                <span className="text-sm font-medium">
                  Lecture {row.lecture_number}
                </span>
                <span className="text-xs text-muted-foreground">
                  Week {row.week_number} ({row.expected_date})
                </span>
              </div>
              {row.topic_hint && (
                <p className="text-xs text-muted-foreground italic truncate">
                  {row.topic_hint}
                </p>
              )}
              {row.fileName && row.localStatus === "uploaded" && (
                <p className="text-xs text-green-600 truncate">
                  {row.fileName}
                </p>
              )}
            </div>

            {/* Actions */}
            {row.localStatus === "pending" && (
              <div className="flex gap-1 shrink-0">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() =>
                    fileInputRefs.current[row.lecture_number]?.click()
                  }
                  disabled={row.localStatus !== "pending"}
                >
                  <Upload className="h-3 w-3 mr-1" />
                  Upload
                </Button>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => handleSkip(row.lecture_number)}
                >
                  Skip
                </Button>
                <input
                  ref={(el) => {
                    fileInputRefs.current[row.lecture_number] = el;
                  }}
                  type="file"
                  className="hidden"
                  accept=".mp3,.wav,.m4a,.pdf,.pptx,.mp4"
                  onChange={(e) => {
                    const file = e.target.files?.[0];
                    if (file) handleFileUpload(row.lecture_number, file);
                  }}
                />
              </div>
            )}

            {row.localStatus === "uploading" && (
              <Badge variant="secondary">Uploading...</Badge>
            )}
          </div>
        ))}
      </div>

      {/* Bulk upload */}
      <Collapsible open={bulkOpen} onOpenChange={setBulkOpen}>
        <CollapsibleTrigger asChild>
          <Button variant="outline" className="w-full justify-between">
            Upload All at Once
            <ChevronDown
              className={cn(
                "h-4 w-4 transition-transform",
                bulkOpen && "rotate-180",
              )}
            />
          </Button>
        </CollapsibleTrigger>
        <CollapsibleContent className="pt-4 space-y-4">
          <div
            role="button"
            tabIndex={0}
            aria-label="Upload files. Drag and drop or click to browse."
            onDragOver={(e) => e.preventDefault()}
            onDrop={handleBulkDrop}
            onClick={() => bulkFileInputRef.current?.click()}
            onKeyDown={(e) => {
              if (e.key === "Enter" || e.key === " ") {
                e.preventDefault();
                bulkFileInputRef.current?.click();
              }
            }}
            className="flex cursor-pointer flex-col items-center justify-center gap-2 rounded-lg border-2 border-dashed p-6 text-center hover:border-muted-foreground/50 transition-colors"
          >
            <Upload className="h-6 w-6 text-muted-foreground" />
            <p className="text-sm text-muted-foreground">
              Drag & drop lecture files here or click to browse
            </p>
            <Button
              variant="outline"
              size="sm"
              type="button"
              onClick={(e) => {
                e.stopPropagation();
                bulkFileInputRef.current?.click();
              }}
            >
              Browse Files
            </Button>
            <input
              ref={bulkFileInputRef}
              type="file"
              multiple
              accept=".mp3,.wav,.m4a,.pdf,.pptx,.mp4"
              className="hidden"
              onChange={(e) => {
                if (e.target.files) addBulkFiles(Array.from(e.target.files));
                if (bulkFileInputRef.current) bulkFileInputRef.current.value = "";
              }}
            />
          </div>

          {bulkFiles.length > 0 && (
            <div className="space-y-2">
              {bulkFiles.map((bf, i) => (
                <div
                  key={bf.file.name}
                  className="flex items-center gap-3 rounded border p-2"
                >
                  <span className="text-sm truncate flex-1">
                    {bf.file.name}
                  </span>
                  <Select
                    value={bf.assignedLecture?.toString() ?? ""}
                    onValueChange={(val) => {
                      setBulkFiles((prev) =>
                        prev.map((item, j) =>
                          j === i
                            ? { ...item, assignedLecture: parseInt(val, 10) }
                            : item,
                        ),
                      );
                    }}
                  >
                    <SelectTrigger className="w-40">
                      <SelectValue placeholder="Assign to..." />
                    </SelectTrigger>
                    <SelectContent position="popper" className="max-h-60">
                      {rows
                        .filter((r) => r.localStatus === "pending")
                        .map((r) => (
                          <SelectItem
                            key={r.lecture_number}
                            value={r.lecture_number.toString()}
                          >
                            Lecture {r.lecture_number}
                          </SelectItem>
                        ))}
                    </SelectContent>
                  </Select>
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() =>
                      setBulkFiles((prev) => prev.filter((_, j) => j !== i))
                    }
                  >
                    <X className="h-3 w-3" />
                  </Button>
                </div>
              ))}
              <Button
                onClick={handleBulkUpload}
                disabled={bulkUploading}
                className="w-full"
              >
                {bulkUploading ? "Uploading..." : "Upload All"}
              </Button>
            </div>
          )}
        </CollapsibleContent>
      </Collapsible>

      {/* Continue */}
      <div className="space-y-2">
        {hasProcessing && (
          <p className="text-xs text-muted-foreground text-center">
            Some lectures are still processing. That&apos;s fine — continue and
            they&apos;ll be ready soon.
          </p>
        )}
        <p className="text-xs text-muted-foreground text-center">
          This is optional — you can always add lectures later from the course
          page.
        </p>
        <div className="flex justify-end">
          <Button onClick={onContinue}>Continue &rarr;</Button>
        </div>
      </div>
    </div>
  );
}
