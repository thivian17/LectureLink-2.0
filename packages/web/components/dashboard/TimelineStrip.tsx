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
  if (item.item_type === "practice_quiz") return "blue";
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

function summarizeItems(items: TimelineItem[]): string | null {
  if (items.length === 0) return null;
  if (items.length === 1) return items[0].title;
  const types = new Set(items.map((i) => i.item_type));
  if (types.size === 1) return `${items.length} ${items[0].item_type}s`;
  return `${items.length} items`;
}

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
      <div className="grid grid-cols-14 gap-1 py-1">
        {Array.from({ length: 14 }).map((_, i) => (
          <Skeleton key={i} className="h-24 rounded-xl" />
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
    <div
      className="grid gap-1 py-1"
      style={{ gridTemplateColumns: "repeat(14, minmax(0, 1fr))" }}
    >
      {dates.map((date) => {
        const isToday = date === today;
        const isSelected = date === selectedDate;
        const dayItems = itemsByDate.get(date) ?? [];
        const dots = dayItems.map((item) => getDotColor(item));
        const parsed = parseISO(date);
        const summary = summarizeItems(dayItems);

        return (
          <button
            key={date}
            ref={isToday ? todayRef : undefined}
            onClick={() => onSelectDate(date)}
            className={cn(
              "flex flex-col items-center gap-1.5 rounded-xl px-1 py-3 transition-colors border min-w-0",
              isToday && "ring-2 ring-primary bg-primary/5 border-primary/20",
              isSelected && !isToday && "bg-accent border-accent-foreground/20",
              !isSelected && !isToday && "border-transparent hover:bg-accent/50",
            )}
          >
            <span className="text-xs font-medium text-muted-foreground">
              {format(parsed, "EEE")}
            </span>
            <span className="text-lg font-semibold leading-none">
              {format(parsed, "d")}
            </span>
            <div className="flex gap-0.5">
              {dots.length > 0 ? (
                dots.slice(0, 4).map((color, i) => (
                  <span
                    key={i}
                    className={cn("h-2 w-2 rounded-full", DOT_CLASSES[color])}
                  />
                ))
              ) : (
                <span className="h-2 w-2" />
              )}
            </div>
            {summary && (
              <span className="text-[10px] leading-tight text-muted-foreground truncate w-full text-center">
                {summary}
              </span>
            )}
          </button>
        );
      })}
    </div>
  );
}
