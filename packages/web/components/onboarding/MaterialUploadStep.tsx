"use client";

import { useState, useCallback, useRef } from "react";
import { toast } from "sonner";
import { Upload, Check, X, FileAudio, Presentation } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import { uploadLecture } from "@/lib/api";

interface MaterialUploadStepProps {
  courseId: string;
  onContinue: () => void;
}

const ACCEPTED_EXTENSIONS = [
  ".mp3",
  ".wav",
  ".m4a",
  ".ogg",
  ".pdf",
  ".pptx",
  ".mp4",
];

type UploadEntry = {
  file: File;
  status: "pending" | "uploading" | "uploaded" | "error";
};

function isAudioFile(f: File): boolean {
  const ext = "." + f.name.split(".").pop()?.toLowerCase();
  return [".mp3", ".wav", ".m4a", ".ogg", ".mp4"].includes(ext);
}

export function MaterialUploadStep({
  courseId,
  onContinue,
}: MaterialUploadStepProps) {
  const [entries, setEntries] = useState<UploadEntry[]>([]);
  const [uploading, setUploading] = useState(false);
  const [dragOver, setDragOver] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const addFiles = useCallback(
    (fileList: FileList | File[]) => {
      const files = Array.from(fileList);
      const newEntries: UploadEntry[] = [];
      for (const file of files) {
        const ext = "." + file.name.split(".").pop()?.toLowerCase();
        if (!ACCEPTED_EXTENSIONS.includes(ext)) {
          toast.error(`Unsupported file type: ${file.name}`);
          continue;
        }
        if (entries.some((e) => e.file.name === file.name)) {
          toast.error(`"${file.name}" is already added.`);
          continue;
        }
        newEntries.push({ file, status: "pending" });
      }
      if (newEntries.length > 0) {
        setEntries((prev) => [...prev, ...newEntries]);
      }
    },
    [entries],
  );

  const removeEntry = useCallback((index: number) => {
    setEntries((prev) => prev.filter((_, i) => i !== index));
  }, []);

  const handleUploadAll = useCallback(async () => {
    const pending = entries.filter((e) => e.status === "pending");
    if (pending.length === 0) {
      toast.error("No files to upload");
      return;
    }

    setUploading(true);

    // Upload with concurrency limit of 3
    // Calculate starting lecture number based on upload order
    const pendingIndices = entries.reduce<number[]>((acc, e, idx) => {
      if (e.status === "pending") acc.push(idx);
      return acc;
    }, []);

    for (let i = 0; i < pending.length; i += 3) {
      const batch = pending.slice(i, i + 3);
      const promises = batch.map(async (entry, batchIdx) => {
        setEntries((prev) =>
          prev.map((e) =>
            e.file.name === entry.file.name
              ? { ...e, status: "uploading" }
              : e,
          ),
        );

        const lectureNumber = i + batchIdx + 1;
        try {
          const formData = new FormData();
          formData.append("files", entry.file);
          formData.append("lecture_number", String(lectureNumber));
          await uploadLecture(courseId, formData);

          setEntries((prev) =>
            prev.map((e) =>
              e.file.name === entry.file.name
                ? { ...e, status: "uploaded" }
                : e,
            ),
          );
        } catch {
          setEntries((prev) =>
            prev.map((e) =>
              e.file.name === entry.file.name ? { ...e, status: "error" } : e,
            ),
          );
          toast.error(`Failed to upload ${entry.file.name}`);
        }
      });
      await Promise.allSettled(promises);
    }

    setUploading(false);
    toast.success("Upload complete");
  }, [entries, courseId]);

  const uploadedCount = entries.filter((e) => e.status === "uploaded").length;
  const pendingCount = entries.filter((e) => e.status === "pending").length;

  return (
    <div className="space-y-6">
      <div className="space-y-2">
        <h2 className="text-xl font-semibold tracking-tight">
          Upload Course Materials
        </h2>
        <p className="text-sm text-muted-foreground">
          Drop all your lecture files here — audio recordings, slides, PDFs.
          We&apos;ll process them and build your study materials.
        </p>
      </div>

      {/* Drop zone */}
      <div
        role="button"
        tabIndex={0}
        aria-label="Upload files. Drag and drop or click to browse."
        onDragOver={(e) => {
          e.preventDefault();
          setDragOver(true);
        }}
        onDragLeave={(e) => {
          e.preventDefault();
          setDragOver(false);
        }}
        onDrop={(e) => {
          e.preventDefault();
          setDragOver(false);
          if (e.dataTransfer.files.length > 0) {
            addFiles(e.dataTransfer.files);
          }
        }}
        onClick={() => fileInputRef.current?.click()}
        onKeyDown={(e) => {
          if (e.key === "Enter" || e.key === " ") {
            e.preventDefault();
            fileInputRef.current?.click();
          }
        }}
        className={cn(
          "flex cursor-pointer flex-col items-center justify-center gap-3 rounded-lg border-2 border-dashed p-8 transition-colors",
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
            Audio: .mp3, .wav, .m4a, .ogg, .mp4
          </p>
          <p className="text-xs text-muted-foreground">Slides: .pdf, .pptx</p>
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
          accept={ACCEPTED_EXTENSIONS.join(",")}
          className="hidden"
          onChange={(e) => {
            if (e.target.files) addFiles(e.target.files);
            if (fileInputRef.current) fileInputRef.current.value = "";
          }}
        />
      </div>

      {/* File list */}
      {entries.length > 0 && (
        <div className="space-y-2">
          <p className="text-xs text-muted-foreground">
            {uploadedCount} of {entries.length} uploaded
          </p>
          <div className="flex flex-wrap gap-2">
            {entries.map((entry, i) => (
              <Badge
                key={entry.file.name}
                variant={entry.status === "uploaded" ? "default" : "secondary"}
                className="gap-2 py-1.5 pl-2 pr-1"
              >
                {entry.status === "uploaded" ? (
                  <Check className="h-3.5 w-3.5" />
                ) : isAudioFile(entry.file) ? (
                  <FileAudio className="h-3.5 w-3.5" />
                ) : (
                  <Presentation className="h-3.5 w-3.5" />
                )}
                <span className="max-w-[180px] truncate text-xs">
                  {entry.file.name}
                </span>
                {entry.status === "uploading" && (
                  <span className="text-xs">...</span>
                )}
                {entry.status === "error" && (
                  <span className="text-xs text-red-500">failed</span>
                )}
                {entry.status === "pending" && (
                  <button
                    type="button"
                    aria-label={`Remove ${entry.file.name}`}
                    onClick={() => removeEntry(i)}
                    className="ml-1 rounded-full p-0.5 hover:bg-muted"
                  >
                    <X className="h-3 w-3" />
                  </button>
                )}
              </Badge>
            ))}
          </div>

          {pendingCount > 0 && (
            <Button
              onClick={handleUploadAll}
              disabled={uploading}
              className="w-full"
            >
              {uploading
                ? "Uploading..."
                : `Upload ${pendingCount} File${pendingCount !== 1 ? "s" : ""}`}
            </Button>
          )}
        </div>
      )}

      <p className="text-xs text-muted-foreground text-center">
        This is optional — you can always add materials later from the course
        page.
      </p>

      <div className="flex justify-end">
        <Button onClick={onContinue}>Continue &rarr;</Button>
      </div>
    </div>
  );
}
