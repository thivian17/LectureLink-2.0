"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { format } from "date-fns";
import { toast } from "sonner";
import Link from "next/link";
import {
  ArrowLeft,
  CalendarDays,
  GraduationCap,
  Pencil,
  Scale,
  Trash2,
} from "lucide-react";

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
import {
  deleteCourse,
  deleteAssessment,
  getAssessments,
  updateAssessment,
} from "@/lib/api";
import type { UpdateAssessmentInput } from "@/lib/api";
import { AssessmentEditDialog } from "@/components/syllabus-review/assessment-edit-dialog";
import type { Assessment, Course, Syllabus } from "@/types/database";
import type { SyllabusExtraction } from "@/types/extraction";

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

/** Format "HH:MM-HH:MM" to "H:MM AM – H:MM PM". Falls back to raw string. */
function formatMeetingTime(raw: string | null): string | null {
  if (!raw) return null;
  const parts = raw.split("-").map((s) => s.trim());
  if (parts.length !== 2) return raw;

  function to12h(hhmm: string): string {
    const [hStr, mStr] = hhmm.split(":");
    if (!hStr || !mStr) return hhmm;
    const h = parseInt(hStr, 10);
    const ampm = h < 12 ? "AM" : "PM";
    const h12 = h % 12 || 12;
    return `${h12}:${mStr} ${ampm}`;
  }

  return `${to12h(parts[0])} – ${to12h(parts[1])}`;
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

  function handleUploadComplete(newSyllabus: Syllabus) {
    setSyllabus(newSyllabus);
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
      {/* Back to Study Hub */}
      <Link
        href="/dashboard"
        className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground transition-colors"
      >
        <ArrowLeft className="h-3.5 w-3.5" />
        Study Hub
      </Link>

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
          <Badge variant="outline">{formatMeetingTime(course.meeting_time)}</Badge>
        )}
        <Badge variant="outline">Target: {gradeLabel}</Badge>
      </div>

      {/* Study Tutor CTA */}
      <Card className="border-primary/20 bg-gradient-to-r from-primary/5 via-primary/10 to-primary/5 shadow-sm">
        <CardContent className="pt-6">
          <div className="flex items-center justify-between gap-4">
            <div className="flex items-center gap-3 min-w-0">
              <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-primary/10">
                <GraduationCap className="h-5 w-5 text-primary" />
              </div>
              <div>
                <p className="font-semibold">Study Tutor</p>
                <p className="text-sm text-muted-foreground">
                  Interactive AI lessons tailored to your weak spots
                </p>
              </div>
            </div>
            <Button asChild>
              <Link href={`/dashboard/courses/${course.id}/tutor`}>
                Start Studying
              </Link>
            </Button>
          </div>
        </CardContent>
      </Card>

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
            <TabsTrigger value="quizzes">Practice Tests</TabsTrigger>
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
                  {course.meeting_time && ` · ${formatMeetingTime(course.meeting_time)}`}
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

          {!syllabus ? (
            <SyllabusUpload
              courseId={course.id}
              compact
              onUploadComplete={handleUploadComplete}
            />
          ) : (
            <SyllabusOverviewCard syllabus={syllabus} courseId={course.id} />
          )}
        </TabsContent>

        <TabsContent value="syllabus" className="mt-6 space-y-6">
          {!syllabus ? (
            <SyllabusUpload
              courseId={course.id}
              onUploadComplete={handleUploadComplete}
            />
          ) : syllabus.needs_review && !syllabus.reviewed_at ? (
            <Card>
              <CardHeader>
                <div>
                  <CardTitle>Review Extraction</CardTitle>
                  <CardDescription>
                    AI has extracted the following from your syllabus. Please
                    review for accuracy.
                  </CardDescription>
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
            <SyllabusDetailView syllabus={syllabus} courseId={course.id} />
          )}
        </TabsContent>

        <TabsContent value="assessments" className="mt-6">
          <CourseAssessmentsTab courseId={course.id} />
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

// ---------------------------------------------------------------------------
// CourseAssessmentsTab — lazy-loads and displays assessments for a course
// ---------------------------------------------------------------------------

