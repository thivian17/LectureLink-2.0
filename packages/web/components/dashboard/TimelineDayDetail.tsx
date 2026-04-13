"use client";

import Link from "next/link";
import { format, parseISO } from "date-fns";
import {
  GraduationCap,
  FileText,
  MessageSquare,
  BookOpen,
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import type { TimelineItem } from "@/types/database";

interface TimelineDayDetailProps {
  items: TimelineItem[];
  selectedDate: string;
}

const EXAM_TYPES = new Set(["exam", "midterm", "quiz"]);

function getItemIcon(item: TimelineItem) {
  if (EXAM_TYPES.has(item.item_type)) {
    const color = readinessColor(item.readiness);
    return <GraduationCap className={cn("h-4 w-4 shrink-0", color)} />;
  }
  if (item.item_type === "practice_quiz") {
    return <BookOpen className="h-4 w-4 shrink-0 text-blue-500" />;
  }
  if (item.item_type === "discussion") {
    return <MessageSquare className="h-4 w-4 shrink-0 text-muted-foreground" />;
  }
  return <FileText className="h-4 w-4 shrink-0 text-muted-foreground" />;
}

function readinessColor(readiness: number | null): string {
  if (readiness == null) return "text-muted-foreground";
  if (readiness < 0.6) return "text-red-500";
  if (readiness < 0.8) return "text-amber-500";
  return "text-emerald-500";
}

function ItemRow({ item }: { item: TimelineItem }) {
  const isExam = EXAM_TYPES.has(item.item_type);

  const content = (
    <div className="flex items-center gap-3 rounded-lg px-3 py-2 transition-colors hover:bg-accent/50">
      {getItemIcon(item)}
      <div className="flex flex-1 items-center gap-2 min-w-0">
        <span className="truncate text-sm font-medium">{item.title}</span>
        {item.course_code && (
          <Badge variant="secondary" className="text-[10px] px-1.5 py-0">
            {item.course_code}
          </Badge>
        )}
      </div>
      <div className="shrink-0 text-xs text-muted-foreground">
        {isExam && item.readiness != null ? (
          <span className={cn("font-medium tabular-nums", readinessColor(item.readiness))}>
            {Math.round(item.readiness * 100)}%
          </span>
        ) : (
          <span>Due</span>
        )}
      </div>
    </div>
  );

  if (isExam && item.assessment_id) {
    return (
      <Link href={`/dashboard/courses/${item.course_id}`}>
        {content}
      </Link>
    );
  }

  return content;
}

export function TimelineDayDetail({
  items,
  selectedDate,
}: TimelineDayDetailProps) {
  const dayItems = items.filter((i) => i.date === selectedDate);
  const parsed = parseISO(selectedDate);

  return (
    <div className="space-y-1">
      <p className="text-xs font-medium text-muted-foreground px-1">
        {format(parsed, "EEEE, MMM d")}
      </p>
      {dayItems.length === 0 ? (
        <p className="text-sm text-muted-foreground px-3 py-2">
          Nothing scheduled
        </p>
      ) : (
        dayItems.map((item, i) => <ItemRow key={i} item={item} />)
      )}
    </div>
  );
}
