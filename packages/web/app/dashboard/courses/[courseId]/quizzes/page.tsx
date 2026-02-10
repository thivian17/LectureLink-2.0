import { notFound } from "next/navigation";
import { createClient } from "@/lib/supabase/server";
import { QuizList } from "@/components/quiz/QuizList";
import type { Course } from "@/types/database";

export default async function QuizzesPage({
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

  return <QuizList courseId={courseId} courseName={typedCourse.name} />;
}