function CourseAssessmentsTab({ courseId }: { courseId: string }) {
  const [assessments, setAssessments] = useState<Assessment[]>([]);
  const [loading, setLoading] = useState(true);
  const [editingAssessment, setEditingAssessment] = useState<Assessment | null>(
    null,
  );
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [confirmDeleteId, setConfirmDeleteId] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        const data = await getAssessments(courseId);
        if (cancelled) return;
        setAssessments(data);
      } catch {
        toast.error("Failed to load assessments");
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    load();
    return () => {
      cancelled = true;
    };
  }, [courseId]);

  async function handleSave(updates: UpdateAssessmentInput) {
    if (!editingAssessment) return;
    try {
      const updated = await updateAssessment(editingAssessment.id, updates);
      setAssessments((prev) =>
        prev.map((a) => (a.id === updated.id ? updated : a)),
      );
      toast.success("Assessment updated");
    } catch {
      toast.error("Failed to update assessment");
    }
  }

  async function handleDelete(id: string) {
    setDeletingId(id);
    try {
      await deleteAssessment(id);
      setAssessments((prev) => prev.filter((a) => a.id !== id));
      toast.success("Assessment deleted");
    } catch {
      toast.error("Failed to delete assessment");
    } finally {
      setDeletingId(null);
      setConfirmDeleteId(null);
    }
  }

  if (loading) {
    return (
      <div className="space-y-3">
        {Array.from({ length: 4 }, (_, i) => (
          <Card key={i}>
            <CardContent className="pt-6 flex items-center gap-4">
              <Skeleton className="h-5 w-1/3" />
              <Skeleton className="h-4 w-20" />
              <Skeleton className="h-4 w-24 ml-auto" />
            </CardContent>
          </Card>
        ))}
      </div>
    );
  }

  if (assessments.length === 0) {
    return (
      <Card className="flex flex-col items-center justify-center py-16">
        <CardHeader className="items-center text-center">
          <CardTitle>No assessments yet</CardTitle>
          <CardDescription>
            Assessments will appear here once you upload and process a syllabus.
          </CardDescription>
        </CardHeader>
      </Card>
    );
  }

  return (
    <>
      <div className="space-y-3">
        {assessments.map((a) => (
          <Card key={a.id}>
            <CardContent className="pt-6">
              <div className="flex items-start justify-between gap-4">
                <div className="space-y-1 min-w-0">
                  <p className="font-medium leading-tight">{a.title}</p>
                  <div className="flex flex-wrap items-center gap-3 text-sm text-muted-foreground">
                    <Badge variant="outline" className="text-xs capitalize">
                      {a.type}
                    </Badge>
                    {a.weight_percent != null && (
                      <span className="flex items-center gap-1">
                        <Scale className="h-3 w-3" />
                        {a.weight_percent}%
                      </span>
                    )}
                    {a.due_date && (
                      <span className="flex items-center gap-1">
                        <CalendarDays className="h-3 w-3" />
                        {format(parseLocalDate(a.due_date), "MMM d, yyyy")}
                        {a.is_date_ambiguous && (
                          <span
                            className="text-yellow-600"
                            title="Date may be ambiguous"
                          >
                            ?
                          </span>
                        )}
                      </span>
                    )}
                  </div>
                  {a.topics && a.topics.length > 0 && (
                    <div className="flex flex-wrap gap-1 pt-1">
                      {a.topics.map((topic) => (
                        <Badge
                          key={topic}
                          variant="secondary"
                          className="text-xs"
                        >
                          {topic}
                        </Badge>
                      ))}
                    </div>
                  )}
                </div>
                <div className="flex items-center gap-1 shrink-0">
                  <Button
                    variant="ghost"
                    size="icon"
                    className="h-8 w-8"
                    onClick={() => setEditingAssessment(a)}
                  >
                    <Pencil className="h-4 w-4" />
                  </Button>
                  {confirmDeleteId === a.id ? (
                    <div className="flex items-center gap-1">
                      <Button
                        variant="destructive"
                        size="sm"
                        className="h-8 text-xs"
                        disabled={deletingId === a.id}
                        onClick={() => handleDelete(a.id)}
                      >
                        {deletingId === a.id ? "..." : "Confirm"}
                      </Button>
                      <Button
                        variant="ghost"
                        size="sm"
                        className="h-8 text-xs"
                        onClick={() => setConfirmDeleteId(null)}
                      >
                        Cancel
                      </Button>
                    </div>
                  ) : (
                    <Button
                      variant="ghost"
                      size="icon"
                      className="h-8 w-8 text-muted-foreground hover:text-destructive"
                      onClick={() => setConfirmDeleteId(a.id)}
                    >
                      <Trash2 className="h-4 w-4" />
                    </Button>
                  )}
                </div>
              </div>
            </CardContent>
          </Card>
        ))}
      </div>

      {editingAssessment && (
        <AssessmentEditDialog
          open={!!editingAssessment}
          onOpenChange={(open) => {
            if (!open) setEditingAssessment(null);
          }}
          assessment={editingAssessment}
          onSave={handleSave}
        />
      )}
    </>
  );
}

