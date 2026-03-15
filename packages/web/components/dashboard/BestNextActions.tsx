"use client";

import { CheckCircle } from "lucide-react";
import { Skeleton } from "@/components/ui/skeleton";
import { ActionCard } from "./ActionCard";
import type { DashboardActions } from "@/types/database";

interface BestNextActionsProps {
  actions: DashboardActions | null;
  loading: boolean;
}

export function BestNextActions({ actions, loading }: BestNextActionsProps) {
  if (loading) {
    return (
      <section className="space-y-3">
        <div>
          <h2 className="text-base font-semibold">Recommended Actions</h2>
          <p className="text-xs text-muted-foreground">
            What to focus on right now
          </p>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          <Skeleton className="h-28 w-full rounded-xl" />
          <Skeleton className="h-28 w-full rounded-xl" />
        </div>
      </section>
    );
  }

  const items = actions?.actions ?? [];

  return (
    <section className="space-y-3">
      <div>
        <h2 className="text-base font-semibold">Recommended Actions</h2>
        <p className="text-xs text-muted-foreground">
          What to focus on right now
        </p>
      </div>
      {items.length === 0 ? (
        <div className="flex items-center gap-2 py-4 text-sm text-muted-foreground">
          <CheckCircle className="h-4 w-4 text-green-500" />
          You&apos;re all caught up!
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          {items.map((action, i) => (
            <ActionCard key={i} action={action} />
          ))}
        </div>
      )}
    </section>
  );
}
