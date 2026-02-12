export interface Course {
  id: string;
  user_id: string;
  name: string;
  code: string | null;
  semester_start: string; // DATE as ISO string
  semester_end: string;
  meeting_days: string[];
  meeting_time: string | null;
  holidays: Record<string, unknown>[];
  target_grade: number;
  created_at: string;
  updated_at: string;
}

export interface Syllabus {
  id: string;
  course_id: string;
  user_id: string;
  file_url: string | null;
  file_name: string | null;
  raw_extraction: Record<string, unknown> | null;
  grade_breakdown: Record<string, unknown>[];
  extraction_confidence: number | null;
  needs_review: boolean;
  reviewed_at: string | null;
  created_at: string;
}

export interface Assessment {
  id: string;
  course_id: string;
  syllabus_id: string | null;
  title: string;
  type: string;
  due_date: string | null;
  due_date_raw: string | null;
  is_date_ambiguous: boolean;
  weight_percent: number | null;
  topics: string[] | null;
  created_at: string;
}

export interface Lecture {
  id: string;
  course_id: string;
  title: string;
  lecture_number: number | null;
  lecture_date: string | null;
  processing_status: "pending" | "processing" | "completed" | "failed";
  processing_stage: string | null;
  processing_progress: number;
  summary: string | null;
  duration_seconds: number | null;
  created_at: string;
}

export interface LectureStatus {
  processing_status: "pending" | "processing" | "completed" | "failed";
  processing_stage: string | null;
  processing_progress: number;
  processing_error: string | null;
}

export interface TranscriptSegment {
  start: number | null;
  end: number | null;
  text: string;
  speaker: string;
  slide_number: number | null;
  source: string;
}

export interface LectureConcept {
  id: string;
  title: string;
  description: string | null;
  category: string;
  difficulty_estimate: number;
  linked_assessments: Array<{
    id: string;
    title: string;
    due_date: string | null;
    relevance_score: number;
  }>;
  segment_indices: number[];
}

export interface SlideInfo {
  slide_number: number;
  image_url: string;
  title: string | null;
  text_content: string;
}

export interface LectureDetail extends Lecture {
  audio_url: string | null;
  slides_url: string | null;
  transcript_segments: TranscriptSegment[];
  concepts: LectureConcept[];
  slides: SlideInfo[];
  processing_path: string;
  slide_count: number | null;
}

// ---------------------------------------------------------------------------
// Quizzes
// ---------------------------------------------------------------------------

export type QuizStatus = "pending" | "generating" | "ready" | "failed";
export type QuestionType = "mcq" | "true_false" | "short_answer";
export type QuizDifficulty = "easy" | "medium" | "hard";

export interface Quiz {
  id: string;
  course_id: string;
  title: string;
  status: QuizStatus;
  question_count: number;
  difficulty: QuizDifficulty;
  target_assessment_id: string | null;
  best_score: number | null;
  attempt_count: number;
  created_at: string;
}

export interface QuizQuestion {
  id: string;
  quiz_id?: string;
  question_index: number;
  question_type: QuestionType;
  question_text: string;
  options: string[] | null;
  correct_answer?: string;
  correct_option_index?: number | null;
  explanation?: string;
  concept?: string | null;
  source_lecture_id?: string | null;
  source_lecture_title?: string | null;
  source_timestamp_seconds?: number | null;
}

export interface QuizAnswer {
  question_id: string;
  student_answer: string;
  time_spent_seconds: number | null;
}

export interface QuizSubmissionResult {
  score: number;
  total_questions: number;
  correct_count: number;
  results: QuestionResult[];
}

export interface QuestionResult {
  question_id: string;
  is_correct: boolean;
  student_answer: string;
  correct_answer: string;
  explanation: string;
  question_text?: string;
  question_type?: QuestionType;
  options?: string[] | null;
  source_chunk_ids?: string[];
  concept_id?: string | null;
}

export interface ConceptPerformance {
  concept: string;
  correct: number;
  total: number;
}

export interface QuizGenerationStatus {
  quiz_id: string;
  status: QuizStatus;
  stage: string | null;
  error_message: string | null;
}

// ---------------------------------------------------------------------------
// Search
// ---------------------------------------------------------------------------

export interface SearchResult {
  id: string;
  lecture_id: string;
  lecture_title: string;
  lecture_number: number | null;
  chunk_type: "transcript" | "slide" | "concept";
  content_snippet: string;
  highlighted_snippet: string;
  timestamp_seconds: number | null;
  slide_number: number | null;
  relevance_score: number;
}

export interface SearchResponse {
  query: string;
  results: SearchResult[];
  total_count: number;
}

// ---------------------------------------------------------------------------
// Q&A Chat
// ---------------------------------------------------------------------------

export interface QACitation {
  id: string;
  lecture_id: string;
  lecture_title: string;
  timestamp_seconds: number | null;
  slide_number: number | null;
  content_preview: string;
}

export interface QAMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  citations: QACitation[];
  follow_ups: string[];
  confidence: number | null;
  created_at: string;
}

export interface QAResponse {
  answer: string;
  citations: QACitation[];
  follow_ups: string[];
  confidence: number;
}
