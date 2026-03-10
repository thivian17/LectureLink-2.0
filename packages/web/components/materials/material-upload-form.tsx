"use client";

import { useState, useCallback, useRef, useEffect } from "react";
import { useRouter } from "next/navigation";
import { format } from "date-fns";
import { toast } from "sonner";
import { ArrowLeft, Upload, CalendarIcon, X, FileText } from "lucide-react";
import Link from "next/link";

import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { Calendar } from "@/components/ui/calendar";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { MaterialProcessingStatus } from "@/components/materials/material-processing-status";
import {
  uploadMaterial,
  getAssessments,
  AuthError,
  RateLimitError,
} from "@/lib/api";
import { cn } from "@/lib/utils";
import {
  MATERIAL_TYPE_LABELS,
  type MaterialType,
  type Assessment,
} from "@/types/database";

const ACCEPTED_EXTENSIONS = [".pdf", ".docx", ".pptx", ".txt", ".md"];
const ACCEPTED_MIME_TYPES = [
  "application/pdf",
  "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
  "application/vnd.openxmlformats-officedocument.presentationml.presentation",
  "text/plain",
  "text/markdown",
];
const MAX_SIZE_BYTES = 50 * 1024 * 1024; // 50 MB

interface MaterialUploadFormProps {
  courseId: string;
  courseName: string;
}

type Phase = "form" | "uploading" | "processing";

