import { notFound } from "next/navigation";
import { createClient } from "@/lib/supabase/server";
import { MaterialUploadForm } from "@/components/materials/material-upload-form";
import type { Course } from "@/types/database";

export default async function NewMaterialPage({
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

  return (
    <MaterialUploadForm courseId={courseId} courseName={typedCourse.name} />
  );
}
