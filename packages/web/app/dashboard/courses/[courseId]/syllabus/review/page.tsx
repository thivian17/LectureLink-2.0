import { notFound, redirect } from "next/navigation";
import { createClient } from "@/lib/supabase/server";
import { SyllabusReviewClient } from "@/components/syllabus-review/syllabus-review-client";
import type { Syllabus, Assessment } from "@/types/database";
import type { SyllabusExtraction } from "@/types/extraction";

export default async function SyllabusReviewPage({
  params,
}: {
  params: Promise<{ courseId: string }>;
}) {
  const { courseId } = await params;
  const supabase = await createClient();

  // Fetch the most recent syllabus for this course
  const { data: syllabus, error: syllabusError } = await supabase
    .from("syllabi")
    .select("*")
    .eq("course_id", courseId)
    .order("created_at", { ascending: false })
    .limit(1)
    .maybeSingle();

  if (syllabusError || !syllabus) {
    notFound();
  }

  const typedSyllabus = syllabus as Syllabus;

  // If no raw_extraction or already reviewed, redirect to course page
  if (!typedSyllabus.raw_extraction || typedSyllabus.reviewed_at) {
    redirect(`/dashboard/courses/${courseId}`);
  }

  // Fetch assessments for this course
  const { data: assessments } = await supabase
    .from("assessments")
    .select("*")
    .eq("course_id", courseId)
    .order("due_date", { ascending: true, nullsFirst: false });

  const extraction = typedSyllabus.raw_extraction as unknown as SyllabusExtraction;

  return (
    <SyllabusReviewClient
      courseId={courseId}
      syllabus={typedSyllabus}
      extraction={extraction}
      assessments={(assessments ?? []) as Assessment[]}
    />
  );
}
