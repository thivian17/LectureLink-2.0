"use client";

import { useState, useMemo } from "react";
import {
  format,
  startOfMonth,
  endOfMonth,
  startOfWeek,
  endOfWeek,
  addMonths,
  subMonths,
  isSameMonth,
  isToday,
  differenceInCalendarDays,
  eachDayOfInterval,
} from "date-fns";
import { ChevronLeft, ChevronRight } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import type { Assessment } from "@/types/database";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface CalendarAssessment extends Assessment {
  course_name: string;
  course_code: string | null;
}

export interface HolidayPeriod {
  name: string;
  start: string; // "YYYY-MM-DD"
  end: string;   // "YYYY-MM-DD"
}

interface AssessmentCalendarProps {
  assessments: CalendarAssessment[];
  holidays?: HolidayPeriod[];
  /** When set, the calendar starts on this month instead of today's month. */
  initialDate?: Date;
}

// ---------------------------------------------------------------------------
// Assessment type → color classes
// ---------------------------------------------------------------------------

const TYPE_COLORS: Record<string, { badge: string; dot: string }> = {
  exam: { badge: "bg-red-100 text-red-700 border-red-200", dot: "bg-red-500" },
  quiz: {
    badge: "bg-amber-100 text-amber-700 border-amber-200",
    dot: "bg-amber-500",
  },
  homework: {
    badge: "bg-blue-100 text-blue-700 border-blue-200",
    dot: "bg-blue-500",
  },
  project: {
    badge: "bg-purple-100 text-purple-700 border-purple-200",
    dot: "bg-purple-500",
  },
  lab: {
    badge: "bg-green-100 text-green-700 border-green-200",
    dot: "bg-green-500",
  },
  paper: {
    badge: "bg-teal-100 text-teal-700 border-teal-200",
    dot: "bg-teal-500",
  },
  presentation: {
    badge: "bg-indigo-100 text-indigo-700 border-indigo-200",
    dot: "bg-indigo-500",
  },
  participation: {
    badge: "bg-slate-100 text-slate-700 border-slate-200",
    dot: "bg-slate-500",
  },
  other: {
    badge: "bg-gray-100 text-gray-700 border-gray-200",
    dot: "bg-gray-500",
  },
};

function getTypeColors(type: string) {
  return TYPE_COLORS[type.toLowerCase()] ?? TYPE_COLORS.other;
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function parseLocalDate(dateStr: string): Date {
  const [year, month, day] = dateStr.split("-").map(Number);
  return new Date(year, month - 1, day);
}

/** Build the 6×7 grid of dates for a given month. */
function getMonthGrid(date: Date): Date[] {
  const monthStart = startOfMonth(date);
  const monthEnd = endOfMonth(date);
  const gridStart = startOfWeek(monthStart); // Sunday
  const gridEnd = endOfWeek(monthEnd); // Saturday
  return eachDayOfInterval({ start: gridStart, end: gridEnd });
}

/** Group assessments by their due_date string (YYYY-MM-DD). */
function groupByDate(
  assessments: CalendarAssessment[],
): Map<string, CalendarAssessment[]> {
  const map = new Map<string, CalendarAssessment[]>();
  for (const a of assessments) {
    if (!a.due_date) continue;
    const key = a.due_date; // already "YYYY-MM-DD"
    const list = map.get(key);
    if (list) {
      list.push(a);
    } else {
      map.set(key, [a]);
    }
  }
  return map;
}

/** Build a Map from "YYYY-MM-DD" → holiday name for all dates in holiday periods. */
function buildHolidayMap(holidays: HolidayPeriod[]): Map<string, string> {
  const map = new Map<string, string>();
  for (const h of holidays) {
    const start = parseLocalDate(h.start);
    const end = parseLocalDate(h.end);
    const days = eachDayOfInterval({ start, end });
    for (const d of days) {
      map.set(format(d, "yyyy-MM-dd"), h.name);
    }
  }
  return map;
}

const DAY_HEADERS = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];
const MAX_VISIBLE_BADGES = 3;

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

