import Link from "next/link";
import { format } from "date-fns";
import { createClient } from "@/lib/supabase/server";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { BookOpen, Plus } from "lucide-react";
import { StudyActionsLoader } from "@/components/study-hub/StudyActionsLoader";
import type { Course } from "@/types/database";

function parseLocalDate(dateStr: string): Date {
  const [year, month, day] = dateStr.split("-").map(Number);
  return new Date(year, month - 1, day);
}

const GRADE_MAP: Record<string, string> = {
  "0.97": "A+",
  "0.93": "A",
  "0.9": "A-",
  "0.87": "B+",
  "0.83": "B",
  "0.8": "B-",
  "0.77": "C+",
  "0.73": "C",
};

export default async function DashboardPage() {
  const supabase = await createClient();
  const { data: courses } = await supabase
    .from("courses")
    .select("*, assessments(count)")
    .order("created_at", { ascending: false })
    .returns<(Course & { assessments: [{ count: number }] })[]>();

  const hasCourses = courses && courses.length > 0;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Study Hub</h1>
          <p className="text-muted-foreground">
            {hasCourses
              ? "Here's what to focus on today."
              : "Get started by adding your first course."}
          </p>
        </div>
        <Button asChild>
          <Link href="/dashboard/courses/new">
            <Plus className="mr-2 h-4 w-4" />
            Add Course
          </Link>
        </Button>
      </div>

      {hasCourses && <StudyActionsLoader />}

      {!hasCourses ? (
        <Card className="flex flex-col items-center justify-center py-16">
          <CardHeader className="items-center text-center">
            <div className="mb-2 flex h-12 w-12 items-center justify-center rounded-full bg-muted">
              <BookOpen className="h-6 w-6 text-muted-foreground" />
            </div>
            <CardTitle>No courses yet</CardTitle>
            <CardDescription>
              Add your first course and upload a syllabus to get started.
            </CardDescription>
          </CardHeader>
          <Button asChild>
            <Link href="/dashboard/courses/new">
              <Plus className="mr-2 h-4 w-4" />
              Add Course
            </Link>
          </Button>
        </Card>
      ) : (
        <div>
          <h2 className="text-lg font-semibold mb-3">Your Courses</h2>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {courses.map((course) => {
              const start = parseLocalDate(course.semester_start);
              const end = parseLocalDate(course.semester_end);
              const assessmentCount = course.assessments?.[0]?.count ?? 0;
              const gradeLabel =
                GRADE_MAP[course.target_grade.toString()] ??
                `${Math.round(course.target_grade * 100)}%`;

              return (
                <Link
                  key={course.id}
                  href={`/dashboard/courses/${course.id}`}
                >
                  <Card className="hover:border-primary/50 transition-colors cursor-pointer h-full">
                    <CardHeader>
                      <CardTitle className="text-lg">{course.name}</CardTitle>
                      <CardDescription>
                        {course.code && <span>{course.code} &middot; </span>}
                        {format(start, "MMM d")} &ndash;{" "}
                        {format(end, "MMM d, yyyy")}
                      </CardDescription>
                    </CardHeader>
                    <CardContent>
                      <div className="flex flex-wrap gap-2">
                        <Badge variant="secondary">
                          {assessmentCount} assessment
                          {assessmentCount !== 1 && "s"}
                        </Badge>
                        <Badge variant="outline">Target: {gradeLabel}</Badge>
                      </div>
                    </CardContent>
                  </Card>
                </Link>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}
