"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { format } from "date-fns";
import { toast } from "sonner";
import Link from "next/link";
import { Pencil, Trash2, UploadCloud } from "lucide-react";

import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import {
  Tabs,
  TabsContent,
  TabsList,
  TabsTrigger,
} from "@/components/ui/tabs";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { CourseForm } from "@/components/course-form";
import { SyllabusUpload } from "@/components/syllabus-upload";
import { AssessmentCalendar } from "@/components/assessment-calendar";
import type { CalendarAssessment } from "@/components/assessment-calendar";
import { Skeleton } from "@/components/ui/skeleton";
import { LectureList } from "@/components/lectures/lecture-list";
import { QuizList } from "@/components/quiz/QuizList";
import { SearchPageClient } from "@/components/search/search-page-client";
import { FloatingQAButton } from "@/components/chat/floating-qa-button";
import { deleteCourse, getAssessments } from "@/lib/api";
import type { Course, Syllabus } from "@/types/database";

const GRADE_MAP: Record<string, string> = {
  "0.97": "A+ (97%)",
  "0.93": "A (93%)",
  "0.9": "A- (90%)",
  "0.87": "B+ (87%)",
  "0.83": "B (83%)",
  "0.8": "B- (80%)",
  "0.77": "C+ (77%)",
  "0.73": "C (73%)",
};

interface CourseDetailProps {
  course: Course;
  assessmentCount: number;
  syllabus: Syllabus | null;
}

function parseLocalDate(dateStr: string): Date {
  const [year, month, day] = dateStr.split("-").map(Number);
  return new Date(year, month - 1, day);
}

