import { notFound } from "next/navigation";
import { createClient } from "@/lib/supabase/server";
import { QuizResultsClient } from "@/components/quiz/QuizResultsClient";

export default async function QuizResultsPage({
  params,
}: {
  params: Promise<{ courseId: string; quizId: string }>;
}) {
  const { courseId, quizId } = await params;
  const supabase = await createClient();

  const { data: course, error } = await supabase
    .from("courses")
    .select("*")
    .eq("id", courseId)
    .single();

  if (error || !course) {
    notFound();
  }

  return <QuizResultsClient courseId={courseId} quizId={quizId} />;
}
