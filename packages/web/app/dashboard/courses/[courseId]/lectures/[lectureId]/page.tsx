import { notFound } from "next/navigation";
import { createClient } from "@/lib/supabase/server";
import { LectureDetailClient } from "@/components/lectures/lecture-detail-client";
import { USE_MOCKS } from "@/lib/mock-api";

export default async function LectureDetailPage({
  params,
}: {
  params: Promise<{ courseId: string; lectureId: string }>;
}) {
  const { courseId, lectureId } = await params;

  // In mock mode, skip DB validation
  if (!USE_MOCKS) {
    const supabase = await createClient();
    const { data: lecture, error } = await supabase
      .from("lectures")
      .select("id, processing_status")
      .eq("id", lectureId)
      .single();

    if (error || !lecture || lecture.processing_status !== "completed") {
      notFound();
    }
  }

  return <LectureDetailClient courseId={courseId} lectureId={lectureId} />;
}
