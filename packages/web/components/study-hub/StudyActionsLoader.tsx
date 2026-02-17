"use client";

import { useState, useEffect } from "react";

import { Card, CardContent } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { HeroActionCard } from "@/components/study-hub/HeroActionCard";
import { SecondaryActions } from "@/components/study-hub/SecondaryActions";
import { getStudyActions, AuthError } from "@/lib/api";
import type { StudyAction } from "@/types/database";

export function StudyActionsLoader() {
  const [actions, setActions] = useState<StudyAction[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        const data = await getStudyActions();
        if (!cancelled) setActions(data.actions);
      } catch (err) {
        if (err instanceof AuthError) return;
        console.error("[StudyHub] Failed to load study actions:", err);
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    load();
    return () => {
      cancelled = true;
    };
  }, []);

  if (loading) {
    return (
      <div className="space-y-4">
        <Card>
          <CardContent className="flex items-start gap-4 py-5">
            <Skeleton className="h-10 w-10 rounded-lg shrink-0" />
            <div className="flex-1 space-y-2">
              <Skeleton className="h-5 w-2/3" />
              <Skeleton className="h-4 w-full" />
            </div>
            <Skeleton className="h-9 w-28 shrink-0" />
          </CardContent>
        </Card>
      </div>
    );
  }

  if (actions.length === 0) return null;

  return (
    <div className="space-y-4">
      <HeroActionCard action={actions[0]} />
      {actions.length > 1 && (
        <SecondaryActions actions={actions.slice(1, 3)} />
      )}
    </div>
  );
}
