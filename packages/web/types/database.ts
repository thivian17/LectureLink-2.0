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
  onboarding_completed_at: string | null;
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
  low_confidence: boolean | null;
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
  low_concept_yield: boolean;
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

export interface Subconcept {
  title: string;
  description: string;
  difficulty_estimate: number;
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
  subconcepts: Subconcept[];
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
export type QuestionType =
  | "mcq"
  | "true_false"
  | "short_answer"
  | "code_writing"
  | "code_fix"
  | "code_explain";
export type QuizDifficulty = "easy" | "medium" | "hard" | "adaptive";

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
  code_metadata?: CodeMetadata;
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
  code_grading_result?: CodeGradingResult;
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
  generation_stage?: string | null;
}

// Coding question metadata (from quiz_questions.code_metadata)
export interface CodeMetadata {
  language: string;
  starter_code: string;
  reference_solution: string;
  grading_rubric: Record<
    string,
    {
      weight: number;
      criteria: string;
    }
  >;
  hints: string[];
  example_inputs_outputs: Array<{
    input: string;
    expected: string;
  }>;
  common_mistakes: string[];
  max_lines: number;
  time_limit_minutes: number;
  related_lecture_concepts: string[];
}

// Grading result (from quiz_attempts.code_grading_result)
export interface CodeGradingResult {
  overall_score: number;
  is_correct: boolean;
  rubric_scores: Record<
    string,
    {
      score: number;
      max_weight: number;
      feedback: string;
    }
  >;
  line_feedback: Array<{
    line: number;
    type: "error" | "suggestion" | "praise";
    message: string;
  }>;
  overall_feedback: string;
  suggested_improvement: string | null;
  concepts_demonstrated: string[];
  concepts_lacking: string[];
}

