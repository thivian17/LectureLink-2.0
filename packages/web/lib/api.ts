import { createClient } from "@/lib/supabase/client";
import type {
  Course,
  Syllabus,
  Assessment,
  Lecture,
  LectureDetail,
  LectureStatus,
  Quiz,
  QuizQuestion,
  QuizSubmissionResult,
  QuizGenerationStatus,
  QuizAnswer,
  QuizDifficulty,
  SearchResponse,
  QAResponse,
} from "@/types/database";
import {
  ApiError,
  AuthError,
  RateLimitError,
  NotFoundError,
} from "@/lib/api-errors";

export { ApiError, AuthError, RateLimitError, NotFoundError } from "@/lib/api-errors";

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

// ---------------------------------------------------------------------------
// Auth helpers
// ---------------------------------------------------------------------------

async function getAuthHeaders(): Promise<HeadersInit> {
  const supabase = createClient();
  const {
    data: { session },
  } = await supabase.auth.getSession();
  if (!session?.access_token) throw new AuthError("Not authenticated");
  return { Authorization: `Bearer ${session.access_token}` };
}

// ---------------------------------------------------------------------------
// Centralized fetch with auth, retry-on-401, and error classification
// ---------------------------------------------------------------------------

async function handleErrorResponse(resp: Response): Promise<never> {
  if (resp.status === 429) {
    const retryAfter = parseInt(resp.headers.get("Retry-After") ?? "3600", 10);
    const body = await resp.json().catch(() => ({ detail: "Rate limit exceeded" }));
    throw new RateLimitError(body.detail ?? "Rate limit exceeded", retryAfter);
  }

  if (resp.status === 404) {
    const body = await resp.json().catch(() => ({ detail: "Not found" }));
    throw new NotFoundError(body.detail ?? "Resource not found");
  }

  const body = await resp.json().catch(() => ({ detail: resp.statusText }));
  throw new ApiError(
    body.detail ?? `Request failed (${resp.status})`,
    resp.status,
    body.detail,
  );
}

async function fetchWithAuth(
  url: string,
  options: RequestInit = {},
): Promise<Response> {
  const headers = await getAuthHeaders();
  const resp = await fetch(url, {
    ...options,
    headers: { ...headers, ...(options.headers as Record<string, string>) },
  });

  if (resp.ok) return resp;

  // 401: try refreshing the session once
  if (resp.status === 401) {
    const supabase = createClient();
    const { error: refreshError } = await supabase.auth.refreshSession();
    if (refreshError) {
      throw new AuthError();
    }
    const freshHeaders = await getAuthHeaders();
    const retryResp = await fetch(url, {
      ...options,
      headers: { ...freshHeaders, ...(options.headers as Record<string, string>) },
    });
    if (retryResp.ok) return retryResp;
    if (retryResp.status === 401) {
      throw new AuthError();
    }
    return handleErrorResponse(retryResp);
  }

  return handleErrorResponse(resp);
}

// ---------------------------------------------------------------------------
// Courses (Supabase direct)
// ---------------------------------------------------------------------------

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
  const {
    data: { user },
  } = await supabase.auth.getUser();
  if (!user) throw new AuthError("Not authenticated");
  const { data: course, error } = await supabase
    .from("courses")
    .insert({ ...data, user_id: user.id })
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
  const formData = new FormData();
  formData.append("course_id", courseId);
  formData.append("file", file);

  const resp = await fetchWithAuth(`${API_BASE}/api/syllabi/upload`, {
    method: "POST",
    body: formData,
  });
  return resp.json();
}

export async function getSyllabusStatus(
  syllabusId: string,
): Promise<SyllabusProcessingStatus> {
  const resp = await fetchWithAuth(
    `${API_BASE}/api/syllabi/${syllabusId}/status`,
  );
  return resp.json();
}

