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
