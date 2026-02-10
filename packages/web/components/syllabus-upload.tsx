"use client";

import { useState, useRef, useCallback, useEffect } from "react";
import { toast } from "sonner";
import { Upload, FileText, X } from "lucide-react";

import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  ProcessingStatus,
  type ProcessingStep,
} from "@/components/processing-status";
import { uploadSyllabus, getSyllabusStatus, getSyllabus } from "@/lib/api";
import type { Syllabus } from "@/types/database";
import { cn } from "@/lib/utils";

type UploadPhase =
  | "idle"
  | "selected"
  | "uploading"
  | "processing"
  | "complete"
  | "error";

interface SyllabusUploadProps {
  courseId: string;
  existingSyllabus?: Syllabus | null;
  onUploadComplete?: (syllabus: Syllabus) => void;
  compact?: boolean;
}

const ACCEPTED_TYPES = [
  "application/pdf",
  "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
];
const ACCEPTED_EXTENSIONS = [".pdf", ".docx"];
const MAX_SIZE_BYTES = 10 * 1024 * 1024;

function validateFile(f: File): string | null {
  const hasValidType = ACCEPTED_TYPES.includes(f.type);
  const hasValidExt = ACCEPTED_EXTENSIONS.some((ext) =>
    f.name.toLowerCase().endsWith(ext),
  );
  if (!hasValidType && !hasValidExt) {
    return "Only PDF and DOCX files are accepted.";
  }
  if (f.size > MAX_SIZE_BYTES) {
    return `File size must be under 10 MB. This file is ${(f.size / (1024 * 1024)).toFixed(1)} MB.`;
  }
  return null;
}