export async function getSyllabus(syllabusId: string): Promise<Syllabus> {
  const resp = await fetchWithAuth(`${API_BASE}/api/syllabi/${syllabusId}`);
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
    const course = row.courses as unknown as {
      name: string;
      code: string | null;
    };
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

// ---------------------------------------------------------------------------
// Lectures
// ---------------------------------------------------------------------------

export async function getLectures(courseId: string): Promise<Lecture[]> {
  const resp = await fetchWithAuth(
    `${API_BASE}/api/courses/${courseId}/lectures`,
  );
  return resp.json();
}

export async function getLecture(lectureId: string): Promise<Lecture> {
  const resp = await fetchWithAuth(`${API_BASE}/api/lectures/${lectureId}`);
  return resp.json();
}

export async function getLectureDetail(
  lectureId: string,
): Promise<LectureDetail> {
  const resp = await fetchWithAuth(
    `${API_BASE}/api/lectures/${lectureId}`,
  );
  return resp.json();
}

export async function getLectureStatus(
  lectureId: string,
): Promise<LectureStatus> {
  const resp = await fetchWithAuth(
    `${API_BASE}/api/lectures/${lectureId}/status`,
  );
  return resp.json();
}

export async function uploadLecture(
  courseId: string,
  data: FormData,
): Promise<{ lecture_id: string; status: string }> {
  data.append("course_id", courseId);
  const resp = await fetchWithAuth(`${API_BASE}/api/lectures/upload`, {
    method: "POST",
    body: data,
  });
  return resp.json();
}

export async function retryLecture(lectureId: string): Promise<void> {
  await fetchWithAuth(`${API_BASE}/api/lectures/${lectureId}/retry`, {
    method: "POST",
  });
}

// ---------------------------------------------------------------------------
// Search
// ---------------------------------------------------------------------------

export async function searchLectures(
  courseId: string,
  query: string,
  lectureId?: string | null,
): Promise<SearchResponse> {
  const params = new URLSearchParams({ course_id: courseId, q: query });
  if (lectureId) params.set("lecture_id", lectureId);
  const resp = await fetchWithAuth(`${API_BASE}/api/search?${params}`);
  return resp.json();
}

// ---------------------------------------------------------------------------
// Q&A
// ---------------------------------------------------------------------------

export async function askQuestion(
  courseId: string,
  question: string,
  lectureIds?: string[],
): Promise<QAResponse> {
  const resp = await fetchWithAuth(`${API_BASE}/api/qa`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      course_id: courseId,
      question,
      lecture_ids: lectureIds ?? [],
    }),
  });
  return resp.json();
}

// ---------------------------------------------------------------------------
// Quizzes
// ---------------------------------------------------------------------------

export async function getQuizzes(courseId: string): Promise<Quiz[]> {
  const resp = await fetchWithAuth(
    `${API_BASE}/api/courses/${courseId}/quizzes`,
  );
  return resp.json();
}

export async function getQuiz(quizId: string): Promise<Quiz> {
  const resp = await fetchWithAuth(`${API_BASE}/api/quizzes/${quizId}`);
  return resp.json();
}

export async function getQuizQuestions(
  quizId: string,
): Promise<QuizQuestion[]> {
  const resp = await fetchWithAuth(
    `${API_BASE}/api/quizzes/${quizId}/questions`,
  );
  return resp.json();
}

export async function generateQuiz(
  courseId: string,
  options: {
    target_assessment_id?: string | null;
    lecture_ids?: string[] | null;
    question_count: number;
    difficulty: QuizDifficulty;
  },
): Promise<{ quiz_id: string; status: "generating" }> {
  const resp = await fetchWithAuth(`${API_BASE}/api/quizzes/generate`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ course_id: courseId, ...options }),
  });
  return resp.json();
}

export async function getQuizGenerationStatus(
  quizId: string,
): Promise<QuizGenerationStatus> {
  const resp = await fetchWithAuth(
    `${API_BASE}/api/quizzes/${quizId}/status`,
  );
  return resp.json();
}

export async function submitQuiz(
  quizId: string,
  answers: QuizAnswer[],
): Promise<QuizSubmissionResult> {
  const resp = await fetchWithAuth(`${API_BASE}/api/quizzes/${quizId}/submit`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ answers }),
  });
  return resp.json();
}