export function CourseDetail({
  course,
  assessmentCount,
  syllabus: initialSyllabus,
}: CourseDetailProps) {
  const router = useRouter();
  const [editOpen, setEditOpen] = useState(false);
  const [deleteOpen, setDeleteOpen] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [syllabus, setSyllabus] = useState<Syllabus | null>(initialSyllabus);
  const [reuploadOpen, setReuploadOpen] = useState(false);

  function handleUploadComplete(newSyllabus: Syllabus) {
    setSyllabus(newSyllabus);
    setReuploadOpen(false);
    router.refresh();
  }

  const start = parseLocalDate(course.semester_start);
  const end = parseLocalDate(course.semester_end);

  const gradeLabel =
    GRADE_MAP[course.target_grade.toString()] ??
    `${Math.round(course.target_grade * 100)}%`;

  async function handleDelete() {
    setDeleting(true);
    try {
      await deleteCourse(course.id);
      toast.success("Course deleted");
      router.push("/dashboard");
      router.refresh();
    } catch {
      toast.error("Failed to delete course");
    } finally {
      setDeleting(false);
    }
  }

  const holidays = course.holidays as
    | { name: string; start_date: string; end_date: string }[]
    | undefined;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">{course.name}</h1>
          {course.code && (
            <p className="text-muted-foreground">{course.code}</p>
          )}
        </div>
        <div className="flex gap-2">
          <Dialog open={editOpen} onOpenChange={setEditOpen}>
            <DialogTrigger asChild>
              <Button variant="outline" size="sm">
                <Pencil className="mr-2 h-4 w-4" />
                Edit
              </Button>
            </DialogTrigger>
            <DialogContent className="max-w-3xl max-h-[90vh] overflow-y-auto">
              <DialogHeader>
                <DialogTitle>Edit Course</DialogTitle>
                <DialogDescription>
                  Update your course details below.
                </DialogDescription>
              </DialogHeader>
              <CourseForm
                course={course}
                onSuccess={() => {
                  setEditOpen(false);
                  router.refresh();
                }}
              />
            </DialogContent>
          </Dialog>
          <Dialog open={deleteOpen} onOpenChange={setDeleteOpen}>
            <DialogTrigger asChild>
              <Button variant="destructive" size="sm">
                <Trash2 className="mr-2 h-4 w-4" />
                Delete
              </Button>
            </DialogTrigger>
            <DialogContent>
              <DialogHeader>
                <DialogTitle>Delete Course</DialogTitle>
                <DialogDescription>
                  This action cannot be undone.
                </DialogDescription>
              </DialogHeader>
              <p className="text-sm text-muted-foreground">
                Are you sure you want to delete &ldquo;{course.name}&rdquo;?
                This will also delete all associated syllabi, assessments, and
                concepts.
              </p>
              <div className="flex gap-2 justify-end">
                <Button
                  variant="outline"
                  onClick={() => setDeleteOpen(false)}
                >
                  Cancel
                </Button>
                <Button
                  variant="destructive"
                  onClick={handleDelete}
                  disabled={deleting}
                >
                  {deleting ? "Deleting..." : "Delete"}
                </Button>
              </div>
            </DialogContent>
          </Dialog>
        </div>
      </div>

      {/* Info badges */}
      <div className="flex flex-wrap gap-2">
        <Badge variant="outline">
          {format(start, "MMM d")} &ndash; {format(end, "MMM d, yyyy")}
        </Badge>
        {course.meeting_days.length > 0 && (
          <Badge variant="outline">{course.meeting_days.join(", ")}</Badge>
        )}
        {course.meeting_time && (
          <Badge variant="outline">{course.meeting_time}</Badge>
        )}
        <Badge variant="outline">Target: {gradeLabel}</Badge>
      </div>

      {/* Tabs */}
      <Tabs defaultValue="overview">
        <div className="overflow-x-auto -mx-1 px-1">
          <TabsList className="inline-flex w-max">
            <TabsTrigger value="overview">Overview</TabsTrigger>
            <TabsTrigger value="syllabus">Syllabus</TabsTrigger>
            <TabsTrigger value="lectures">Lectures</TabsTrigger>
            <TabsTrigger value="assessments">
              Assessments ({assessmentCount})
            </TabsTrigger>
            <TabsTrigger value="calendar">Calendar</TabsTrigger>
            <TabsTrigger value="search">Search</TabsTrigger>
            <TabsTrigger value="quizzes">Quizzes</TabsTrigger>
          </TabsList>
        </div>

        <TabsContent value="overview" className="mt-6 space-y-6">
          <Card>
            <CardHeader>
              <CardTitle>Course Details</CardTitle>
            </CardHeader>
            <CardContent className="grid gap-4 sm:grid-cols-2">
              <div>
                <p className="text-sm text-muted-foreground">Semester</p>
                <p>
                  {format(start, "MMMM d, yyyy")} &ndash;{" "}
                  {format(end, "MMMM d, yyyy")}
                </p>
              </div>
              <div>
                <p className="text-sm text-muted-foreground">
                  Meeting Schedule
                </p>
                <p>
                  {course.meeting_days.length > 0
                    ? course.meeting_days.join(", ")
                    : "Not set"}
                  {course.meeting_time && ` · ${course.meeting_time}`}
                </p>
              </div>
              <div>
                <p className="text-sm text-muted-foreground">Target Grade</p>
                <p>{gradeLabel}</p>
              </div>
              <div>
                <p className="text-sm text-muted-foreground">Assessments</p>
                <p>{assessmentCount}</p>
              </div>
            </CardContent>
          </Card>

          {holidays && holidays.length > 0 && (
            <Card>
              <CardHeader>
                <CardTitle>Holidays</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="space-y-2">
                  {holidays.map((h, i) => (
                    <div
                      key={i}
                      className="flex items-center justify-between text-sm"
                    >
                      <span>{h.name}</span>
                      <span className="text-muted-foreground">
                        {format(parseLocalDate(h.start_date), "MMM d")}{" "}
                        &ndash;{" "}
                        {format(parseLocalDate(h.end_date), "MMM d")}
                      </span>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>
          )}

          {!syllabus || reuploadOpen ? (
            <SyllabusUpload
              courseId={course.id}
              compact
              onUploadComplete={handleUploadComplete}
            />
          ) : (
            <Card>
              <CardHeader>
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <CardTitle>Syllabus</CardTitle>
                    {syllabus.needs_review && !syllabus.reviewed_at && (
                      <Badge
                        variant="outline"
                        className="text-amber-600 border-amber-300"
                      >
                        Needs Review
                      </Badge>
                    )}
                  </div>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => setReuploadOpen(true)}
                  >
                    <UploadCloud className="mr-2 h-4 w-4" />
                    Re-upload
                  </Button>
                </div>
                <CardDescription>
                  {syllabus.file_name ?? "Uploaded syllabus"}
                </CardDescription>
              </CardHeader>
              {syllabus.extraction_confidence !== null && (
                <CardContent>
                  <p className="text-sm text-muted-foreground">
                    Extraction confidence:{" "}
                    {Math.round(syllabus.extraction_confidence * 100)}%
                  </p>
                </CardContent>
              )}
            </Card>
          )}
        </TabsContent>

        <TabsContent value="syllabus" className="mt-6 space-y-6">
          {!syllabus || reuploadOpen ? (
            <SyllabusUpload
              courseId={course.id}
              onUploadComplete={handleUploadComplete}
            />
          ) : syllabus.needs_review && !syllabus.reviewed_at ? (
            <Card>
              <CardHeader>
                <div className="flex items-center justify-between">
                  <div>
                    <CardTitle>Review Extraction</CardTitle>
                    <CardDescription>
                      AI has extracted the following from your syllabus. Please
                      review for accuracy.
                    </CardDescription>
                  </div>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => setReuploadOpen(true)}
                  >
                    <UploadCloud className="mr-2 h-4 w-4" />
                    Re-upload
                  </Button>
                </div>
              </CardHeader>
              <CardContent className="space-y-4">
                {syllabus.grade_breakdown.length > 0 && (
                  <div>
                    <p className="text-sm font-medium mb-2">Grade Breakdown</p>
                    <div className="space-y-1">
                      {syllabus.grade_breakdown.map((item, i) => {
                        const gb = item as Record<string, unknown>;
                        return (
                          <div
                            key={i}
                            className="flex justify-between text-sm"
                          >
                            <span>{gb.component as string}</span>
                            <span className="text-muted-foreground">
                              {gb.weight as number}%
                            </span>
                          </div>
                        );
                      })}
                    </div>
                  </div>
                )}
                {syllabus.extraction_confidence !== null && (
                  <p className="text-xs text-muted-foreground">
                    Confidence:{" "}
                    {Math.round(syllabus.extraction_confidence * 100)}%
                  </p>
                )}
                <Button asChild>
                  <Link href={`/dashboard/courses/${course.id}/syllabus/review`}>
                    Review Extraction
                  </Link>
                </Button>
              </CardContent>
            </Card>
          ) : (
            <Card>
              <CardHeader>
                <div className="flex items-center justify-between">
                  <div>
                    <CardTitle>Syllabus Extraction</CardTitle>
                    <CardDescription>
                      {syllabus.reviewed_at
                        ? `Reviewed on ${format(new Date(syllabus.reviewed_at), "MMMM d, yyyy")}`
                        : "Extraction complete"}
                    </CardDescription>
                  </div>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => setReuploadOpen(true)}
                  >
                    <UploadCloud className="mr-2 h-4 w-4" />
                    Re-upload
                  </Button>
                </div>
              </CardHeader>
              <CardContent className="space-y-4">
                {syllabus.grade_breakdown.length > 0 && (
                  <div>
                    <p className="text-sm font-medium mb-2">Grade Breakdown</p>
                    <div className="space-y-1">
                      {syllabus.grade_breakdown.map((item, i) => {
                        const gb = item as Record<string, unknown>;
                        return (
                          <div
                            key={i}
                            className="flex justify-between text-sm"
                          >
                            <span>{gb.component as string}</span>
                            <span className="text-muted-foreground">
                              {gb.weight as number}%
                            </span>
                          </div>
                        );
                      })}
                    </div>
                  </div>
                )}
              </CardContent>
            </Card>
          )}
        </TabsContent>

        <TabsContent value="assessments" className="mt-6">
          <Card className="flex flex-col items-center justify-center py-16">
            <CardHeader className="items-center text-center">
              <CardTitle>No assessments yet</CardTitle>
              <CardDescription>
                Assessments will appear here once you upload and process a
                syllabus.
              </CardDescription>
            </CardHeader>
          </Card>
        </TabsContent>

        <TabsContent value="lectures" className="mt-6">
          <LectureList courseId={course.id} courseName={course.name} />
        </TabsContent>

        <TabsContent value="calendar" className="mt-6">
          <CourseCalendarTab course={course} />
        </TabsContent>

        <TabsContent value="search" className="mt-6">
          <SearchPageClient courseId={course.id} />
        </TabsContent>

        <TabsContent value="quizzes" className="mt-6">
          <QuizList courseId={course.id} courseName={course.name} />
        </TabsContent>
      </Tabs>

      <FloatingQAButton courseId={course.id} />
    </div>
  );
}

