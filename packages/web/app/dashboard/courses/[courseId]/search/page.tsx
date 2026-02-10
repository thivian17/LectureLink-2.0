import { notFound } from "next/navigation";
import { createClient } from "@/lib/supabase/server";
import { SearchPageClient } from "@/components/search/search-page-client";

export default async function SearchPage({
  params,
}: {
  params: Promise<{ courseId: string }>;
}) {
  const { courseId } = await params;
  const supabase = await createClient();
  const { data: course, error } = await supabase
    .from("courses")
    .select("id")
    .eq("id", courseId)
    .single();
  if (error || !course) notFound();
  return <SearchPageClient courseId={courseId} />;
}
