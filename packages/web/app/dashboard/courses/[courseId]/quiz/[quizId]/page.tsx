import { notFound } from "next/navigation";
import { createClient } from "@/lib/supabase/server";
import { QuizTakingClient } from "@/components/quiz/QuizTakingClient";

export default async function QuizTakingPage({
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

  return <QuizTakingClient courseId={courseId} quizId={quizId} />;
}
