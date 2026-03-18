"use client";

import { useState } from "react";
import { format } from "date-fns";
import { StatsRow } from "./StatsRow";
import { TimelineStrip } from "./TimelineStrip";
import { TimelineDayDetail } from "./TimelineDayDetail";
import type { DashboardTimeline, DashboardStats } from "@/types/database";

interface AcademicCommandCenterProps {
  timeline: DashboardTimeline | null;
  stats: DashboardStats | null;
  loading: boolean;
}

export function AcademicCommandCenter({
  timeline,
  stats,
  loading,
}: AcademicCommandCenterProps) {
  const today = timeline?.today ?? format(new Date(), "yyyy-MM-dd");
  const [selectedDate, setSelectedDate] = useState(today);

  return (
    <section className="space-y-3">
      <div className="flex items-center justify-between gap-4">
        <h2 className="text-base font-semibold shrink-0">Academic Command Center</h2>
        <StatsRow stats={stats} loading={loading} />
      </div>

      <TimelineStrip
        items={timeline?.items ?? []}
        today={today}
        selectedDate={selectedDate}
        onSelectDate={setSelectedDate}
        loading={loading}
      />

      {!loading && (
        <TimelineDayDetail
          items={timeline?.items ?? []}
          selectedDate={selectedDate}
        />
      )}
    </section>
  );
}
