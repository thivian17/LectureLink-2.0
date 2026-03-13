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
  HintResponse,
  SearchResponse,
  QAResponse,
  PerformanceData,
  CoachResponse,
  StudyActionsResponse,
  OnboardingPath,
  OnboardingStatus,
  SuggestedPath,
  PersonalizedMessage,
  LectureChecklistItem,
  SemesterProgress,
  AssessmentReadiness,
  TutorMode,
  TutorSession,
  TutorSessionEntry,
  TutorQuestion,
  GradingResult,
  TutorChatResponse,
  DiagnosticResult,
  SessionSummary,
  ContentBlock,
  GamificationState,
  GamificationReadiness,
  CourseReadinessSummary,
  GradeProjection,
  BadgeInfo,
  WeeklyProgress,
  LearnStartSessionResponse,
  ConceptBrief,
  QuizAnswerResult,
  PowerQuizQuestion,
  LearnSessionComplete,
  Invite,
  MaterialType,
  CourseMaterial,
  CourseMaterialDetail,
  MaterialStatus,
  MaterialListResponse,
  DashboardBriefingResponse,
  DashboardChatResponse,
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
  const signal = options.signal ?? AbortSignal.timeout(15_000);
  const resp = await fetch(url, {
    ...options,
    signal,
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
      signal,
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
  meeting_days: string[];
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

export async function deleteAssessment(assessmentId: string): Promise<void> {
  await fetchWithAuth(`${API_BASE}/api/assessments/${assessmentId}`, {
    method: "DELETE",
  });
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
  const body: Record<string, unknown> = { course_id: courseId, query };
  if (lectureId) body.lecture_ids = [lectureId];
  const resp = await fetchWithAuth(`${API_BASE}/api/search`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
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
    include_coding?: boolean;
    coding_ratio?: number;
    coding_language?: string;
    coding_only?: boolean;
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

// ---------------------------------------------------------------------------
// Quiz Hints (Coding Questions)
// ---------------------------------------------------------------------------

export async function getHint(
  quizId: string,
  questionId: string,
  hintIndex: number = 0,
): Promise<HintResponse> {
  const resp = await fetchWithAuth(
    `${API_BASE}/api/quizzes/${quizId}/questions/${questionId}/hint`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ hint_index: hintIndex }),
    },
  );
  return resp.json();
}

// ---------------------------------------------------------------------------
// Performance Analytics (Phase 3)
// ---------------------------------------------------------------------------

export async function getCoursePerformance(
  courseId: string,
): Promise<PerformanceData> {
  const resp = await fetchWithAuth(
    `${API_BASE}/api/courses/${courseId}/performance`,
  );
  return resp.json();
}

// ---------------------------------------------------------------------------
// Study Coach (Phase 3)
// ---------------------------------------------------------------------------

export async function chatWithCoach(
  courseId: string,
  message: string,
  conversationHistory?: Array<{ role: string; content: string }>,
): Promise<CoachResponse> {
  const resp = await fetchWithAuth(
    `${API_BASE}/api/courses/${courseId}/study-coach/chat`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        message,
        conversation_history: conversationHistory,
      }),
    },
  );
  return resp.json();
}

// ---------------------------------------------------------------------------
// Study Coach — Streaming
// ---------------------------------------------------------------------------

/**
 * Stream study coach chat. Returns an async generator of text chunks.
 * Usage: for await (const chunk of streamCoachChat(courseId, message)) { ... }
 */
export async function* streamCoachChat(
  courseId: string,
  message: string,
  conversationHistory?: Array<{ role: string; content: string }>,
): AsyncGenerator<string> {
  const headers = await getAuthHeaders();
  const response = await fetch(
    `${API_BASE}/api/courses/${courseId}/study-coach/chat/stream`,
    {
      method: "POST",
      headers: {
        ...headers,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        message,
        conversation_history: conversationHistory,
      }),
    },
  );

  if (!response.ok) throw new ApiError("Stream failed", response.status);

  const reader = response.body!.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split("\n\n");
    buffer = lines.pop() || "";

    for (const line of lines) {
      if (line.startsWith("data: ")) {
        try {
          const parsed = JSON.parse(line.slice(6));
          if (parsed.type === "chunk") yield parsed.content;
          if (parsed.type === "done") return;
        } catch {
          /* ignore malformed chunks */
        }
      }
    }
  }
}