// Hint response
export interface HintResponse {
  hint: string;
  hints_remaining: number;
  hint_index: number;
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

// ---------------------------------------------------------------------------
// Performance Analytics (Phase 3)
// ---------------------------------------------------------------------------

export type ConceptTrend = "improving" | "declining" | "stable" | "new";

export interface ConceptMastery {
  concept_id: string;
  title: string;
  description: string | null;
  category: string | null;
  difficulty_estimate: number;
  lecture_id: string | null;
  mastery: number;
  total_attempts: number;
  correct_attempts: number;
  accuracy: number;
  avg_time_seconds: number;
  recent_accuracy: number;
  trend: ConceptTrend;
  linked_assessments: Array<{
    assessment_id: string;
    title: string;
    relevance_score: number;
  }>;
}

export interface PerformanceOverall {
  total_questions_attempted: number;
  overall_accuracy: number;
  quizzes_taken: number;
  average_quiz_score: number | null;
  strongest_category: string | null;
  weakest_category: string | null;
}

export interface QuizHistoryItem {
  quiz_id: string;
  title: string;
  difficulty: string;
  best_score: number | null;
  attempt_count: number;
  question_count: number;
  created_at: string;
}

export interface PerformanceData {
  overall: PerformanceOverall;
  concepts: ConceptMastery[];
  quiz_history: QuizHistoryItem[];
  weak_concepts: string[];
  strong_concepts: string[];
}


// ---------------------------------------------------------------------------
// Invites & Referrals
// ---------------------------------------------------------------------------

export interface Invite {
  invite_code: string;
  invite_url: string;
  email?: string;
  max_uses: number;
  use_count: number;
  expires_at: string;
}

// ---------------------------------------------------------------------------
// Onboarding
// ---------------------------------------------------------------------------

export type OnboardingPath =
  | "just_starting"
  | "mid_semester"
  | "course_complete";

export interface OnboardingStatus {
  path: OnboardingPath | null;
  step: string | null;
  completed_at: string | null;
  welcome_message: {
    message: string;
    generated_at: string;
    path: string;
  } | null;
}

export interface SuggestedPath {
  suggested_path: OnboardingPath;
  progress_pct: number;
}

export interface LectureChecklistItem {
  lecture_number: number;
  expected_date: string;
  week_number: number;
  topic_hint: string | null;
  day_of_week: string;
  status: "pending" | "uploaded" | "skipped";
  is_user_added?: boolean;
}

export interface SemesterProgress {
  status: "not_started" | "in_progress" | "complete";
  progress_pct: number;
  weeks_elapsed: number;
  estimated_lectures_passed: number;
  days_remaining: number;
  past_assessments: Assessment[];
  upcoming_assessments: Assessment[];
  next_assessment: Assessment | null;
}

export interface PersonalizedMessage {
  message: string;
  generated_at: string;
  path: string;
}

// ---------------------------------------------------------------------------
// Study Tutor
// ---------------------------------------------------------------------------

export type TutorMode = "diagnostic" | "full_lesson" | "custom_topic" | "custom_plan";
export type TutorSessionStatus = "active" | "paused" | "completed" | "abandoned";
export type MisconceptionType = "near_miss" | "fundamental" | "incomplete";
export type TutorQuestionType =
  | "mcq"
  | "short_answer"
  | "true_false"
  | "fill_in_blank"
  | "long_answer"
  | "ordering";
export type ChatRelevance = "on_topic" | "related" | "off_topic";
export type BlockType =
  | "teaching"
  | "check"
  | "feedback"
  | "reteach"
  | "practice"
  | "summary"
  | "transition"
  | "chat_response"
  | "complete"
  | "concept_complete";

export interface AssessmentChoice {
  id: string;
  title: string;
  due_date: string;
  weight_percent: number | null;
  days_remaining: number;
}

export interface MasterySummaryItem {
  concept: string;
  mastery: number;
  status: string;
}

export interface TutorSessionEntry {
  upcoming_assessments: AssessmentChoice[];
  active_session: TutorSession | null;
  mastery_summary: MasterySummaryItem[];
  suggested_duration_minutes: number;
}

export interface TutorSession {
  id: string;
  course_id: string;
  mode: TutorMode;
  status: TutorSessionStatus;
  lesson_plan: LessonPlan | null;
  current_concept_index: number;
  current_step_index: number;
  concepts_planned: number;
  concepts_completed: number;
  questions_asked: number;
  questions_correct: number;
  duration_seconds: number;
  suggested_duration_minutes: number;
  target_assessment_id: string | null;
  started_at: string;
  created_at: string;
}

export interface LessonPlan {
  session_title: string;
  estimated_duration_minutes: number;
  concepts: LessonConcept[];
  wrap_up: { type: string; description: string };
}

export interface LessonConcept {
  concept_id: string | null;
  title: string;
  mastery: number;
  total_attempts?: number;
  priority_score: number;
  teaching_approach: "foundational" | "application" | "synthesis";
  estimated_minutes: number;
  outline: LessonStep[];
  generated_content?: ConceptContent;
}

export interface LessonStep {
  type: "activate" | "explain" | "check" | "practice" | "summary" | "transition";
  description: string;
  question_type?: TutorQuestionType;
  targets?: string;
}

export interface ConceptContent {
  concept_title: string;
  blocks: ContentBlock[];
}

export interface ContentBlock {
  block_type: BlockType;
  content: string;
  question?: TutorQuestion;
  rubric?: QuestionRubric;
}

export interface TutorQuestion {
  question_id: string;
  question_text: string;
  question_type: TutorQuestionType;
  options?: string[];
  concept_title: string;
}

export interface QuestionRubric {
  must_mention: string[];
  partial_credit_for: string[];
  common_misconceptions: string[];
  model_answer: string;
}

export interface GradingResult {
  is_correct: boolean;
  feedback: string;
  misconception_type: MisconceptionType | null;
  reteach_triggered: boolean;
  reteach_content: string | null;
  grading_confidence: number;
  rubric_evaluation: Record<string, unknown> | null;
  model_answer: string | null;
}

export interface TutorChatResponse {
  response: string;
  relevance: ChatRelevance;
}

export interface ConceptReadiness {
  concept_id: string | null;
  title: string;
  mastery: number;
  total_attempts: number;
  covered: boolean;
  teaching_approach: "foundational" | "application" | "synthesis";
  lecture_title: string | null;
}

export interface AssessmentReadiness {
  assessment_id: string;
  assessment_title: string;
  due_date: string | null;
  days_remaining: number | null;
  concepts: ConceptReadiness[];
  overall_readiness: number;
  ready_count: number;
  total_count: number;
}

export interface DiagnosticResult {
  total_correct: number;
  total_questions: number;
  concept_results: {
    concept: string;
    correct: boolean;
    misconception?: string;
  }[];
  identified_gaps: string[];
  recommended_focus: (string | { concept_title: string; approach: string })[];
}

// ---------------------------------------------------------------------------
// Gamification (Track A)
// ---------------------------------------------------------------------------

export interface StreakInfo {
  current_streak: number;
  longest_streak: number;
  studied_today: boolean;
  freeze_available: boolean;
  streak_milestone: number | null;
}

export interface LevelInfo {
  current_level: number;
  total_xp: number;
  xp_to_next_level: number;
  progress_percent: number;
}

export interface BadgeInfo {
  badge_id: string;
  name: string;
  description: string;
  icon: string;
  category: string;
  earned_at?: string;
  progress?: number;
  target?: number;
}

export interface GamificationState {
  streak: StreakInfo;
  level: LevelInfo;
  today_xp: number;
  badges_count: number;
  recent_badges: BadgeInfo[];
}

export interface GamificationReadiness {
  assessment_id: string;
  title: string;
  due_date: string | null;
  weight_percent: number | null;
  type: string;
  readiness_score: number;
  days_until_due: number | null;
  urgency: "danger" | "building" | "strong" | "ready";
  trend: number;
  concept_scores: Array<{
    concept_id: string;
    title: string;
    mastery: number;
    total_attempts: number;
    relevance: number;
  }>;
}

export interface CourseReadinessSummary {
  course_id: string;
  course_name: string;
  overall_readiness: number;
  next_assessment: {
    title: string;
    due_date: string | null;
    readiness: number;
    days_until: number | null;
  } | null;
  concepts_mastered: number;
  concepts_total: number;
}

export interface GradeProjection {
  projected_grade_low: number;
  projected_grade_high: number;
  grade_letter: string;
}

export interface WeeklyProgress {
  sessions_count: number;
  concepts_improved: number;
  total_xp: number;
  xp_by_day: Array<{ date: string; xp: number }>;
}

// ---------------------------------------------------------------------------
// Learn Mode (Track B)
// ---------------------------------------------------------------------------

export interface AvailableAssessment {
  assessment_id: string;
  title: string;
  due_date: string | null;
  weight_percent: number | null;
}

export interface AvailableConcept {
  concept_id: string;
  title: string;
  mastery: number;
  total_attempts: number;
}

export interface DailyBriefing {
  course_name: string;
  focus_description: string;
  assessment_context: string | null;
  time_budget: number;
  concepts_planned: Array<{
    concept_id: string;
    title: string;
    mastery: number;
    total_attempts?: number;
  }>;
  available_assessments?: AvailableAssessment[];
  available_concepts?: AvailableConcept[];
  is_custom?: boolean;
}

export interface FlashReviewCard {
  card_id: string;
  concept_id: string;
  concept_title: string;
  question_text: string;
  options: string[];
  correct_index?: number;
  source_lecture_title: string;
}

// Study Card types for Learn Session V2
export interface FormulaVariable {
  symbol: string;
  name: string;
  unit: string;
  description: string;
}

export interface StudyCard {
  type: "hook" | "explain" | "formula" | "example" | "interactive" | "real_world" | "connection" | "gut_check";
  // Common
  content?: string;
  title?: string;
  // Formula
  formula_latex?: string;
  formula_name?: string;
  plain_english?: string;
  variable_breakdown?: FormulaVariable[];
  conditions?: string;
  // Example
  setup?: string;
  steps?: string[];
  answer?: string;
  // Interactive
  challenge_type?: "calculation" | "fill_in";
  prompt?: string;
  hint?: string;
  solution_steps?: string[];
  // Real world
  domain?: string;
  // Connection
  related_concept?: string;
  // Gut check
  question_text?: string;
  options?: string[];
  correct_index?: number;
  explanation?: string;
}

// V2 concept brief with cards array
export interface ConceptBriefV2 extends ConceptBrief {
  cards: StudyCard[];
  has_formula: boolean;
  estimated_read_seconds: number;
}

export interface ConceptBrief {
  concept_id: string;
  concept_title: string;
  sections: {
    what_is_this: string;
    why_it_matters: string;
    key_relationship: string;
  };
  gut_check: {
    question_text: string;
    options: string[];
    correct_index?: number;
    explanation: string;
  };
  sources: Array<{
    lecture_title: string;
    timestamp_seconds: number | null;
  }>;
  mastery_tier: string;
}

export interface PowerQuizQuestion {
  question_id: string;
  question_text: string;
  options: string[];
  concept_id: string;
  concept_title: string;
}

export interface QuizAnswerResult {
  correct: boolean;
  correct_answer: string;
  correct_index?: number;
  explanation: string;
  source_citation: string;
  xp_earned: number;
  combo_count: number;
  combo_multiplier: number;
}

export interface LearnSessionComplete {
  session_summary: {
    duration_minutes: number;
    concepts_covered: Array<{
      title: string;
      mastery_before: number;
      mastery_after: number;
      delta: number;
    }>;
    quiz_score: { correct: number; total: number; accuracy: number };
    combo_max: number;
  };
  xp_summary: {
    total_earned: number;
    breakdown: Array<{ source: string; amount: number }>;
    level_before: number;
    level_after: number;
    leveled_up: boolean;
  };
  streak: StreakInfo;
  badges_earned: BadgeInfo[];
  tomorrow_preview: string;
}

export type LearnSessionStep =
  | "briefing"
  | "flash_review"
  | "concept_brief"
  | "power_quiz"
  | "celebration";

export interface LearnStartSessionResponse {
  session_id: string;
  daily_briefing: DailyBriefing;
  flash_review_cards: FlashReviewCard[];
}

// ---------------------------------------------------------------------------
// Course Materials
// ---------------------------------------------------------------------------

export type MaterialType =
  | 'reading'
  | 'homework'
  | 'practice_exam'
  | 'assignment_outline'
  | 'lab_manual'
  | 'study_guide'
  | 'problem_set'
  | 'other';

export const MATERIAL_TYPE_LABELS: Record<MaterialType, string> = {
  reading: 'Reading',
  homework: 'Homework',
  practice_exam: 'Practice Exam',
  assignment_outline: 'Assignment Outline',
  lab_manual: 'Lab Manual',
  study_guide: 'Study Guide',
  problem_set: 'Problem Set',
  other: 'Other',
};

export interface CourseMaterial {
  id: string;
  course_id: string;
  title: string;
  material_type: MaterialType;
  file_name: string | null;
  processing_status: 'pending' | 'processing' | 'completed' | 'failed';
  processing_progress: number;
  processing_error: string | null;
  linked_assessment_id: string | null;
  linked_lecture_id: string | null;
  week_number: number | null;
  relevant_date: string | null;
  concept_count: number;
  chunk_count: number;
  created_at: string;
}

export interface CourseMaterialDetail extends CourseMaterial {
  file_url: string | null;
  extracted_text_preview: string | null;
  page_count: number | null;
}

export interface MaterialStatus {
  id: string;
  processing_status: 'pending' | 'processing' | 'completed' | 'failed';
  processing_stage: string | null;
  processing_progress: number;
  processing_error: string | null;
}

export interface MaterialListResponse {
  materials: CourseMaterial[];
  total: number;
}

// ---------------------------------------------------------------------------
// Dashboard Briefing
// ---------------------------------------------------------------------------

export interface DashboardBriefingContext {
  student_name: string;
  current_streak: number;
  total_xp: number;
  current_level: number;
  courses: DashboardCourseContext[];
  top_priority_course_id: string | null;
  has_courses: boolean;
}

export interface DashboardCourseContext {
  course_id: string;
  course_name: string;
  course_code: string;
  next_assessment: {
    title: string;
    due_date: string;
    days_until: number;
    weight_percent: number;
    type: string;
    assessment_id: string;
  } | null;
  weak_concepts: { concept_id: string; title: string; mastery: number }[];
  session_recommendation: {
    concepts: string[];
    reason: string;
    time_budget: number;
  } | null;
  recent_session: {
    completed_at: string;
    concepts_covered: string[];
    quiz_score: number;
  } | null;
  lecture_gap: number;
}

export interface DashboardGreeting {
  greeting: string;
  session_pitch: string;
  checkin_question: string;
  encouragement: string;
}

export interface DashboardBriefingResponse {
  context: DashboardBriefingContext;
  greeting: DashboardGreeting;
}

export interface DashboardChatResponse {
  message: string;
  context_used: boolean;
}

export interface SessionSummary {
  session_id: string;
  mode: TutorMode;
  concepts_covered: {
    concept_title: string;
    questions_asked: number;
    questions_correct: number;
  }[];
  total_questions: number;
  total_correct: number;
  accuracy_percent: number;
  duration_seconds: number;
  mastery_changes: {
    concept: string;
    before: number;
    after: number;
  }[] | null;
}

// ---------------------------------------------------------------------------
// Dashboard V2 — Academic Command Center
// ---------------------------------------------------------------------------

export interface ReadinessBreakdownV2 {
  coverage: number;
  practice: number;
  freshness: number;
  effort: number;
}

export interface WeakConcept {
  concept_id: string;
  title: string;
  coverage: boolean;
  practice_score: number;
  freshness_score: number;
  combined_score: number;
}

export interface SuggestedAction {
  action_type: "study_session" | "practice_test" | "flash_review";
  title: string;
  description: string;
  estimated_minutes: number;
  target_course_id: string | null;
  target_assessment_id: string | null;
  urgency: "critical" | "high" | "medium" | "low";
  expected_impact: string;
}

export interface AssessmentReadinessV2 {
  assessment_id: string;
  title: string;
  course_id: string;
  course_name: string | null;
  assessment_type: string;
  due_date: string | null;
  days_until_due: number | null;
  readiness: number;
  breakdown: ReadinessBreakdownV2;
  weak_concepts: WeakConcept[];
  suggested_actions: SuggestedAction[];
  urgency: "critical" | "high" | "medium" | "low";
  concept_count: number;
  covered_count: number;
}

export interface CourseIntelligenceV2 {
  course_id: string;
  course_name: string;
  course_code: string | null;
  readiness: number;
  risk: "low" | "medium" | "high";
  next_assessment: {
    assessment_id: string;
    title: string;
    type: string;
    due_date: string | null;
    days_until: number | null;
    readiness: number | null;
  } | null;
  recommended_action: SuggestedAction | null;
  assessment_count: number;
}

export interface TimelineItem {
  date: string;
  item_type: "exam" | "quiz" | "midterm" | "assignment" | "project" | "discussion" | "practice_quiz";
  title: string;
  course_id: string;
  course_name: string;
  course_code: string | null;
  assessment_id: string | null;
  readiness: number | null;
  urgency: "critical" | "high" | "medium" | "low" | null;
  needs_review: boolean;
}

export interface DashboardTimeline {
  items: TimelineItem[];
  today: string;
}

export interface DashboardActions {
  actions: SuggestedAction[];
}

export interface DashboardCourses {
  courses: CourseIntelligenceV2[];
}

export interface DashboardStats {
  streak: number;
  xp_this_week: number;
  study_minutes_this_week: number;
  concepts_practiced_this_week: number;
}
