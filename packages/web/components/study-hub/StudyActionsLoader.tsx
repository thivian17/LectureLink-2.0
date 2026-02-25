"use client";

import { useState, useEffect, useRef, useCallback } from "react";

import { Card, CardContent } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { HeroActionCard } from "@/components/study-hub/HeroActionCard";
import { SecondaryActions } from "@/components/study-hub/SecondaryActions";
import { getStudyActions, getStudyActionsEnhanced, AuthError } from "@/lib/api";
import type { StudyAction } from "@/types/database";

export function StudyActionsLoader() {
  const [actions, setActions] = useState<StudyAction[]>([]);
  const [loading, setLoading] = useState(true);
  const [fading, setFading] = useState(false);
  const cancelledRef = useRef(false);
  const pendingEnhancedRef = useRef<StudyAction[] | null>(null);

  const applyEnhanced = useCallback((enhanced: StudyAction[]) => {
    // Fade out, swap data, fade back in
    setFading(true);
    setTimeout(() => {
      setActions(enhanced);
      setFading(false);
    }, 200);
  }, []);

  useEffect(() => {
    cancelledRef.current = false;

    // Phase 1: fast deterministic results
    getStudyActions()
      .then((data) => {
        if (cancelledRef.current) return;
        setActions(data.actions);
        setLoading(false);

        // If enhanced results already arrived while we were loading,
        // apply them immediately (no fade needed — user just saw skeleton)
        const pending = pendingEnhancedRef.current;
        if (pending && pending.length > 0) {
          setActions(pending);
          pendingEnhancedRef.current = null;
        }
      })
      .catch((err) => {
        if (err instanceof AuthError) return;
        console.error("[StudyHub] Failed to load study actions:", err);
        if (!cancelledRef.current) setLoading(false);
      });

    // Phase 2: LLM-enhanced results (fire in parallel)
    getStudyActionsEnhanced()
      .then((data) => {
        if (cancelledRef.current || data.actions.length === 0) return;

        // If still in loading skeleton, stash for phase 1 to pick up
        if (loading) {
          pendingEnhancedRef.current = data.actions;
        } else {
          applyEnhanced(data.actions);
        }
      })
      .catch((err) => {
        if (err instanceof AuthError) return;
        // Silent — deterministic results are already showing
      });

    return () => {
      cancelledRef.current = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
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
    <div
      className="space-y-4 transition-opacity duration-200"
      style={{ opacity: fading ? 0 : 1 }}
    >
      <HeroActionCard action={actions[0]} />
      {actions.length > 1 && (
        <SecondaryActions actions={actions.slice(1, 3)} />
      )}
    </div>
  );
}
