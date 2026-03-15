"use client";

import { useRef, useEffect } from "react";
import { format, parseISO } from "date-fns";
import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";
import type { TimelineItem } from "@/types/database";

interface TimelineStripProps {
  items: TimelineItem[];
  today: string;
  selectedDate: string;
  onSelectDate: (date: string) => void;
  loading: boolean;
}

type DotColor = "red" | "amber" | "green" | "blue" | "gray";

function getDotColor(item: TimelineItem): DotColor {
  const examTypes = new Set(["exam", "midterm", "quiz"]);

  if (item.needs_review) return "blue";
  if (item.item_type === "lecture_review") return "blue";
  if (!examTypes.has(item.item_type)) return "gray";

  const r = item.readiness;
  if (r == null) return "gray";
  if (r < 0.6) return "red";
  if (r < 0.8) return "amber";
  return "green";
}

const DOT_CLASSES: Record<DotColor, string> = {
  red: "bg-red-500",
  amber: "bg-amber-500",
  green: "bg-emerald-500",
  blue: "bg-blue-500",
  gray: "bg-muted-foreground/50",
};

export function TimelineStrip({
  items,
  today,
  selectedDate,
  onSelectDate,
  loading,
}: TimelineStripProps) {
  const todayRef = useRef<HTMLButtonElement>(null);

  // Scroll today's cell into view on mount
  useEffect(() => {
    if (!loading && todayRef.current) {
      todayRef.current.scrollIntoView({
        inline: "center",
        block: "nearest",
        behavior: "instant",
      });
    }
  }, [loading]);

  if (loading) {
    return (
      <div className="flex gap-1.5 overflow-hidden">
        {Array.from({ length: 14 }).map((_, i) => (
          <Skeleton key={i} className="h-20 w-16 shrink-0 rounded-lg" />
        ))}
      </div>
    );
  }

  // Group items by date
  const itemsByDate = new Map<string, TimelineItem[]>();
  for (const item of items) {
    const existing = itemsByDate.get(item.date) ?? [];
    existing.push(item);
    itemsByDate.set(item.date, existing);
  }

  // Generate 14 days starting from today
  const dates: string[] = [];
  const start = parseISO(today);
  for (let i = 0; i < 14; i++) {
    const d = new Date(start);
    d.setDate(d.getDate() + i);
    dates.push(format(d, "yyyy-MM-dd"));
  }

  return (
    <div className="flex gap-1.5 overflow-x-auto snap-x snap-mandatory pb-1 scrollbar-none">
      {dates.map((date) => {
        const isToday = date === today;
        const isSelected = date === selectedDate;
        const dayItems = itemsByDate.get(date) ?? [];
        const dots = dayItems.map((item) => getDotColor(item));
        const parsed = parseISO(date);

        return (
          <button
            key={date}
            ref={isToday ? todayRef : undefined}
            onClick={() => onSelectDate(date)}
            className={cn(
              "flex w-16 shrink-0 snap-start flex-col items-center gap-1 rounded-lg px-1 py-2 transition-colors",
              isToday && "ring-2 ring-primary bg-primary/5",
              isSelected && !isToday && "bg-accent",
              !isSelected && !isToday && "hover:bg-accent/50",
            )}
          >
            <span className="text-xs text-muted-foreground">
              {format(parsed, "EEE")}
            </span>
            <span className="text-sm font-medium">{format(parsed, "d")}</span>
            <div className="flex gap-0.5">
              {dots.length > 0 ? (
                dots.slice(0, 4).map((color, i) => (
                  <span
                    key={i}
                    className={cn("h-1.5 w-1.5 rounded-full", DOT_CLASSES[color])}
                  />
                ))
              ) : (
                <span className="h-1.5 w-1.5" />
              )}
            </div>
          </button>
        );
      })}
    </div>
  );
}