/**
 * Stream tutor chat. Returns an async generator of text chunks.
 */
export async function* streamTutorChat(
  sessionId: string,
  message: string,
): AsyncGenerator<string> {
  const headers = await getAuthHeaders();
  const response = await fetch(
    `${API_BASE}/api/tutor/session/${sessionId}/chat/stream`,
    {
      method: "POST",
      headers: {
        ...headers,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ message }),
    },
  );

  if (!response.ok) throw new ApiError("Stream failed", response.status);

  const reader = response.body!.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split("\n\n");
    buffer = lines.pop() || "";

    for (const line of lines) {
      if (line.startsWith("data: ")) {
        try {
          const parsed = JSON.parse(line.slice(6));
          if (parsed.type === "chunk") yield parsed.content;
          if (parsed.type === "done") return;
        } catch {
          /* ignore malformed chunks */
        }
      }
    }
  }
}

// ---------------------------------------------------------------------------
// Study Actions (Study Hub)
// ---------------------------------------------------------------------------

export async function getStudyActions(): Promise<StudyActionsResponse> {
  const resp = await fetchWithAuth(`${API_BASE}/api/study-actions`);
  return resp.json();
}

export async function getStudyActionsEnhanced(): Promise<StudyActionsResponse> {
  const resp = await fetchWithAuth(`${API_BASE}/api/study-actions/enhanced`);
  return resp.json();
}

export async function getCourseStudyActions(
  courseId: string,
): Promise<StudyActionsResponse> {
  const resp = await fetchWithAuth(
    `${API_BASE}/api/courses/${courseId}/study-actions`,
  );
  return resp.json();
}

// ---------------------------------------------------------------------------
// Onboarding
// ---------------------------------------------------------------------------

export async function startOnboarding(
  courseId: string,
): Promise<{ status: string; step: string }> {
  const resp = await fetchWithAuth(
    `${API_BASE}/api/courses/${courseId}/onboarding/start`,
    { method: "POST" },
  );
  return resp.json();
}

export async function getOnboardingStatus(
  courseId: string,
): Promise<OnboardingStatus> {
  const resp = await fetchWithAuth(
    `${API_BASE}/api/courses/${courseId}/onboarding/status`,
  );
  return resp.json();
}

export async function updateOnboardingStep(
  courseId: string,
  step: string,
): Promise<void> {
  await fetchWithAuth(
    `${API_BASE}/api/courses/${courseId}/onboarding/step`,
    {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ step }),
    },
  );
}

export async function getSuggestedPath(
  courseId: string,
): Promise<SuggestedPath> {
  const resp = await fetchWithAuth(
    `${API_BASE}/api/courses/${courseId}/onboarding/suggest-path`,
  );
  return resp.json();
}

export async function setOnboardingPath(
  courseId: string,
  path: OnboardingPath,
): Promise<{ path: string; mode: string; suggested_path: string }> {
  const resp = await fetchWithAuth(
    `${API_BASE}/api/courses/${courseId}/onboarding/set-path`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ path }),
    },
  );
  return resp.json();
}

export async function getPersonalizedMessage(
  courseId: string,
  forceRegenerate?: boolean,
): Promise<PersonalizedMessage> {
  const resp = await fetchWithAuth(
    `${API_BASE}/api/courses/${courseId}/onboarding/personalized-message`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ force_regenerate: forceRegenerate ?? false }),
    },
  );
  return resp.json();
}

export async function getLectureChecklist(
  courseId: string,
): Promise<LectureChecklistItem[]> {
  const resp = await fetchWithAuth(
    `${API_BASE}/api/courses/${courseId}/onboarding/lecture-checklist`,
  );
  return resp.json();
}

export async function getSemesterProgress(
  courseId: string,
): Promise<SemesterProgress> {
  const resp = await fetchWithAuth(
    `${API_BASE}/api/courses/${courseId}/semester-progress`,
  );
  return resp.json();
}

export async function completeOnboarding(
  courseId: string,
): Promise<{ completed_at: string; mastery_scores_seeded: number }> {
  const resp = await fetchWithAuth(
    `${API_BASE}/api/courses/${courseId}/onboarding/complete`,
    { method: "PUT" },
  );
  return resp.json();
}

