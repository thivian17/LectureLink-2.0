import { notFound } from "next/navigation";
import { createClient } from "@/lib/supabase/server";
import { LectureList } from "@/components/lectures/lecture-list";
import type { Course } from "@/types/database";

export default async function LecturesPage({
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

  const typedCourse = course as Course;

  return <LectureList courseId={courseId} courseName={typedCourse.name} />;
}
