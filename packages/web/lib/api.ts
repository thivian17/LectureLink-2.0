import { createClient } from "@/lib/supabase/client";
import type { Course, Syllabus, Assessment } from "@/types/database";

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

async function getAuthHeaders(): Promise<HeadersInit> {
  const supabase = createClient();
  const {
    data: { session },
  } = await supabase.auth.getSession();
  if (!session?.access_token) throw new Error("Not authenticated");
  return { Authorization: `Bearer ${session.access_token}` };
}

export type SyllabusProcessingStatus = {
  syllabus_id: string;
  status: "uploading" | "processing" | "complete" | "error";
  needs_review: boolean;
  error_message?: string;
};

export interface CourseInput {
  name: string;
  code?: string | null;
  semester_start: string;
  semester_end: string;
  meeting_days?: string[];
  meeting_time?: string | null;
  holidays?: { name: string; start_date: string; end_date: string }[];
  target_grade?: number;
}

export async function createCourse(data: CourseInput): Promise<Course> {
  const supabase = createClient();
  const { data: course, error } = await supabase
    .from("courses")
    .insert(data)
    .select()
    .single();
  if (error) throw error;
  return course as Course;
}

export async function getCourses(): Promise<Course[]> {
  const supabase = createClient();
  const { data, error } = await supabase
    .from("courses")
    .select("*")
    .order("created_at", { ascending: false });
  if (error) throw error;
  return (data ?? []) as Course[];
}

export async function getCourse(id: string): Promise<Course> {
  const supabase = createClient();
  const { data, error } = await supabase
    .from("courses")
    .select("*")
    .eq("id", id)
    .single();
  if (error) throw error;
  return data as Course;
}

export async function updateCourse(
  id: string,
  data: Partial<CourseInput>,
): Promise<Course> {
  const supabase = createClient();
  const { data: course, error } = await supabase
    .from("courses")
    .update(data)
    .eq("id", id)
    .select()
    .single();
  if (error) throw error;
  return course as Course;
}

export async function deleteCourse(id: string): Promise<void> {
  const supabase = createClient();
  const { error } = await supabase.from("courses").delete().eq("id", id);
  if (error) throw error;
}

// ---------------------------------------------------------------------------
// Syllabi
// ---------------------------------------------------------------------------

export async function getCourseSyllabus(
  courseId: string,
): Promise<Syllabus | null> {
  const supabase = createClient();
  const { data, error } = await supabase
    .from("syllabi")
    .select("*")
    .eq("course_id", courseId)
    .order("created_at", { ascending: false })
    .limit(1)
    .maybeSingle();
  if (error) throw error;
  return data as Syllabus | null;
}

export async function uploadSyllabus(
  courseId: string,
  file: File,
): Promise<{ syllabus_id: string; status: "processing" }> {
  const headers = await getAuthHeaders();
  const formData = new FormData();
  formData.append("course_id", courseId);
  formData.append("file", file);

  const resp = await fetch(`${API_BASE}/api/syllabi/upload`, {
    method: "POST",
    headers,
    body: formData,
  });
  if (!resp.ok) {
    const detail = await resp.json().catch(() => ({ detail: resp.statusText }));
    throw new Error(detail.detail ?? "Upload failed");
  }
  return resp.json();
}

export async function getSyllabusStatus(
  syllabusId: string,
): Promise<SyllabusProcessingStatus> {
  const headers = await getAuthHeaders();
  const resp = await fetch(`${API_BASE}/api/syllabi/${syllabusId}/status`, {
    headers,
  });
  if (!resp.ok) {
    throw new Error(`Failed to get syllabus status: ${resp.statusText}`);
  }
  return resp.json();
}

export async function getSyllabus(syllabusId: string): Promise<Syllabus> {
  const headers = await getAuthHeaders();
  const resp = await fetch(`${API_BASE}/api/syllabi/${syllabusId}`, {
    headers,
  });
  if (!resp.ok) {
    throw new Error(`Failed to get syllabus: ${resp.statusText}`);
  }
  return resp.json();
}

// ---------------------------------------------------------------------------
// Syllabus Review
// ---------------------------------------------------------------------------

export interface ReviewSyllabusInput {
  grade_breakdown: {
    component: string;
    weight: number;
    drop_policy?: string | null;
  }[];
  course_info: {
    instructor_name?: string | null;
    instructor_email?: string | null;
    office_hours?: string | null;
  };
}

export async function reviewSyllabus(
  syllabusId: string,
  data: ReviewSyllabusInput,
): Promise<Syllabus> {
  const supabase = createClient();
  const { data: syllabus, error } = await supabase
    .from("syllabi")
    .update({
      grade_breakdown: data.grade_breakdown,
      needs_review: false,
      reviewed_at: new Date().toISOString(),
    })
    .eq("id", syllabusId)
    .select()
    .single();
  if (error) throw error;
  return syllabus as Syllabus;
}

// ---------------------------------------------------------------------------
// Assessments
// ---------------------------------------------------------------------------

export interface UpdateAssessmentInput {
  title?: string;
  type?: string;
  due_date?: string | null;
  due_date_raw?: string | null;
  is_date_ambiguous?: boolean;
  weight_percent?: number | null;
  topics?: string[] | null;
}

export interface AssessmentWithCourse extends Assessment {
  course_name: string;
  course_code: string | null;
}

/** Fetch all assessments (with due dates) across all of the user's courses. */
export async function getAllAssessments(): Promise<AssessmentWithCourse[]> {
  const supabase = createClient();
  const { data, error } = await supabase
    .from("assessments")
    .select("*, courses!inner(name, code)")
    .not("due_date", "is", null)
    .order("due_date", { ascending: true });
  if (error) throw error;
  return (data ?? []).map((row) => {
    const course = row.courses as unknown as { name: string; code: string | null };
    return {
      ...row,
      course_name: course.name,
      course_code: course.code,
    } as AssessmentWithCourse;
  });
}

export async function getAssessments(courseId: string): Promise<Assessment[]> {
  const supabase = createClient();
  const { data, error } = await supabase
    .from("assessments")
    .select("*")
    .eq("course_id", courseId)
    .order("due_date", { ascending: true, nullsFirst: false });
  if (error) throw error;
  return (data ?? []) as Assessment[];
}

export async function updateAssessment(
  assessmentId: string,
  data: UpdateAssessmentInput,
): Promise<Assessment> {
  const supabase = createClient();
  const { data: assessment, error } = await supabase
    .from("assessments")
    .update(data)
    .eq("id", assessmentId)
    .select()
    .single();
  if (error) throw error;
  return assessment as Assessment;
}

export async function bulkUpdateAssessments(
  updates: { id: string; data: UpdateAssessmentInput }[],
): Promise<void> {
  const supabase = createClient();
  const results = await Promise.all(
    updates.map(({ id, data }) =>
      supabase.from("assessments").update(data).eq("id", id),
    ),
  );
  const firstError = results.find((r) => r.error);
  if (firstError?.error) throw firstError.error;
}
