// TypeScript mirrors of packages/api/src/lecturelink_api/models/syllabus_models.py

export interface ExtractedField<T = string | number | null> {
  value: T;
  confidence: number; // 0.0-1.0
  source_text: string | null;
}

export interface AssessmentExtraction {
  title: ExtractedField<string>;
  type: ExtractedField<string>;
  due_date_raw: ExtractedField<string | null>;
  due_date_resolved: ExtractedField<string | null>;
  weight_percent: ExtractedField<number | null>;
  topics: string[];
}

export interface GradeComponent {
  name: ExtractedField<string>;
  weight_percent: ExtractedField<number | null>;
  drop_policy: ExtractedField<string | null> | null;
}

export interface WeeklyScheduleEntry {
  week_number: number;
  date_range: ExtractedField<string | null> | null;
  topics: string[];
  readings: string[];
  due_items: string[];
}

export interface SyllabusExtraction {
  course_name: ExtractedField<string>;
  course_code: ExtractedField<string | null> | null;
  instructor_name: ExtractedField<string | null> | null;
  instructor_email: ExtractedField<string | null> | null;
  office_hours: ExtractedField<string | null> | null;
  grade_breakdown: GradeComponent[];
  assessments: AssessmentExtraction[];
  weekly_schedule: WeeklyScheduleEntry[];
  policies: Record<string, string>;
  extraction_confidence: number;
  missing_sections: string[];
}

// Confidence thresholds
export const CONFIDENCE_HIGH = 0.7;
export const CONFIDENCE_MEDIUM = 0.5;

export type ConfidenceLevel = "high" | "medium" | "low";

export function getConfidenceLevel(confidence: number): ConfidenceLevel {
  if (confidence >= CONFIDENCE_HIGH) return "high";
  if (confidence >= CONFIDENCE_MEDIUM) return "medium";
  return "low";
}

export function getConfidenceColor(level: ConfidenceLevel) {
  switch (level) {
    case "high":
      return "border-l-green-500/60";
    case "medium":
      return "border-l-amber-500/60 bg-amber-50/50";
    case "low":
      return "border-l-red-500/60 bg-red-50/50";
  }
}

export function getConfidenceBadgeClasses(level: ConfidenceLevel) {
  switch (level) {
    case "high":
      return "text-green-700 border-green-300 bg-green-50";
    case "medium":
      return "text-amber-700 border-amber-300 bg-amber-50";
    case "low":
      return "text-red-700 border-red-300 bg-red-50";
  }
}

export const ASSESSMENT_TYPES = [
  "exam",
  "quiz",
  "homework",
  "project",
  "lab",
  "paper",
  "presentation",
  "participation",
  "other",
] as const;

export type AssessmentType = (typeof ASSESSMENT_TYPES)[number];
