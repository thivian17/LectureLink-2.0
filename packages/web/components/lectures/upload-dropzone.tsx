"use client";

import { useState, useRef, useCallback } from "react";
import { Upload, FileText, X, FileAudio, Presentation } from "lucide-react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";

const ACCEPTED_AUDIO_TYPES = [
  "audio/mpeg",
  "audio/wav",
  "audio/x-wav",
  "audio/mp4",
  "audio/x-m4a",
  "audio/ogg",
];
const ACCEPTED_SLIDE_TYPES = [
  "application/pdf",
  "application/vnd.openxmlformats-officedocument.presentationml.presentation",
];
const ACCEPTED_AUDIO_EXTENSIONS = [".mp3", ".wav", ".m4a", ".ogg"];
const ACCEPTED_SLIDE_EXTENSIONS = [".pdf", ".pptx"];
const ALL_ACCEPTED_EXTENSIONS = [
  ...ACCEPTED_AUDIO_EXTENSIONS,
  ...ACCEPTED_SLIDE_EXTENSIONS,
];
const MAX_SIZE_BYTES = 200 * 1024 * 1024; // 200MB

function validateFile(f: File): string | null {
  const ext = "." + f.name.split(".").pop()?.toLowerCase();
  const hasValidType = [...ACCEPTED_AUDIO_TYPES, ...ACCEPTED_SLIDE_TYPES].includes(f.type);
  const hasValidExt = ALL_ACCEPTED_EXTENSIONS.includes(ext);
  if (!hasValidType && !hasValidExt) {
    return `Unsupported file type. Accepted: ${ALL_ACCEPTED_EXTENSIONS.join(", ")}`;
  }
  if (f.size > MAX_SIZE_BYTES) {
    return `File too large. Maximum size is 200MB. This file is ${(f.size / (1024 * 1024)).toFixed(1)}MB.`;
  }
  return null;
}

function isAudioFile(f: File): boolean {
  const ext = "." + f.name.split(".").pop()?.toLowerCase();
  return (
    ACCEPTED_AUDIO_TYPES.includes(f.type) ||
    ACCEPTED_AUDIO_EXTENSIONS.includes(ext)
  );
}

function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

interface UploadDropzoneProps {
  files: File[];
  onFilesChange: (files: File[]) => void;
}

export function UploadDropzone({ files, onFilesChange }: UploadDropzoneProps) {
  const [dragOver, setDragOver] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const addFiles = useCallback(
    (newFiles: FileList | File[]) => {
      const toAdd: File[] = [];
      for (const f of Array.from(newFiles)) {
        const err = validateFile(f);
        if (err) {
          toast.error(err);
          continue;
        }
        // Avoid duplicates by name
        if (files.some((existing) => existing.name === f.name)) {
          toast.error(`"${f.name}" is already added.`);
          continue;
        }
        toAdd.push(f);
      }
      if (toAdd.length > 0) {
        onFilesChange([...files, ...toAdd]);
      }
    },
    [files, onFilesChange],
  );

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

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      e.stopPropagation();
      setDragOver(false);
      if (e.dataTransfer.files.length > 0) {
        addFiles(e.dataTransfer.files);
      }
    },
    [addFiles],
  );

  const handleFileSelect = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      if (e.target.files && e.target.files.length > 0) {
        addFiles(e.target.files);
      }
      // Reset input so re-selecting same file triggers change
      if (fileInputRef.current) fileInputRef.current.value = "";
    },
    [addFiles],
  );

  const removeFile = useCallback(
    (index: number) => {
      onFilesChange(files.filter((_, i) => i !== index));
    },
    [files, onFilesChange],
  );

  return (
    <div className="space-y-3">
      <div
        role="button"
        tabIndex={0}
        aria-label="Upload files. Drag and drop or click to browse."
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
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
        <Upload className="h-8 w-8 text-muted-foreground" />
        <div className="text-center">
          <p className="text-sm font-medium">
            Drag & drop files here or click to browse
          </p>
          <p className="mt-1 text-xs text-muted-foreground">
            Audio: .mp3, .wav, .m4a, .ogg
          </p>
          <p className="text-xs text-muted-foreground">
            Slides: .pdf, .pptx
          </p>
          <p className="mt-1 text-xs text-muted-foreground">
            Max file size: 200MB
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
          multiple
          accept={ALL_ACCEPTED_EXTENSIONS.join(",")}
          className="hidden"
          onChange={handleFileSelect}
        />
      </div>

      {/* Selected files */}
      {files.length > 0 && (
        <div className="flex flex-wrap gap-2">
          {files.map((f, i) => (
            <Badge
              key={f.name}
              variant="secondary"
              className="gap-2 py-1.5 pl-2 pr-1"
            >
              {isAudioFile(f) ? (
                <FileAudio className="h-3.5 w-3.5" />
              ) : (
                <Presentation className="h-3.5 w-3.5" />
              )}
              <span className="max-w-[180px] truncate text-xs">{f.name}</span>
              <span className="text-xs text-muted-foreground">
                {formatFileSize(f.size)}
              </span>
              <button
                type="button"
                aria-label={`Remove ${f.name}`}
                onClick={(e) => {
                  e.stopPropagation();
                  removeFile(i);
                }}
                className="ml-1 rounded-full p-0.5 hover:bg-muted"
              >
                <X className="h-3 w-3" />
              </button>
            </Badge>
          ))}
        </div>
      )}
    </div>
  );
}