function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export function SyllabusUpload({
  courseId,
  existingSyllabus,
  onUploadComplete,
  compact,
}: SyllabusUploadProps) {
  const [phase, setPhase] = useState<UploadPhase>(
    existingSyllabus ? "complete" : "idle",
  );
  const [file, setFile] = useState<File | null>(null);
  const [dragOver, setDragOver] = useState(false);
  const [processingStep, setProcessingStep] =
    useState<ProcessingStep>("upload");
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const pollingRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const pollCountRef = useRef(0);
  const completedRef = useRef(false);

  // Cleanup polling on unmount
  useEffect(() => {
    return () => {
      if (pollingRef.current) clearInterval(pollingRef.current);
    };
  }, []);

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setDragOver(true);
  }, []);

  const handleDragLeave = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setDragOver(false);
  }, []);

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setDragOver(false);
    const droppedFile = e.dataTransfer.files[0];
    if (!droppedFile) return;
    const err = validateFile(droppedFile);
    if (err) {
      toast.error(err);
      return;
    }
    setFile(droppedFile);
    setPhase("selected");
  }, []);

  const handleFileSelect = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const selectedFile = e.target.files?.[0];
      if (!selectedFile) return;
      const err = validateFile(selectedFile);
      if (err) {
        toast.error(err);
        return;
      }
      setFile(selectedFile);
      setPhase("selected");
    },
    [],
  );

  const handleRemoveFile = useCallback(() => {
    setFile(null);
    setPhase("idle");
    if (fileInputRef.current) fileInputRef.current.value = "";
  }, []);

  const handleUpload = useCallback(async () => {
    if (!file) return;

    setPhase("uploading");
    setProcessingStep("upload");
    setErrorMessage(null);
    pollCountRef.current = 0;
    completedRef.current = false;

    try {
      const result = await uploadSyllabus(courseId, file);
      setPhase("processing");
      setProcessingStep("extract");

      pollingRef.current = setInterval(async () => {
        if (completedRef.current) return;
        try {
          pollCountRef.current += 1;
          const statusResult = await getSyllabusStatus(result.syllabus_id);
          if (completedRef.current) return;

          if (statusResult.status === "processing") {
            if (pollCountRef.current >= 2) {
              setProcessingStep("validate");
            }
          } else if (statusResult.status === "complete") {
            completedRef.current = true;
            if (pollingRef.current) {
              clearInterval(pollingRef.current);
              pollingRef.current = null;
            }
            setProcessingStep("review");
            setPhase("complete");

            const syllabus = await getSyllabus(result.syllabus_id);
            onUploadComplete?.(syllabus);
            toast.success("Syllabus processed successfully!");
          } else if (statusResult.status === "error") {
            completedRef.current = true;
            if (pollingRef.current) {
              clearInterval(pollingRef.current);
              pollingRef.current = null;
            }
            setPhase("error");
            setErrorMessage(
              statusResult.error_message ??
                "Processing failed. Please try again.",
            );
          }
        } catch {
          if (completedRef.current) return;
          completedRef.current = true;
          if (pollingRef.current) {
            clearInterval(pollingRef.current);
            pollingRef.current = null;
          }
          setPhase("error");
          setErrorMessage("Failed to check processing status.");
        }
      }, 2000);
    } catch {
      setPhase("error");
      setProcessingStep("upload");
      setErrorMessage("Failed to upload file. Please try again.");
    }
  }, [file, courseId, onUploadComplete]);

  const handleRetry = useCallback(() => {
    setPhase(file ? "selected" : "idle");
    setErrorMessage(null);
    pollCountRef.current = 0;
  }, [file]);

  // Phase: idle — drag-and-drop zone
  if (phase === "idle") {
    return (
      <Card className="border-dashed">
        <div
          onDragOver={handleDragOver}
          onDragLeave={handleDragLeave}
          onDrop={handleDrop}
          onClick={() => fileInputRef.current?.click()}
          className={cn(
            "flex cursor-pointer flex-col items-center justify-center gap-3 rounded-lg transition-colors",
            compact ? "p-6" : "p-8",
            dragOver && "bg-accent/50",
          )}
        >
          <Upload className="h-8 w-8 text-muted-foreground" />
          <div className="text-center">
            <p className="text-sm font-medium">
              Drag and drop your syllabus here
            </p>
            <p className="mt-1 text-xs text-muted-foreground">
              PDF or DOCX, up to 10 MB
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
            accept=".pdf,.docx"
            className="hidden"
            onChange={handleFileSelect}
          />
        </div>
      </Card>
    );
  }

  // Phase: selected — file chosen, ready to upload
  if (phase === "selected") {
    return (
      <Card>
        <CardContent className="pt-6">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <FileText className="h-8 w-8 text-muted-foreground" />
              <div>
                <p className="text-sm font-medium">{file!.name}</p>
                <p className="text-xs text-muted-foreground">
                  {formatFileSize(file!.size)}
                </p>
              </div>
            </div>
            <Button variant="ghost" size="icon" onClick={handleRemoveFile}>
              <X className="h-4 w-4" />
            </Button>
          </div>
          <div className="mt-4 flex justify-end">
            <Button onClick={handleUpload}>
              <Upload className="mr-2 h-4 w-4" />
              Upload and Process
            </Button>
          </div>
        </CardContent>
      </Card>
    );
  }

  // Phase: complete
  if (phase === "complete") {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Syllabus Processed</CardTitle>
          <CardDescription>
            Your syllabus has been processed successfully.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <ProcessingStatus currentStep="review" />
        </CardContent>
      </Card>
    );
  }

  // Phases: uploading, processing, error — show progress
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Processing Syllabus</CardTitle>
        <CardDescription>
          {phase === "uploading"
            ? "Uploading your file..."
            : phase === "processing"
              ? "Extracting content with AI..."
              : "An error occurred during processing."}
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <ProcessingStatus
          currentStep={processingStep}
          error={phase === "error" ? errorMessage : null}
          onRetry={handleRetry}
        />
        {file && (
          <div className="flex items-center gap-2 text-xs text-muted-foreground">
            <FileText className="h-4 w-4" />
            <span>{file.name}</span>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