function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export function MaterialUploadForm({
  courseId,
  courseName,
}: MaterialUploadFormProps) {
  const router = useRouter();
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [phase, setPhase] = useState<Phase>("form");
  const [file, setFile] = useState<File | null>(null);
  const [materialType, setMaterialType] = useState<MaterialType | "">("");
  const [title, setTitle] = useState("");
  const [linkedAssessmentId, setLinkedAssessmentId] = useState("");
  const [weekNumber, setWeekNumber] = useState("");
  const [relevantDate, setRelevantDate] = useState<Date | undefined>();
  const [uploading, setUploading] = useState(false);
  const [materialId, setMaterialId] = useState<string | null>(null);
  const [assessments, setAssessments] = useState<Assessment[]>([]);
  const [dragOver, setDragOver] = useState(false);

  // Load assessments on mount
  useEffect(() => {
    let cancelled = false;
    getAssessments(courseId)
      .then((data) => {
        if (!cancelled) setAssessments(data);
      })
      .catch(() => {
        // Non-critical, ignore
      });
    return () => {
      cancelled = true;
    };
  }, [courseId]);

  const validateFile = useCallback((f: File): string | null => {
    const ext = "." + f.name.split(".").pop()?.toLowerCase();
    const hasValidType = ACCEPTED_MIME_TYPES.includes(f.type);
    const hasValidExt = ACCEPTED_EXTENSIONS.includes(ext);
    if (!hasValidType && !hasValidExt) {
      return `Unsupported file type. Accepted: ${ACCEPTED_EXTENSIONS.join(", ")}`;
    }
    if (f.size > MAX_SIZE_BYTES) {
      return `File too large. Maximum size is 50MB. This file is ${(f.size / (1024 * 1024)).toFixed(1)}MB.`;
    }
    return null;
  }, []);

  const handleFileSelect = useCallback(
    (files: FileList | null) => {
      if (!files || files.length === 0) return;
      const f = files[0];
      const err = validateFile(f);
      if (err) {
        toast.error(err);
        return;
      }
      setFile(f);
    },
    [validateFile],
  );

  const canSubmit = file !== null && materialType !== "" && !uploading;

  const handleSubmit = useCallback(
    async (e: React.FormEvent) => {
      e.preventDefault();
      if (!canSubmit || !file || !materialType) return;

      setUploading(true);
      setPhase("uploading");

      try {
        const result = await uploadMaterial(
          courseId,
          file,
          materialType as MaterialType,
          {
            title: title || undefined,
            linkedAssessmentId:
              linkedAssessmentId && linkedAssessmentId !== "none"
                ? linkedAssessmentId
                : undefined,
            weekNumber: weekNumber ? Number(weekNumber) : undefined,
            relevantDate: relevantDate
              ? format(relevantDate, "yyyy-MM-dd")
              : undefined,
          },
        );
        setMaterialId(result.id);
        setPhase("processing");
        toast.success("Upload complete! Processing started.");
      } catch (err) {
        setPhase("form");
        if (err instanceof AuthError) {
          toast.error("Session expired. Please log in again.");
          router.push("/login");
          return;
        }
        if (err instanceof RateLimitError) {
          toast.error(
            `Rate limit reached. Try again in ${Math.ceil(err.retryAfterSeconds / 60)} min.`,
          );
          return;
        }
        toast.error(
          err instanceof Error ? err.message : "Failed to upload material",
        );
      } finally {
        setUploading(false);
      }
    },
    [
      canSubmit,
      file,
      materialType,
      courseId,
      title,
      linkedAssessmentId,
      weekNumber,
      relevantDate,
      router,
    ],
  );

  // Show processing status after upload
  if (phase === "processing" && materialId) {
    return (
      <div className="space-y-6">
        <div>
          <h2 className="text-lg font-semibold">Processing Material</h2>
          <p className="text-sm text-muted-foreground">
            {title || file?.name}
          </p>
        </div>
        <MaterialProcessingStatus
          materialId={materialId}
          courseId={courseId}
        />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center gap-4">
        <Button variant="ghost" size="icon" asChild>
          <Link href={`/dashboard/courses/${courseId}/materials`}>
            <ArrowLeft className="h-4 w-4" />
          </Link>
        </Button>
        <div>
          <h2 className="text-lg font-semibold">Upload Material</h2>
          <p className="text-sm text-muted-foreground">{courseName}</p>
        </div>
      </div>

      <form onSubmit={handleSubmit} className="space-y-6">
        {/* File dropzone */}
        <Card>
          <CardHeader>
            <CardTitle className="text-base">File *</CardTitle>
            <CardDescription>
              Upload a document file (PDF, DOCX, PPTX, TXT, or Markdown).
            </CardDescription>
          </CardHeader>
          <CardContent>
            {!file ? (
              <div
                role="button"
                tabIndex={0}
                aria-label="Drag & drop a file here or click to browse"
                onDragOver={(e) => {
                  e.preventDefault();
                  e.stopPropagation();
                  setDragOver(true);
                }}
                onDragLeave={(e) => {
                  e.preventDefault();
                  e.stopPropagation();
                  setDragOver(false);
                }}
                onDrop={(e) => {
                  e.preventDefault();
                  e.stopPropagation();
                  setDragOver(false);
                  handleFileSelect(e.dataTransfer.files);
                }}
                onClick={() => fileInputRef.current?.click()}
                onKeyDown={(e) => {
                  if (e.key === "Enter" || e.key === " ") {
                    e.preventDefault();
                    fileInputRef.current?.click();
                  }
                }}
                className={cn(
                  "flex cursor-pointer flex-col items-center justify-center gap-3 rounded-lg border-2 border-dashed p-8 transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2",
                  dragOver
                    ? "border-primary bg-primary/5"
                    : "border-muted-foreground/25 hover:border-muted-foreground/50",
                )}
              >
                <FileText className="h-8 w-8 text-muted-foreground" />
                <div className="text-center">
                  <p className="text-sm font-medium">
                    Drag & drop a file here or click to browse
                  </p>
                  <p className="mt-1 text-xs text-muted-foreground">
                    {ACCEPTED_EXTENSIONS.join(", ")}
                  </p>
                  <p className="mt-1 text-xs text-muted-foreground">
                    Max file size: 50MB
                  </p>
                </div>
                <Button
                  variant="outline"
                  size="sm"
                  type="button"
                  onClick={(e) => {
                    e.stopPropagation();
                    fileInputRef.current?.click();
                  }}
                >
                  Browse Files
                </Button>
                <input
                  ref={fileInputRef}
                  type="file"
                  accept={ACCEPTED_EXTENSIONS.join(",")}
                  className="hidden"
                  onChange={(e) => {
                    handleFileSelect(e.target.files);
                    if (fileInputRef.current) fileInputRef.current.value = "";
                  }}
                />
              </div>
            ) : (
              <div className="flex items-center gap-2">
                <Badge
                  variant="secondary"
                  className="gap-2 py-1.5 pl-2 pr-1"
                >
                  <FileText className="h-3.5 w-3.5" />
                  <span className="max-w-[240px] truncate text-xs">
                    {file.name}
                  </span>
                  <span className="text-xs text-muted-foreground">
                    {formatFileSize(file.size)}
                  </span>
                  <button
                    type="button"
                    aria-label={`Remove ${file.name}`}
                    onClick={() => setFile(null)}
                    className="ml-1 rounded-full p-0.5 hover:bg-muted"
                  >
                    <X className="h-3 w-3" />
                  </button>
                </Badge>
              </div>
            )}
          </CardContent>
        </Card>

        {/* Material details */}
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Material Details</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid gap-4 sm:grid-cols-2">
              {/* Material type */}
              <div className="space-y-2">
                <Label>Material Type *</Label>
                <Select
                  value={materialType}
                  onValueChange={(v) => setMaterialType(v as MaterialType)}
                >
                  <SelectTrigger>
                    <SelectValue placeholder="Select type..." />
                  </SelectTrigger>
                  <SelectContent>
                    {(
                      Object.entries(MATERIAL_TYPE_LABELS) as [
                        MaterialType,
                        string,
                      ][]
                    ).map(([value, label]) => (
                      <SelectItem key={value} value={value}>
                        {label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>

              {/* Title */}
              <div className="space-y-2">
                <Label htmlFor="materialTitle">Title</Label>
                <Input
                  id="materialTitle"
                  placeholder="Auto-detected from content"
                  value={title}
                  onChange={(e) => setTitle(e.target.value)}
                />
              </div>

              {/* Assessment link */}
              <div className="space-y-2">
                <Label>Linked Assessment</Label>
                <Select
                  value={linkedAssessmentId}
                  onValueChange={setLinkedAssessmentId}
                >
                  <SelectTrigger>
                    <SelectValue placeholder="None" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="none">None</SelectItem>
                    {assessments.map((a) => (
                      <SelectItem key={a.id} value={a.id}>
                        {a.title}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>

              {/* Week number */}
              <div className="space-y-2">
                <Label htmlFor="weekNumber">Week Number</Label>
                <Input
                  id="weekNumber"
                  type="number"
                  min={1}
                  max={52}
                  placeholder="e.g., 3"
                  value={weekNumber}
                  onChange={(e) => setWeekNumber(e.target.value)}
                />
              </div>

              {/* Relevant date */}
              <div className="space-y-2">
                <Label>Relevant Date</Label>
                <Popover>
                  <PopoverTrigger asChild>
                    <Button
                      variant="outline"
                      className={cn(
                        "w-full justify-start text-left font-normal",
                        !relevantDate && "text-muted-foreground",
                      )}
                    >
                      <CalendarIcon className="mr-2 h-4 w-4" />
                      {relevantDate
                        ? format(relevantDate, "MMM d, yyyy")
                        : "Pick a date"}
                    </Button>
                  </PopoverTrigger>
                  <PopoverContent className="w-auto p-0" align="start">
                    <Calendar
                      mode="single"
                      selected={relevantDate}
                      onSelect={setRelevantDate}
                      initialFocus
                    />
                  </PopoverContent>
                </Popover>
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Submit */}
        <div className="flex justify-end gap-2">
          <Button
            variant="outline"
            type="button"
            onClick={() =>
              router.push(`/dashboard/courses/${courseId}/materials`)
            }
          >
            Cancel
          </Button>
          <Button type="submit" disabled={!canSubmit}>
            {uploading ? (
              <>Uploading...</>
            ) : (
              <>
                <Upload className="mr-2 h-4 w-4" />
                Upload and Process
              </>
            )}
          </Button>
        </div>
      </form>
    </div>
  );
}