export async function saveAssessmentResult(
  assessmentId: string,
  scorePercent: number,
): Promise<void> {
  await fetchWithAuth(
    `${API_BASE}/api/assessments/${assessmentId}/result`,
    {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ score_percent: scorePercent }),
    },
  );
}

// ---------------------------------------------------------------------------
// Study Tutor
// ---------------------------------------------------------------------------

export async function getTutorEntry(
  courseId: string,
): Promise<TutorSessionEntry> {
  const resp = await fetchWithAuth(
    `${API_BASE}/api/tutor/${courseId}/entry`,
  );
  return resp.json();
}

export async function startTutorSession(
  courseId: string,
  body: {
    mode: TutorMode;
    custom_topic?: string;
    target_assessment_id?: string;
    concept_ids?: string[];
  },
): Promise<TutorSession> {
  const resp = await fetchWithAuth(
    `${API_BASE}/api/tutor/${courseId}/session/start`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    },
  );
  return resp.json();
}

export async function getActiveTutorSession(
  courseId: string,
): Promise<TutorSession | null> {
  const resp = await fetchWithAuth(
    `${API_BASE}/api/tutor/${courseId}/session/active`,
  );
  const data = await resp.json();
  return data ?? null;
}

export async function submitTutorAnswer(
  sessionId: string,
  body: {
    question_id: string;
    student_answer: string;
    time_spent_seconds: number;
  },
): Promise<GradingResult> {
  const resp = await fetchWithAuth(
    `${API_BASE}/api/tutor/session/${sessionId}/answer`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    },
  );
  return resp.json();
}

export async function pauseTutorSession(
  sessionId: string,
): Promise<void> {
  await fetchWithAuth(
    `${API_BASE}/api/tutor/session/${sessionId}/pause`,
    { method: "PUT" },
  );
}

export async function resumeTutorSession(
  sessionId: string,
): Promise<TutorSession> {
  const resp = await fetchWithAuth(
    `${API_BASE}/api/tutor/session/${sessionId}/resume`,
    { method: "POST" },
  );
  return resp.json();
}

export async function completeTutorSession(
  sessionId: string,
): Promise<SessionSummary> {
  const resp = await fetchWithAuth(
    `${API_BASE}/api/tutor/session/${sessionId}/complete`,
    { method: "PUT" },
  );
  return resp.json();
}

export async function sendTutorChat(
  sessionId: string,
  message: string,
): Promise<TutorChatResponse> {
  const resp = await fetchWithAuth(
    `${API_BASE}/api/tutor/session/${sessionId}/chat`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message }),
    },
  );
  return resp.json();
}

export async function startDiagnostic(
  sessionId: string,
): Promise<{ questions: TutorQuestion[] }> {
  const resp = await fetchWithAuth(
    `${API_BASE}/api/tutor/session/${sessionId}/diagnostic`,
    { method: "POST" },
  );
  return resp.json();
}

export async function submitDiagnostic(
  sessionId: string,
  answers: {
    question_id: string;
    question: TutorQuestion;
    student_answer: string;
    time_spent_seconds: number;
  }[],
): Promise<DiagnosticResult> {
  const resp = await fetchWithAuth(
    `${API_BASE}/api/tutor/session/${sessionId}/diagnostic/submit`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ answers }),
    },
  );
  return resp.json();
}

export async function submitGradingFeedback(
  sessionId: string,
  body: {
    event_id: string;
    feedback_type: "accurate" | "inaccurate";
    feedback_text?: string;
  },
): Promise<void> {
  await fetchWithAuth(
    `${API_BASE}/api/tutor/session/${sessionId}/grading-feedback`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    },
  );
}

export async function getTutorHistory(
  courseId: string,
): Promise<TutorSession[]> {
  const resp = await fetchWithAuth(
    `${API_BASE}/api/tutor/${courseId}/history`,
  );
  return resp.json();
}

export async function getTutorSessionSummary(
  sessionId: string,
): Promise<SessionSummary> {
  const resp = await fetchWithAuth(
    `${API_BASE}/api/tutor/session/${sessionId}/summary`,
  );
  return resp.json();
}