// ---------------------------------------------------------------------------
// CourseCalendarTab — lazy-loads assessments for a single course
// ---------------------------------------------------------------------------

function CourseCalendarTab({ course }: { course: Course }) {
  const [assessments, setAssessments] = useState<CalendarAssessment[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        const data = await getAssessments(course.id);
        if (cancelled) return;
        setAssessments(
          data.map((a) => ({
            ...a,
            course_name: course.name,
            course_code: course.code,
          })),
        );
      } catch {
        // Silently handle — calendar will show empty
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    load();
    return () => {
      cancelled = true;
    };
  }, [course.id, course.name, course.code]);

  if (loading) {
    return (
      <Card>
        <CardContent className="pt-6 space-y-3">
          <Skeleton className="h-6 w-1/3" />
          <div className="grid grid-cols-7 gap-2">
            {Array.from({ length: 35 }, (_, i) => (
              <Skeleton key={i} className="h-10 w-full" />
            ))}
          </div>
        </CardContent>
      </Card>
    );
  }

  if (assessments.length === 0) {
    return (
      <Card className="flex flex-col items-center justify-center py-16">
        <CardHeader className="items-center text-center">
          <CardTitle>No assessments with dates</CardTitle>
          <CardDescription>
            Upload a syllabus to populate the calendar with assessment dates.
          </CardDescription>
        </CardHeader>
      </Card>
    );
  }

  return <AssessmentCalendar assessments={assessments} />;
}
