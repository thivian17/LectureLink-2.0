"use client";

import { useState, useEffect, useCallback, useRef } from "react";
import { toast } from "sonner";
import {
  Upload,
  Check,
  X,
  ChevronDown,
  Pencil,
  Plus,
  Save,
} from "lucide-react";

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
  addLectureChecklistItem,
  getLectureChecklist,
  getSemesterProgress,
  matchFilesToLectures,
  updateLectureChecklistItem,
  uploadLecture,
} from "@/lib/api";
import type { LectureChecklistItem } from "@/types/database";
import { cn } from "@/lib/utils";

interface LectureCatchUpStepProps {
  courseId: string;
  onContinue: () => void;
}

type ChecklistRow = LectureChecklistItem & {
  rowId: string;
  localStatus: "pending" | "uploading" | "uploaded" | "skipped";
  fileName?: string;
};

function makeRowId(item: LectureChecklistItem): string {
  return item.is_user_added
    ? `user-${item.lecture_number}`
    : `auto-${item.lecture_number}`;
}

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

  // Editing state
  const [editingRowId, setEditingRowId] = useState<string | null>(null);
  const [editingLectureNumber, setEditingLectureNumber] = useState<number | null>(null);
  const [editTitle, setEditTitle] = useState("");
  const [editDate, setEditDate] = useState("");
  const [editDescription, setEditDescription] = useState("");
  const [editSaving, setEditSaving] = useState(false);

  // Add lecture state
  const [addOpen, setAddOpen] = useState(false);
  const [addTitle, setAddTitle] = useState("");
  const [addDate, setAddDate] = useState("");
  const [addDescription, setAddDescription] = useState("");
  const [addSaving, setAddSaving] = useState(false);

  useEffect(() => {
    async function load() {
      try {
        const checklist = await getLectureChecklist(courseId);
        setRows(
          checklist.map((item) => ({
            ...item,
            rowId: makeRowId(item),
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
    async (row: ChecklistRow, file: File) => {
      const id = row.rowId;
      setRows((prev) =>
        prev.map((r) =>
          r.rowId === id
            ? { ...r, localStatus: "uploading", fileName: file.name }
            : r,
        ),
      );

      try {
        const formData = new FormData();
        formData.append("files", file);
        formData.append("lecture_number", String(row.lecture_number));

        await uploadLecture(courseId, formData);

        setRows((prev) =>
          prev.map((r) =>
            r.rowId === id
              ? { ...r, localStatus: "uploaded" }
              : r,
          ),
        );
        toast.success(`Lecture ${row.lecture_number} uploaded`);
      } catch {
        setRows((prev) =>
          prev.map((r) =>
            r.rowId === id
              ? { ...r, localStatus: "pending", fileName: undefined }
              : r,
          ),
        );
        toast.error(`Failed to upload lecture ${row.lecture_number}`);
      }
    },
    [courseId],
  );

  const handleSkip = useCallback((rowId: string) => {
    setRows((prev) =>
      prev.map((r) =>
        r.rowId === rowId
          ? { ...r, localStatus: "skipped" }
          : r,
      ),
    );
  }, []);

  const startEditing = useCallback((row: ChecklistRow) => {
    setEditingRowId(row.rowId);
    setEditingLectureNumber(row.lecture_number);
    setEditTitle(row.topic_hint ?? "");
    setEditDate(row.expected_date);
    setEditDescription("");
  }, []);

  const cancelEditing = useCallback(() => {
    setEditingRowId(null);
    setEditingLectureNumber(null);
    setEditTitle("");
    setEditDate("");
    setEditDescription("");
  }, []);

  const saveEdit = useCallback(async () => {
    if (editingRowId === null || editingLectureNumber === null) return;

    setEditSaving(true);
    try {
      const updated = await updateLectureChecklistItem(
        courseId,
        editingLectureNumber,
        {
          title: editTitle || undefined,
          date: editDate || undefined,
          description: editDescription || undefined,
        },
      );

      setRows((prev) =>
        prev.map((r) =>
          r.rowId === editingRowId
            ? {
                ...r,
                expected_date: updated.expected_date,
                topic_hint: updated.topic_hint,
              }
            : r,
        ),
      );
      toast.success(`Lecture ${editingLectureNumber} updated`);
      cancelEditing();
    } catch {
      toast.error("Failed to save changes");
    } finally {
      setEditSaving(false);
    }
  }, [courseId, editingRowId, editingLectureNumber, editTitle, editDate, editDescription, cancelEditing]);

  const handleAddLecture = useCallback(async () => {
    setAddSaving(true);
    try {
      const added = await addLectureChecklistItem(courseId, {
        title: addTitle || undefined,
        date: addDate || undefined,
        description: addDescription || undefined,
      });

      setRows((prev) => [
        ...prev,
        {
          ...added,
          rowId: makeRowId(added),
          localStatus: "pending" as const,
        },
      ]);
      toast.success(`Lecture ${added.lecture_number} added`);
      setAddOpen(false);
      setAddTitle("");
      setAddDate("");
      setAddDescription("");
    } catch {
      toast.error("Failed to add lecture");
    } finally {
      setAddSaving(false);
    }
  }, [courseId, addTitle, addDate, addDescription]);

  const addBulkFiles = useCallback(
    async (files: File[]) => {
      // Immediate: use local regex heuristic so files appear instantly
      const newEntries = files.map((file) => {
        const suggested = suggestLectureNumber(file.name);
        return { file, assignedLecture: suggested };
      });
      setBulkFiles((prev) => [...prev, ...newEntries]);

      // Background: call LLM matcher for smarter assignments
      try {
        const { matches } = await matchFilesToLectures(
          courseId,
          files.map((f) => f.name),
        );
        setBulkFiles((prev) =>
          prev.map((entry) => {
            const match = matches.find(
              (m) => m.filename === entry.file.name,
            );
            if (
              match &&
              match.lecture_number != null &&
              match.confidence >= 0.7
            ) {
              // Only override if user hasn't manually changed it
              const originalSuggestion = suggestLectureNumber(
                entry.file.name,
              );
              if (entry.assignedLecture === originalSuggestion) {
                return { ...entry, assignedLecture: match.lecture_number };
              }
            }
            return entry;
          }),
        );
      } catch {
        // Silently fail — heuristic assignments remain
      }
    },
    [courseId],
  );

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
    let successCount = 0;
    let failCount = 0;

    // Upload sequentially — concurrent uploads saturate bandwidth and
    // cause timeouts, especially for large audio files.
    for (const bf of toUpload) {
      try {
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
        successCount++;
      } catch {
        failCount++;
      }
    }

    setBulkUploading(false);
    setBulkFiles([]);

    if (failCount === 0) {
      toast.success(`${successCount} lectures uploaded successfully`);
    } else if (successCount > 0) {
      toast.warning(
        `${successCount} uploaded, ${failCount} failed. You can retry the failed ones individually.`,
      );
    } else {
      toast.error("All uploads failed. Please try again.");
    }
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
          {uploadedCount} of {rows.length} lectures uploaded. Edit any lecture
          details or add missing ones.
        </p>
      </div>

      {/* Checklist */}
      <div className="space-y-2">
        {rows.map((row) => (
          <div key={row.rowId}>
            <div
              className={cn(
                "flex items-center gap-3 rounded-lg border p-3 transition-colors",
                row.localStatus === "skipped" && "opacity-50",
                row.localStatus === "uploaded" &&
                  "bg-green-50/50 border-green-200",
                row.is_user_added && "border-dashed border-blue-300",
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
                    {row.week_number > 0
                      ? `Week ${row.week_number} (${row.expected_date})`
                      : row.expected_date}
                  </span>
                  {row.is_user_added && (
                    <Badge variant="outline" className="text-xs py-0">
                      Added
                    </Badge>
                  )}
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
                    variant="ghost"
                    size="sm"
                    onClick={() => startEditing(row)}
                    title="Edit lecture details"
                  >
                    <Pencil className="h-3 w-3" />
                  </Button>
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
                    onClick={() => handleSkip(row.rowId)}
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
                      if (file) handleFileUpload(row, file);
                    }}
                  />
                </div>
              )}

              {row.localStatus === "uploading" && (
                <Badge variant="secondary">Uploading...</Badge>
              )}

              {row.localStatus === "uploaded" && (
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => startEditing(row)}
                  title="Edit lecture details"
                >
                  <Pencil className="h-3 w-3" />
                </Button>
              )}
            </div>

            {/* Inline edit form */}
            {editingRowId === row.rowId && (
              <div className="ml-7 mt-2 mb-1 space-y-2 rounded-lg border bg-muted/30 p-3">
                <div className="grid grid-cols-2 gap-2">
                  <div>
                    <label className="text-xs font-medium text-muted-foreground">
                      Title
                    </label>
                    <Input
                      value={editTitle}
                      onChange={(e) => setEditTitle(e.target.value)}
                      placeholder={`Lecture ${row.lecture_number}`}
                      className="h-8 text-sm"
                    />
                  </div>
                  <div>
                    <label className="text-xs font-medium text-muted-foreground">
                      Date
                    </label>
                    <Input
                      type="date"
                      value={editDate}
                      onChange={(e) => setEditDate(e.target.value)}
                      className="h-8 text-sm"
                    />
                  </div>
                </div>
                <div>
                  <label className="text-xs font-medium text-muted-foreground">
                    Description / Topic
                  </label>
                  <Input
                    value={editDescription}
                    onChange={(e) => setEditDescription(e.target.value)}
                    placeholder="e.g. Introduction to thermodynamics"
                    className="h-8 text-sm"
                  />
                </div>
                <div className="flex justify-end gap-2">
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={cancelEditing}
                    disabled={editSaving}
                  >
                    Cancel
                  </Button>
                  <Button
                    size="sm"
                    onClick={saveEdit}
                    disabled={editSaving}
                  >
                    <Save className="h-3 w-3 mr-1" />
                    {editSaving ? "Saving..." : "Save"}
                  </Button>
                </div>
              </div>
            )}
          </div>
        ))}
      </div>

      {/* Add lecture */}
      <Collapsible open={addOpen} onOpenChange={setAddOpen}>
        <CollapsibleTrigger asChild>
          <Button variant="outline" size="sm" className="gap-1">
            <Plus className="h-3 w-3" />
            Add Missing Lecture
          </Button>
        </CollapsibleTrigger>
        <CollapsibleContent className="pt-3 space-y-2">
          <div className="rounded-lg border bg-muted/30 p-3 space-y-2">
            <div className="grid grid-cols-2 gap-2">
              <div>
                <label className="text-xs font-medium text-muted-foreground">
                  Title
                </label>
                <Input
                  value={addTitle}
                  onChange={(e) => setAddTitle(e.target.value)}
                  placeholder="e.g. Guest Lecture: AI Ethics"
                  className="h-8 text-sm"
                />
              </div>
              <div>
                <label className="text-xs font-medium text-muted-foreground">
                  Date
                </label>
                <Input
                  type="date"
                  value={addDate}
                  onChange={(e) => setAddDate(e.target.value)}
                  className="h-8 text-sm"
                />
              </div>
            </div>
            <div>
              <label className="text-xs font-medium text-muted-foreground">
                Description / Topic
              </label>
              <Input
                value={addDescription}
                onChange={(e) => setAddDescription(e.target.value)}
                placeholder="Brief description of the lecture"
                className="h-8 text-sm"
              />
            </div>
            <div className="flex justify-end gap-2">
              <Button
                variant="ghost"
                size="sm"
                onClick={() => {
                  setAddOpen(false);
                  setAddTitle("");
                  setAddDate("");
                  setAddDescription("");
                }}
                disabled={addSaving}
              >
                Cancel
              </Button>
              <Button
                size="sm"
                onClick={handleAddLecture}
                disabled={addSaving}
              >
                <Plus className="h-3 w-3 mr-1" />
                {addSaving ? "Adding..." : "Add Lecture"}
              </Button>
            </div>
          </div>
        </CollapsibleContent>
      </Collapsible>

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
                if (bulkFileInputRef.current)
                  bulkFileInputRef.current.value = "";
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