export async function fetchNextBlock(
  sessionId: string,
): Promise<ContentBlock & { concept_index: number; step_index: number }> {
  const resp = await fetchWithAuth(
    `${API_BASE}/api/tutor/session/${sessionId}/next-block`,
    { method: "POST" },
  );
  return resp.json();
}

export async function getAssessmentReadiness(
  courseId: string,
  assessmentId: string,
): Promise<AssessmentReadiness> {
  const resp = await fetchWithAuth(
    `${API_BASE}/api/tutor/${courseId}/assessment/${assessmentId}/readiness`,
  );
  return resp.json();
}

// ---------------------------------------------------------------------------
// Gamification (Track A backend)
// ---------------------------------------------------------------------------

export async function getGamificationState(): Promise<GamificationState> {
  const resp = await fetchWithAuth(`${API_BASE}/api/gamification/state`);
  return resp.json();
}

export async function getGamificationReadiness(
  courseId?: string,
): Promise<GamificationReadiness[]> {
  const url = courseId
    ? `${API_BASE}/api/gamification/readiness?course_id=${courseId}`
    : `${API_BASE}/api/gamification/readiness`;
  const resp = await fetchWithAuth(url);
  return resp.json();
}

export async function getCourseReadiness(
  courseId: string,
): Promise<CourseReadinessSummary> {
  const resp = await fetchWithAuth(
    `${API_BASE}/api/gamification/courses/${courseId}/readiness`,
  );
  return resp.json();
}

export async function getGradeProjection(
  courseId: string,
): Promise<GradeProjection> {
  const resp = await fetchWithAuth(
    `${API_BASE}/api/gamification/courses/${courseId}/grade-projection`,
  );
  return resp.json();
}

export async function getUserBadges(): Promise<{
  earned: BadgeInfo[];
  available: BadgeInfo[];
}> {
  const resp = await fetchWithAuth(`${API_BASE}/api/gamification/badges`);
  return resp.json();
}

export async function useStreakFreeze(): Promise<{
  success: boolean;
  freezes_remaining: number;
}> {
  const resp = await fetchWithAuth(
    `${API_BASE}/api/gamification/streak/freeze`,
    { method: "POST" },
  );
  return resp.json();
}

export async function getWeeklyProgress(): Promise<WeeklyProgress> {
  const resp = await fetchWithAuth(
    `${API_BASE}/api/gamification/weekly-progress`,
  );
  return resp.json();
}

// ---------------------------------------------------------------------------
// Learn Mode (Track B backend)
// ---------------------------------------------------------------------------

export async function startLearnSession(
  courseId: string,
  timeBudget: number,
): Promise<LearnStartSessionResponse> {
  const resp = await fetchWithAuth(
    `${API_BASE}/api/learn/${courseId}/session/start`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ time_budget_minutes: timeBudget }),
      signal: AbortSignal.timeout(60_000),
    },
  );
  return resp.json();
}

export async function submitFlashReview(
  sessionId: string,
  cardId: string,
  answerIndex: number,
  timeMs: number,
): Promise<{ correct: boolean; correct_answer: string; xp_earned: number }> {
  const resp = await fetchWithAuth(
    `${API_BASE}/api/learn/session/${sessionId}/flash-review`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        card_id: cardId,
        answer_index: answerIndex,
        time_ms: timeMs,
      }),
    },
  );
  return resp.json();
}

export async function getConceptBrief(
  sessionId: string,
  conceptIndex: number,
): Promise<ConceptBrief> {
  const resp = await fetchWithAuth(
    `${API_BASE}/api/learn/session/${sessionId}/concept/${conceptIndex}`,
    { signal: AbortSignal.timeout(60_000) },
  );
  return resp.json();
}

export async function submitGutCheck(
  sessionId: string,
  conceptId: string,
  answerIndex: number,
): Promise<{
  correct: boolean;
  explanation: string;
  clarification: string | null;
  xp_earned: number;
}> {
  const resp = await fetchWithAuth(
    `${API_BASE}/api/learn/session/${sessionId}/gut-check`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ concept_id: conceptId, answer_index: answerIndex }),
    },
  );
  return resp.json();
}