// ---------------------------------------------------------------------------
// SyllabusOverviewCard — concise syllabus summary for the Overview tab
// ---------------------------------------------------------------------------

function SyllabusOverviewCard({
  syllabus,
  courseId,
}: {
  syllabus: Syllabus;
  courseId: string;
}) {
  const extraction = syllabus.raw_extraction as SyllabusExtraction | null;
  const gradeBreakdown = syllabus.grade_breakdown as {
    component: string;
    weight: number;
  }[];

  const instructor = extraction?.instructor_name?.value;
  const email = extraction?.instructor_email?.value;
  const officeHours = extraction?.office_hours?.value;

  return (
    <Card>
      <CardHeader>
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
        {(instructor || email) && (
          <CardDescription>
            {instructor}
            {email && ` · ${email}`}
          </CardDescription>
        )}
      </CardHeader>
      <CardContent className="space-y-4">
        {officeHours && (
          <div>
            <p className="text-sm text-muted-foreground">Office Hours</p>
            <p className="text-sm">{officeHours}</p>
          </div>
        )}

        {gradeBreakdown.length > 0 && (
          <div>
            <p className="text-sm font-medium mb-2">Grade Breakdown</p>
            <div className="space-y-1.5">
              {gradeBreakdown.map((item, i) => (
                <div key={i} className="flex items-center gap-2">
                  <div className="h-1.5 flex-1 rounded-full bg-muted overflow-hidden">
                    <div
                      className="h-full rounded-full bg-primary/60"
                      style={{ width: `${item.weight}%` }}
                    />
                  </div>
                  <span className="text-sm min-w-[120px] truncate">
                    {item.component}
                  </span>
                  <span className="text-sm text-muted-foreground tabular-nums w-10 text-right">
                    {item.weight}%
                  </span>
                </div>
              ))}
            </div>
          </div>
        )}

        <p className="text-xs text-muted-foreground">
          {syllabus.file_name}
          {syllabus.reviewed_at && " · Reviewed and confirmed"}
        </p>
      </CardContent>
    </Card>
  );
}

// ---------------------------------------------------------------------------
// SyllabusDetailView — full syllabus details for the Syllabus tab
// ---------------------------------------------------------------------------

