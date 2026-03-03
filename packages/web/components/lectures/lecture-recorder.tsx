"use client";

import { useState, useEffect, useRef, useCallback } from "react";
import { useRouter } from "next/navigation";
import { format } from "date-fns";
import { toast } from "sonner";
import { Mic, Square, Upload, Loader2, CalendarIcon } from "lucide-react";

import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
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
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { LectureProcessingStatus } from "@/components/lectures/processing-status";
import { uploadLecture, getCourses, AuthError, RateLimitError } from "@/lib/api";
import { cn } from "@/lib/utils";
import type { Course } from "@/types/database";

type Phase = "idle" | "recording" | "recorded" | "uploading" | "processing";

function formatDuration(seconds: number): string {
  const m = Math.floor(seconds / 60);
  const s = seconds % 60;
  return `${m.toString().padStart(2, "0")}:${s.toString().padStart(2, "0")}`;
}

export function LectureRecorder() {
  const router = useRouter();

  // Phase
  const [phase, setPhase] = useState<Phase>("idle");

  // Courses
  const [courses, setCourses] = useState<Course[]>([]);
  const [selectedCourseId, setSelectedCourseId] = useState("");
  const [loadingCourses, setLoadingCourses] = useState(true);

  // Lecture details
  const [lectureNumber, setLectureNumber] = useState("");
  const [lectureDate, setLectureDate] = useState<Date | undefined>(new Date());

  // Recording
  const [elapsedSeconds, setElapsedSeconds] = useState(0);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const streamRef = useRef<MediaStream | null>(null);

  // Recorded audio
  const [audioBlob, setAudioBlob] = useState<Blob | null>(null);
  const [audioUrl, setAudioUrl] = useState<string | null>(null);

  // Upload result
  const [lectureId, setLectureId] = useState<string | null>(null);

  // Error
  const [error, setError] = useState<string | null>(null);

  // Fetch courses on mount
  useEffect(() => {
    getCourses()
      .then((data) => {
        setCourses(data);
        if (data.length === 1) setSelectedCourseId(data[0].id);
      })
      .catch((err) => {
        if (err instanceof AuthError) {
          router.push("/login");
          return;
        }
        toast.error("Failed to load courses");
      })
      .finally(() => setLoadingCourses(false));
  }, [router]);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (streamRef.current) {
        streamRef.current.getTracks().forEach((t) => t.stop());
      }
      if (timerRef.current) clearInterval(timerRef.current);
    };
  }, []);

  // Revoke old audio URL when it changes
  useEffect(() => {
    return () => {
      if (audioUrl) URL.revokeObjectURL(audioUrl);
    };
  }, [audioUrl]);

  const startRecording = useCallback(async () => {
    setError(null);
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      streamRef.current = stream;

      let mimeType = "audio/webm";
      if (typeof MediaRecorder.isTypeSupported === "function" && !MediaRecorder.isTypeSupported(mimeType)) {
        mimeType = "audio/mp4"; // Safari fallback
      }

      const mediaRecorder = new MediaRecorder(stream, { mimeType });
      mediaRecorderRef.current = mediaRecorder;
      chunksRef.current = [];

      mediaRecorder.ondataavailable = (e) => {
        if (e.data.size > 0) chunksRef.current.push(e.data);
      };

      mediaRecorder.onstop = () => {
        const blob = new Blob(chunksRef.current, { type: mimeType });
        setAudioBlob(blob);
        setAudioUrl(URL.createObjectURL(blob));
        setPhase("recorded");
        stream.getTracks().forEach((t) => t.stop());
        streamRef.current = null;
      };

      mediaRecorder.start(1000);
      setElapsedSeconds(0);
      timerRef.current = setInterval(() => {
        setElapsedSeconds((prev) => prev + 1);
      }, 1000);
      setPhase("recording");
    } catch (err) {
      if (err instanceof DOMException && err.name === "NotAllowedError") {
        setError("Microphone access denied. Please allow microphone access in your browser settings.");
      } else {
        setError("Could not access microphone. Please check your device settings.");
      }
    }
  }, []);

  const stopRecording = useCallback(() => {
    if (timerRef.current) {
      clearInterval(timerRef.current);
      timerRef.current = null;
    }
    mediaRecorderRef.current?.stop();
  }, []);

  const discardRecording = useCallback(() => {
    setAudioBlob(null);
    setAudioUrl(null);
    setElapsedSeconds(0);
    setPhase("idle");
  }, []);

  const handleSubmit = useCallback(async () => {
    if (!audioBlob || !selectedCourseId || !lectureNumber.trim()) return;

    setPhase("uploading");
    try {
      const ext = audioBlob.type.includes("mp4") ? "m4a" : "webm";
      const file = new File([audioBlob], `recording-${Date.now()}.${ext}`, {
        type: audioBlob.type,
      });

      const formData = new FormData();
      formData.append("files", file);
      formData.append("lecture_number", lectureNumber);
      if (lectureDate) {
        formData.append("lecture_date", format(lectureDate, "yyyy-MM-dd"));
      }

      const result = await uploadLecture(selectedCourseId, formData);
      setLectureId(result.lecture_id);
      setPhase("processing");
      toast.success("Upload complete! Processing started.");
    } catch (err) {
      setPhase("recorded");
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
        err instanceof Error ? err.message : "Failed to upload recording",
      );
    }
  }, [audioBlob, selectedCourseId, lectureNumber, lectureDate, router]);

  const canSubmit =
    phase === "recorded" &&
    audioBlob !== null &&
    selectedCourseId !== "" &&
    lectureNumber.trim().length > 0;

  // Processing phase
  if (phase === "processing" && lectureId) {
    return (
      <div className="space-y-6">
        <div>
          <h2 className="text-lg font-semibold">Processing Lecture</h2>
          <p className="text-sm text-muted-foreground">
            Lecture {lectureNumber}
          </p>
        </div>
        <LectureProcessingStatus lectureId={lectureId} courseId={selectedCourseId} />
      </div>
    );
  }

  const fileSizeMB = audioBlob ? (audioBlob.size / (1024 * 1024)).toFixed(1) : null;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Record Lecture</h1>
        <p className="text-muted-foreground">
          Record a lecture directly from your microphone.
        </p>
      </div>

      {/* Recording card */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Recording</CardTitle>
        </CardHeader>
        <CardContent>
          {phase === "idle" && (
            <div className="flex flex-col items-center gap-4 rounded-lg border-2 border-dashed p-8">
              <Mic className="h-10 w-10 text-muted-foreground" />
              <p className="text-sm text-muted-foreground">
                Click to start recording from your microphone.
              </p>
              <Button onClick={startRecording}>
                <Mic className="mr-2 h-4 w-4" />
                Start Recording
              </Button>
              {error && (
                <p className="text-sm text-destructive">{error}</p>
              )}
            </div>
          )}

          {phase === "recording" && (
            <div className="flex flex-col items-center gap-4 p-8">
              <div className="flex items-center gap-2">
                <span className="relative flex h-3 w-3">
                  <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-red-400 opacity-75" />
                  <span className="relative inline-flex h-3 w-3 rounded-full bg-red-500" />
                </span>
                <span className="text-sm font-medium text-red-600">Recording</span>
              </div>
              <p className="font-mono text-3xl tabular-nums">
                {formatDuration(elapsedSeconds)}
              </p>
              <Button variant="destructive" onClick={stopRecording}>
                <Square className="mr-2 h-4 w-4" />
                Stop Recording
              </Button>
            </div>
          )}

          {phase === "recorded" && audioUrl && (
            <div className="flex flex-col items-center gap-4 p-4">
              {/* eslint-disable-next-line jsx-a11y/media-has-caption */}
              <audio controls src={audioUrl} className="w-full max-w-md" />
              <div className="flex items-center gap-4 text-sm text-muted-foreground">
                <span>Duration: {formatDuration(elapsedSeconds)}</span>
                <span>{fileSizeMB} MB</span>
              </div>
            </div>
          )}

          {phase === "uploading" && (
            <div className="flex flex-col items-center gap-4 p-8">
              <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
              <p className="text-sm text-muted-foreground">Uploading recording...</p>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Lecture details card */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Lecture Details</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          {/* Course selector */}
          <div className="space-y-2">
            <Label>Course *</Label>
            {loadingCourses ? (
              <p className="text-sm text-muted-foreground">Loading courses...</p>
            ) : courses.length === 0 ? (
              <p className="text-sm text-muted-foreground">
                No courses found. Please{" "}
                <a href="/dashboard/courses/new" className="underline">
                  create a course
                </a>{" "}
                first.
              </p>
            ) : (
              <Select value={selectedCourseId} onValueChange={setSelectedCourseId}>
                <SelectTrigger className="w-full">
                  <SelectValue placeholder="Select a course" />
                </SelectTrigger>
                <SelectContent>
                  {courses.map((course) => (
                    <SelectItem key={course.id} value={course.id}>
                      {course.code ? `${course.code} - ` : ""}
                      {course.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            )}
          </div>

          {/* Lecture number + date */}
          <div className="grid gap-4 sm:grid-cols-2">
            <div className="space-y-2">
              <Label htmlFor="lectureNumber">Lecture Number *</Label>
              <Input
                id="lectureNumber"
                type="number"
                min={1}
                placeholder="e.g., 5"
                value={lectureNumber}
                onChange={(e) => setLectureNumber(e.target.value)}
                required
              />
              <p className="text-xs text-muted-foreground">
                A title will be auto-generated from the content.
              </p>
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

      {/* Submit buttons */}
      <div className="flex justify-end gap-2">
        {phase === "recorded" && (
          <Button variant="outline" onClick={discardRecording}>
            Re-record
          </Button>
        )}
        <Button onClick={handleSubmit} disabled={!canSubmit}>
          <Upload className="mr-2 h-4 w-4" />
          Upload and Process
        </Button>
      </div>
    </div>
  );
}