export async function getPowerQuiz(
  sessionId: string,
): Promise<{ quiz_id: string; questions: PowerQuizQuestion[] }> {
  const resp = await fetchWithAuth(
    `${API_BASE}/api/learn/session/${sessionId}/quiz`,
  );
  return resp.json();
}

export async function submitLearnQuizAnswer(
  sessionId: string,
  questionId: string,
  answerIndex: number,
  timeMs: number,
): Promise<QuizAnswerResult> {
  const resp = await fetchWithAuth(
    `${API_BASE}/api/learn/session/${sessionId}/quiz/answer`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        question_id: questionId,
        answer_index: answerIndex,
        time_ms: timeMs,
      }),
    },
  );
  return resp.json();
}

export async function completeLearnSession(
  sessionId: string,
): Promise<LearnSessionComplete> {
  const resp = await fetchWithAuth(
    `${API_BASE}/api/learn/session/${sessionId}/complete`,
    { method: "PUT" },
  );
  return resp.json();
}

export async function abandonLearnSession(
  sessionId: string,
): Promise<void> {
  await fetchWithAuth(
    `${API_BASE}/api/learn/session/${sessionId}/abandon`,
    { method: "PUT" },
  );
}

export async function getLearnSessionState(
  sessionId: string,
): Promise<LearnStartSessionResponse> {
  const resp = await fetchWithAuth(
    `${API_BASE}/api/learn/session/${sessionId}`,
  );
  return resp.json();
}

// ---------------------------------------------------------------------------
// Google Calendar Integration
// ---------------------------------------------------------------------------

export async function storeGoogleTokens(
  accessToken: string,
  refreshToken: string | null,
): Promise<void> {
  await fetchWithAuth(`${API_BASE}/api/google/tokens`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      access_token: accessToken,
      refresh_token: refreshToken,
    }),
  });
}

export async function getGoogleSyncStatus(): Promise<{
  connected: boolean;
  calendar_sync_enabled: boolean;
  has_refresh_token: boolean;
}> {
  const resp = await fetchWithAuth(`${API_BASE}/api/google/sync/status`);
  return resp.json();
}

export async function triggerCalendarSync(): Promise<{
  created: number;
  updated: number;
  deleted: number;
  errors: number;
}> {
  const resp = await fetchWithAuth(`${API_BASE}/api/google/sync`, {
    method: "POST",
    signal: AbortSignal.timeout(30_000),
  });
  return resp.json();
}

export async function toggleCalendarSync(enabled: boolean): Promise<void> {
  await fetchWithAuth(`${API_BASE}/api/google/sync/toggle`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ enabled }),
  });
}

export async function disconnectGoogle(): Promise<void> {
  await fetchWithAuth(`${API_BASE}/api/google/tokens`, {
    method: "DELETE",
  });
}

// ---------------------------------------------------------------------------
// Invites & Referrals
// ---------------------------------------------------------------------------

export async function createInvite(opts: {
  email?: string;
  max_uses?: number;
}): Promise<Invite> {
  const resp = await fetchWithAuth(`${API_BASE}/api/invites`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(opts),
  });
  return resp.json();
}

export async function listInvites(): Promise<Invite[]> {
  const resp = await fetchWithAuth(`${API_BASE}/api/invites`);
  return resp.json();
}

export async function validateInvite(
  code: string,
): Promise<{ valid: boolean }> {
  const resp = await fetchWithAuth(
    `${API_BASE}/api/invites/validate/${code}`,
  );
  return resp.json();
}

export async function createCourseShareToken(
  courseId: string,
): Promise<{ share_token: string; share_url: string }> {
  const resp = await fetchWithAuth(
    `${API_BASE}/api/invites/courses/${courseId}/share-token`,
    { method: "POST" },
  );
  return resp.json();
}

// ---------------------------------------------------------------------------
// Feedback
// ---------------------------------------------------------------------------

export interface FeedbackSubmission {
  type: "bug" | "feature" | "ux" | "praise";
  description: string;
  page_url: string;
  page_title?: string;
  screenshot_storage_path?: string;
  annotation_bounds?: { x: number; y: number; width: number; height: number };
  browser_info?: {
    user_agent: string;
    viewport_width: number;
    viewport_height: number;
    platform: string;
  };
  console_errors?: string[];
}

export interface FeedbackResponse {
  id: string;
  github_issue_url?: string;
  message: string;
}

