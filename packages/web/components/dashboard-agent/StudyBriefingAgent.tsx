"use client";

import { useState, useEffect, useCallback } from "react";
import Link from "next/link";
import { Bot, ChevronDown, ChevronUp, Plus } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { BriefingChat } from "./BriefingChat";
import { getDashboardBriefing, AuthError } from "@/lib/api";
import { serverLog } from "@/lib/server-log";
import type { DashboardBriefingResponse } from "@/types/database";

interface StudyBriefingAgentProps {
  onBriefingLoaded?: (data: DashboardBriefingResponse) => void;
}

export function StudyBriefingAgent({ onBriefingLoaded }: StudyBriefingAgentProps) {
  const [briefing, setBriefing] = useState<DashboardBriefingResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [chatExpanded, setChatExpanded] = useState(false);
  const [error, setError] = useState(false);

  const load = useCallback(async () => {
    try {
      const data = await getDashboardBriefing();
      setBriefing(data);
      onBriefingLoaded?.(data);
    } catch (err) {
      if (err instanceof AuthError) return;
      serverLog("error", "StudyBriefingAgent", "Briefing fetch failed, hiding agent card", {
        error: err instanceof Error ? err.message : String(err),
      });
      setError(true);
    } finally {
      setLoading(false);
    }
  }, [onBriefingLoaded]);

  useEffect(() => {
    load();
  }, [load]);

  if (loading) {
    return (
      <Card className="border-primary/10">
        <CardContent className="pt-5 space-y-3">
          <div className="flex items-start gap-3">
            <Skeleton className="h-9 w-9 rounded-full shrink-0" />
            <div className="flex-1 space-y-2">
              <Skeleton className="h-4 w-3/4" />
              <Skeleton className="h-4 w-full" />
              <Skeleton className="h-4 w-1/2" />
            </div>
          </div>
        </CardContent>
      </Card>
    );
  }

  if (error || !briefing) return null;

  const { greeting, context } = briefing;
  const hasCourses = context.has_courses;

  return (
    <Card className="border-primary/10 bg-gradient-to-br from-primary/[0.02] to-transparent">
      <CardContent className="pt-5">
        <div className="flex items-start gap-3">
          {/* Avatar */}
          <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-primary/10">
            <Bot className="h-4.5 w-4.5 text-primary" />
          </div>

          {/* Content */}
          <div className="flex-1 min-w-0 space-y-2.5">
            {/* Greeting */}
            <p className="text-sm leading-relaxed">
              {greeting.greeting}
            </p>

            {/* Session pitch */}
            {hasCourses && greeting.session_pitch && (
              <p className="text-sm text-muted-foreground leading-relaxed">
                {greeting.session_pitch}
              </p>
            )}

            {/* Encouragement */}
            {greeting.encouragement && (
              <p className="text-sm text-muted-foreground italic">
                {greeting.encouragement}
              </p>
            )}

            {/* Check-in or onboarding CTA */}
            {hasCourses ? (
              <div className="pt-1">
                <button
                  onClick={() => setChatExpanded(!chatExpanded)}
                  className="inline-flex items-center gap-1.5 text-sm text-primary hover:underline"
                >
                  {greeting.checkin_question}
                  {chatExpanded ? (
                    <ChevronUp className="h-3.5 w-3.5" />
                  ) : (
                    <ChevronDown className="h-3.5 w-3.5" />
                  )}
                </button>
              </div>
            ) : (
              <div className="pt-1">
                <Button asChild size="sm">
                  <Link href="/dashboard/courses/new">
                    <Plus className="mr-1.5 h-3.5 w-3.5" />
                    Add Your First Course
                  </Link>
                </Button>
              </div>
            )}

            {/* Expandable chat */}
            {chatExpanded && hasCourses && (
              <BriefingChat />
            )}
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
