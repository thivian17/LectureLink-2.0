import { notFound, redirect } from "next/navigation";
import { createClient } from "@/lib/supabase/server";
import { CourseDetail } from "@/components/course-detail";
import type { Course, Syllabus } from "@/types/database";

export default async function CourseDetailPage({
  params,
}: {
  params: Promise<{ courseId: string }>;
}) {
  const { courseId } = await params;
  const supabase = await createClient();

  const { data: course, error } = await supabase
    .from("courses")
    .select("*")
    .eq("id", courseId)
    .single();

  if (error || !course) {
    notFound();
  }

  // Redirect to onboarding if not completed
  if (!course.onboarding_completed_at) {
    redirect(`/dashboard/courses/${courseId}/onboarding`);
  }

  const { count: assessmentCount } = await supabase
    .from("assessments")
    .select("*", { count: "exact", head: true })
    .eq("course_id", courseId);

  const { data: syllabus } = await supabase
    .from("syllabi")
    .select("*")
    .eq("course_id", courseId)
    .order("created_at", { ascending: false })
    .limit(1)
    .maybeSingle();

  return (
    <CourseDetail
      course={course as Course}
      assessmentCount={assessmentCount ?? 0}
      syllabus={(syllabus as Syllabus) ?? null}
    />
  );
}