export async function uploadFeedbackScreenshot(
  blob: Blob,
): Promise<{ storage_path: string }> {
  const formData = new FormData();
  formData.append("file", blob, "screenshot.png");
  // Do NOT set Content-Type header — let the browser set multipart boundary
  const resp = await fetchWithAuth(
    `${API_BASE}/api/feedback/upload-screenshot`,
    {
      method: "POST",
      body: formData,
    },
  );
  return resp.json();
}

export async function submitFeedback(
  data: FeedbackSubmission,
): Promise<FeedbackResponse> {
  const resp = await fetchWithAuth(`${API_BASE}/api/feedback`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
  return resp.json();
}

// ---------------------------------------------------------------------------
// Course Materials
// ---------------------------------------------------------------------------

export async function uploadMaterial(
  courseId: string,
  file: File,
  materialType: MaterialType,
  options?: {
    title?: string;
    linkedAssessmentId?: string;
    weekNumber?: number;
    relevantDate?: string;
  },
): Promise<CourseMaterial> {
  const formData = new FormData();
  formData.append("file", file);
  formData.append("material_type", materialType);
  if (options?.title) formData.append("title", options.title);
  if (options?.linkedAssessmentId)
    formData.append("linked_assessment_id", options.linkedAssessmentId);
  if (options?.weekNumber)
    formData.append("week_number", String(options.weekNumber));
  if (options?.relevantDate)
    formData.append("relevant_date", options.relevantDate);

  const resp = await fetchWithAuth(
    `${API_BASE}/api/courses/${courseId}/materials/upload`,
    {
      method: "POST",
      body: formData,
      // Do NOT set Content-Type — browser sets it with boundary for FormData
    },
  );
  return resp.json();
}

export async function listMaterials(
  courseId: string,
  materialType?: MaterialType,
): Promise<MaterialListResponse> {
  const params = new URLSearchParams();
  if (materialType) params.set("material_type", materialType);
  const qs = params.toString();
  const resp = await fetchWithAuth(
    `${API_BASE}/api/courses/${courseId}/materials${qs ? `?${qs}` : ""}`,
  );
  return resp.json();
}

export async function getMaterial(
  materialId: string,
): Promise<CourseMaterialDetail> {
  const resp = await fetchWithAuth(
    `${API_BASE}/api/materials/${materialId}`,
  );
  return resp.json();
}

export async function getMaterialStatus(
  materialId: string,
): Promise<MaterialStatus> {
  const resp = await fetchWithAuth(
    `${API_BASE}/api/materials/${materialId}/status`,
  );
  return resp.json();
}

export async function deleteMaterial(materialId: string): Promise<void> {
  await fetchWithAuth(`${API_BASE}/api/materials/${materialId}`, {
    method: "DELETE",
  });
}

export async function retryMaterial(materialId: string): Promise<CourseMaterial> {
  const resp = await fetchWithAuth(
    `${API_BASE}/api/materials/${materialId}/retry`,
    { method: "POST" },
  );
  return resp.json();
}

export async function updateMaterial(
  materialId: string,
  updates: {
    title?: string;
    material_type?: MaterialType;
    linked_assessment_id?: string | null;
    week_number?: number | null;
    relevant_date?: string | null;
  },
): Promise<CourseMaterial> {
  const resp = await fetchWithAuth(
    `${API_BASE}/api/materials/${materialId}`,
    {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(updates),
    },
  );
  return resp.json();
}

// ---------------------------------------------------------------------------
// Dashboard Briefing
// ---------------------------------------------------------------------------

export async function getDashboardBriefing(): Promise<DashboardBriefingResponse> {
  const resp = await fetchWithAuth(`${API_BASE}/api/dashboard/briefing`);
  return resp.json();
}

export async function sendDashboardChat(
  message: string,
  conversationHistory?: { role: string; content: string }[],
): Promise<DashboardChatResponse> {
  const resp = await fetchWithAuth(`${API_BASE}/api/dashboard/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      message,
      conversation_history: conversationHistory,
    }),
  });
  return resp.json();
}

export async function invalidateBriefingCache(): Promise<void> {
  await fetchWithAuth(`${API_BASE}/api/dashboard/briefing/cache`, {
    method: "DELETE",
  });
}
