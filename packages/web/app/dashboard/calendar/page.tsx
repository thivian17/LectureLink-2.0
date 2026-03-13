import { createClient } from "@/lib/supabase/server";
import { AssessmentCalendar } from "@/components/assessment-calendar";
import type { CalendarAssessment, HolidayPeriod } from "@/components/assessment-calendar";
import { UpcomingAssessments } from "@/components/upcoming-assessments";

export default async function CalendarPage() {
  const supabase = await createClient();

  // Fetch all assessments with their course info for the authenticated user.
  // RLS + inner join on courses ensures only the user's data is returned.
  const { data } = await supabase
    .from("assessments")
    .select("*, courses!inner(name, code)")
    .not("due_date", "is", null)
    .order("due_date", { ascending: true });

  const assessments: CalendarAssessment[] = (data ?? []).map((row) => {
    const course = row.courses as unknown as { name: string; code: string | null };
    return {
      id: row.id,
      course_id: row.course_id,
      syllabus_id: row.syllabus_id,
      title: row.title,
      type: row.type,
      due_date: row.due_date,
      due_date_raw: row.due_date_raw,
      is_date_ambiguous: row.is_date_ambiguous,
      weight_percent: row.weight_percent,
      topics: row.topics,
      created_at: row.created_at,
      course_name: course.name,
      course_code: course.code,
    };
  });

  // Fetch holidays from all user courses and deduplicate by date range
  const { data: courses } = await supabase
    .from("courses")
    .select("holidays");

  const holidaySet = new Set<string>();
  const holidays: HolidayPeriod[] = [];
  for (const course of courses ?? []) {
    // DB stores start_date/end_date; normalize to start/end
    for (const h of (course.holidays as Record<string, string>[]) ?? []) {
      const start = h.start ?? h.start_date;
      const end = h.end ?? h.end_date;
      if (!start || !end) continue;
      const key = `${start}_${end}`;
      if (holidaySet.has(key)) continue;
      holidaySet.add(key);
      holidays.push({ name: h.name ?? "Holiday", start, end });
    }
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Calendar</h1>
        <p className="text-muted-foreground">
          Assessment deadlines across all your courses.
        </p>
      </div>

      <AssessmentCalendar assessments={assessments} holidays={holidays} />

      <UpcomingAssessments assessments={assessments} />
    </div>
  );
}
