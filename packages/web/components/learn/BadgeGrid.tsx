"use client";

import type { BadgeInfo } from "@/types/database";
import { BadgeCard } from "./BadgeCard";

interface BadgeGridProps {
  earned: BadgeInfo[];
  available: BadgeInfo[];
  categoryFilter: string | null;
  onBadgeClick: (badge: BadgeInfo) => void;
}

export function BadgeGrid({ earned, available, categoryFilter, onBadgeClick }: BadgeGridProps) {
  const earnedSet = new Set(earned.map((b) => b.badge_id));

  const allBadges = [
    ...earned.map((b) => ({ ...b, isEarned: true })),
    ...available.filter((b) => !earnedSet.has(b.badge_id)).map((b) => ({ ...b, isEarned: false })),
  ];

  const filtered = categoryFilter
    ? allBadges.filter((b) => b.category === categoryFilter)
    : allBadges;

  if (filtered.length === 0) {
    return (
      <p className="text-center py-8 text-muted-foreground text-sm">
        No badges in this category yet.
      </p>
    );
  }

  return (
    <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
      {filtered.map((badge) => (
        <BadgeCard
          key={badge.badge_id}
          badge={badge}
          earned={badge.isEarned}
          onClick={() => onBadgeClick(badge)}
        />
      ))}
    </div>
  );
}