function AssessmentBadgePopover({ assessment }: { assessment: CalendarAssessment }) {
  const colors = getTypeColors(assessment.type);
  const daysUntil = assessment.due_date
    ? differenceInCalendarDays(parseLocalDate(assessment.due_date), new Date())
    : null;

  const courseLabel = assessment.course_code ?? assessment.course_name;

  return (
    <Popover>
      <PopoverTrigger asChild>
        <button
          className={`w-full text-left text-[11px] leading-tight px-1.5 py-0.5 rounded border truncate cursor-pointer hover:opacity-80 transition-opacity ${colors.badge}`}
        >
          {assessment.title}
        </button>
      </PopoverTrigger>
      <PopoverContent className="w-64 p-3 space-y-2" align="start">
        <div className="space-y-1">
          <p className="font-medium text-sm">{assessment.title}</p>
          <div className="flex items-center gap-2">
            <Badge
              variant="outline"
              className={`text-[10px] px-1.5 py-0 ${colors.badge}`}
            >
              {assessment.type}
            </Badge>
            <span className="text-xs text-muted-foreground">{courseLabel}</span>
          </div>
        </div>
        <div className="text-xs text-muted-foreground space-y-0.5">
          {assessment.due_date && (
            <p>Due: {format(parseLocalDate(assessment.due_date), "MMMM d, yyyy")}</p>
          )}
          {assessment.weight_percent != null && (
            <p>Weight: {assessment.weight_percent}%</p>
          )}
          {daysUntil !== null && (
            <p className={daysUntil < 0 ? "text-red-600" : daysUntil <= 3 ? "text-amber-600" : ""}>
              {daysUntil === 0
                ? "Due today"
                : daysUntil > 0
                  ? `${daysUntil} day${daysUntil !== 1 ? "s" : ""} from now`
                  : `${Math.abs(daysUntil)} day${Math.abs(daysUntil) !== 1 ? "s" : ""} ago`}
            </p>
          )}
        </div>
      </PopoverContent>
    </Popover>
  );
}

function DayCell({
  date,
  currentMonth,
  assessments,
  holidayName,
}: {
  date: Date;
  currentMonth: Date;
  assessments: CalendarAssessment[];
  holidayName?: string;
}) {
  const inMonth = isSameMonth(date, currentMonth);
  const today = isToday(date);
  const overflow = assessments.length - MAX_VISIBLE_BADGES;

  return (
    <div
      className={`min-h-[90px] border-t p-1 ${
        holidayName && inMonth
          ? "bg-orange-50 dark:bg-orange-950/20"
          : !inMonth
            ? "bg-muted/30"
            : ""
      } ${today ? "bg-primary/5 ring-1 ring-inset ring-primary/30" : ""}`}
    >
      <span
        className={`text-xs font-medium inline-flex items-center justify-center w-6 h-6 rounded-full ${
          today
            ? "bg-primary text-primary-foreground"
            : !inMonth
              ? "text-muted-foreground"
              : ""
        }`}
      >
        {format(date, "d")}
      </span>
      {holidayName && inMonth && (
        <p className="text-[10px] text-orange-600 dark:text-orange-400 font-medium px-0.5 truncate">
          {holidayName}
        </p>
      )}
      <div className="mt-0.5 space-y-0.5">
        {assessments.slice(0, MAX_VISIBLE_BADGES).map((a) => (
          <AssessmentBadgePopover key={a.id} assessment={a} />
        ))}
        {overflow > 0 && (
          <p className="text-[10px] text-muted-foreground px-1">
            +{overflow} more
          </p>
        )}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------

export function AssessmentCalendar({
  assessments,
  holidays = [],
  initialDate,
}: AssessmentCalendarProps) {
  const [currentMonth, setCurrentMonth] = useState(
    initialDate ?? new Date(),
  );

  const grid = useMemo(() => getMonthGrid(currentMonth), [currentMonth]);
  const byDate = useMemo(() => groupByDate(assessments), [assessments]);
  const holidayMap = useMemo(() => buildHolidayMap(holidays), [holidays]);

  return (
    <div className="space-y-4">
      {/* Month navigation */}
      <div className="flex items-center justify-between">
        <Button
          variant="outline"
          size="icon"
          className="h-8 w-8"
          onClick={() => setCurrentMonth((d) => subMonths(d, 1))}
        >
          <ChevronLeft className="h-4 w-4" />
        </Button>
        <h2 className="text-lg font-semibold">
          {format(currentMonth, "MMMM yyyy")}
        </h2>
        <Button
          variant="outline"
          size="icon"
          className="h-8 w-8"
          onClick={() => setCurrentMonth((d) => addMonths(d, 1))}
        >
          <ChevronRight className="h-4 w-4" />
        </Button>
      </div>

      {/* Day-of-week headers */}
      <div className="grid grid-cols-7 border rounded-lg overflow-hidden">
        {DAY_HEADERS.map((day) => (
          <div
            key={day}
            className="text-center text-xs font-medium text-muted-foreground py-2 bg-muted/50"
          >
            {day}
          </div>
        ))}

        {/* Day cells */}
        {grid.map((date) => {
          const key = format(date, "yyyy-MM-dd");
          return (
            <DayCell
              key={key}
              date={date}
              currentMonth={currentMonth}
              assessments={byDate.get(key) ?? []}
              holidayName={holidayMap.get(key)}
            />
          );
        })}
      </div>
    </div>
  );
}

// Re-export the type color helpers so other components can use them
export { getTypeColors, parseLocalDate, TYPE_COLORS };