function SyllabusDetailView({
  syllabus,
  courseId,
}: {
  syllabus: Syllabus;
  courseId: string;
}) {
  const extraction = syllabus.raw_extraction as SyllabusExtraction | null;
  const gradeBreakdown = syllabus.grade_breakdown as {
    component: string;
    weight: number;
    drop_policy?: string | null;
  }[];

  const instructor = extraction?.instructor_name?.value;
  const email = extraction?.instructor_email?.value;
  const officeHours = extraction?.office_hours?.value;
  const schedule = extraction?.weekly_schedule ?? [];
  const policies = extraction?.policies ?? {};
  const policyEntries = Object.entries(policies);

  const totalWeight = gradeBreakdown.reduce((sum, g) => sum + (g.weight ?? 0), 0);

  return (
    <div className="space-y-6">
      {/* Course info */}
      {(instructor || email || officeHours) && (
        <Card>
          <CardHeader>
            <CardTitle>Course Information</CardTitle>
          </CardHeader>
          <CardContent className="grid gap-4 sm:grid-cols-2">
            {instructor && (
              <div>
                <p className="text-sm text-muted-foreground">Instructor</p>
                <p className="text-sm">{instructor}</p>
              </div>
            )}
            {email && (
              <div>
                <p className="text-sm text-muted-foreground">Email</p>
                <p className="text-sm">{email}</p>
              </div>
            )}
            {officeHours && (
              <div className="sm:col-span-2">
                <p className="text-sm text-muted-foreground">Office Hours</p>
                <p className="text-sm">{officeHours}</p>
              </div>
            )}
          </CardContent>
        </Card>
      )}

      {/* Grade breakdown */}
      {gradeBreakdown.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle>Grade Breakdown</CardTitle>
            <CardDescription>
              {totalWeight === 100
                ? "Weights sum to 100%"
                : `Weights sum to ${totalWeight}%`}
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="rounded-lg border overflow-hidden">
              <div className="grid grid-cols-[1fr_80px_1fr] gap-2 bg-muted/50 px-4 py-2 text-xs font-medium text-muted-foreground">
                <span>Component</span>
                <span className="text-right">Weight</span>
                <span>Drop Policy</span>
              </div>
              {gradeBreakdown.map((item, i) => (
                <div
                  key={i}
                  className={`grid grid-cols-[1fr_80px_1fr] gap-2 px-4 py-2.5 text-sm ${
                    i % 2 === 1 ? "bg-muted/30" : ""
                  }`}
                >
                  <span>{item.component}</span>
                  <span className="text-right tabular-nums font-medium">
                    {item.weight}%
                  </span>
                  <span className="text-muted-foreground">
                    {item.drop_policy || "\u2014"}
                  </span>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Weekly schedule */}
      {schedule.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle>Weekly Schedule</CardTitle>
            <CardDescription>
              {schedule.length} weeks extracted from syllabus
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="rounded-lg border overflow-hidden">
              <div className="grid grid-cols-[60px_1fr_1fr] gap-2 bg-muted/50 px-4 py-2 text-xs font-medium text-muted-foreground">
                <span>Week</span>
                <span>Topics</span>
                <span>Readings / Due</span>
              </div>
              {schedule.map((week) => (
                <div
                  key={week.week_number}
                  className={`grid grid-cols-[60px_1fr_1fr] gap-2 px-4 py-2.5 text-sm ${
                    week.week_number % 2 === 0 ? "bg-muted/30" : ""
                  }`}
                >
                  <span className="tabular-nums text-muted-foreground">
                    {week.week_number}
                  </span>
                  <div>
                    {week.topics.length > 0 ? (
                      <p>{week.topics.join(", ")}</p>
                    ) : (
                      <p className="text-muted-foreground">&mdash;</p>
                    )}
                    {week.date_range?.value && (
                      <p className="text-xs text-muted-foreground mt-0.5">
                        {week.date_range.value}
                      </p>
                    )}
                  </div>
                  <div className="space-y-0.5">
                    {week.readings.map((r, ri) => (
                      <p key={ri} className="text-muted-foreground text-xs">
                        {r}
                      </p>
                    ))}
                    {week.due_items.map((d, di) => (
                      <p key={di} className="text-xs font-medium text-amber-600">
                        Due: {d}
                      </p>
                    ))}
                    {week.readings.length === 0 && week.due_items.length === 0 && (
                      <p className="text-muted-foreground">&mdash;</p>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Policies */}
      {policyEntries.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle>Course Policies</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            {policyEntries.map(([key, value]) => (
              <div key={key}>
                <p className="text-sm font-medium capitalize">
                  {key.replace(/_/g, " ")}
                </p>
                <p className="text-sm text-muted-foreground mt-0.5 whitespace-pre-line">
                  {value}
                </p>
              </div>
            ))}
          </CardContent>
        </Card>
      )}

      {/* Source file */}
      <p className="text-xs text-muted-foreground px-1">
        Source: {syllabus.file_name}
        {syllabus.reviewed_at &&
          ` · Reviewed ${format(new Date(syllabus.reviewed_at), "MMM d, yyyy")}`}
      </p>
    </div>
  );
}
