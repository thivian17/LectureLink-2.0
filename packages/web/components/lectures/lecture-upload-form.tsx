"use client";

import { useState, useCallback } from "react";
import { useRouter } from "next/navigation";
import { format } from "date-fns";
import { toast } from "sonner";
import { ArrowLeft, Upload, CalendarIcon } from "lucide-react";
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
import { Calendar } from "@/components/ui/calendar";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import { UploadDropzone } from "@/components/lectures/upload-dropzone";
import { LectureProcessingStatus } from "@/components/lectures/processing-status";
import { uploadLecture, AuthError, RateLimitError } from "@/lib/api";
import { cn } from "@/lib/utils";

interface LectureUploadFormProps {
  courseId: string;
  courseName: string;
}

type Phase = "form" | "uploading" | "processing";

export function LectureUploadForm({
  courseId,
  courseName,
}: LectureUploadFormProps) {
  const router = useRouter();
  const [phase, setPhase] = useState<Phase>("form");
  const [files, setFiles] = useState<File[]>([]);
  const [title, setTitle] = useState("");
  const [lectureNumber, setLectureNumber] = useState("");
  const [lectureDate, setLectureDate] = useState<Date | undefined>(new Date());
  const [uploading, setUploading] = useState(false);
  const [lectureId, setLectureId] = useState<string | null>(null);

  const canSubmit = files.length > 0 && title.trim().length > 0 && !uploading;

  const handleSubmit = useCallback(
    async (e: React.FormEvent) => {
      e.preventDefault();
      if (!canSubmit) return;

      setUploading(true);
      setPhase("uploading");

      try {
        const formData = new FormData();
        files.forEach((f) => formData.append("files", f));
        formData.append("title", title.trim());
        if (lectureNumber) {
          formData.append("lecture_number", lectureNumber);
        }
        if (lectureDate) {
          formData.append("lecture_date", format(lectureDate, "yyyy-MM-dd"));
        }

        const result = await uploadLecture(courseId, formData);
        setLectureId(result.lecture_id);
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
          err instanceof Error ? err.message : "Failed to upload lecture",
        );
      } finally {
        setUploading(false);
      }
    },
    [canSubmit, files, title, lectureNumber, lectureDate, courseId],
  );

  // Show processing status after upload
  if (phase === "processing" && lectureId) {
    return (
      <div className="space-y-6">
        <div>
          <h2 className="text-lg font-semibold">Processing Lecture</h2>
          <p className="text-sm text-muted-foreground">{title}</p>
        </div>
        <LectureProcessingStatus lectureId={lectureId} courseId={courseId} />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center gap-4">
        <Button variant="ghost" size="icon" asChild>
          <Link href={`/dashboard/courses/${courseId}/lectures`}>
            <ArrowLeft className="h-4 w-4" />
          </Link>
        </Button>
        <div>
          <h2 className="text-lg font-semibold">Upload Lecture</h2>
          <p className="text-sm text-muted-foreground">{courseName}</p>
        </div>
      </div>

      <form onSubmit={handleSubmit} className="space-y-6">
        {/* File drop zone */}
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Files</CardTitle>
            <CardDescription>
              Upload audio recordings and/or slide decks for this lecture.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <UploadDropzone files={files} onFilesChange={setFiles} />
            {files.length === 0 && (
              <p className="mt-2 text-xs text-muted-foreground">
                Please add at least one audio or slides file.
              </p>
            )}
          </CardContent>
        </Card>

        {/* Lecture details */}
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Lecture Details</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="title">Title *</Label>
              <Input
                id="title"
                placeholder="e.g., Lecture 5: Introduction to Entropy"
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                required
              />
            </div>

            <div className="grid gap-4 sm:grid-cols-2">
              <div className="space-y-2">
                <Label htmlFor="lectureNumber">Lecture Number</Label>
                <Input
                  id="lectureNumber"
                  type="number"
                  min={1}
                  placeholder="e.g., 5"
                  value={lectureNumber}
                  onChange={(e) => setLectureNumber(e.target.value)}
                />
              </div>

              <div className="space-y-2">
                <Label>Lecture Date</Label>
                <Popover>
                  <PopoverTrigger asChild>
                    <Button
                      variant="outline"
                      className={cn(
                        "w-full justify-start text-left font-normal",
                        !lectureDate && "text-muted-foreground",
                      )}
                    >
                      <CalendarIcon className="mr-2 h-4 w-4" />
                      {lectureDate
                        ? format(lectureDate, "MMM d, yyyy")
                        : "Pick a date"}
                    </Button>
                  </PopoverTrigger>
                  <PopoverContent className="w-auto p-0" align="start">
                    <Calendar
                      mode="single"
                      selected={lectureDate}
                      onSelect={setLectureDate}
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
              router.push(`/dashboard/courses/${courseId}/lectures`)
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
