"use client";

import { useState, useEffect, useCallback } from "react";
import { useRouter } from "next/navigation";
import { toast } from "sonner";
import { Award } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from "@/components/ui/dialog";
import { Progress } from "@/components/ui/progress";
import { Skeleton } from "@/components/ui/skeleton";
import { BadgeGrid } from "@/components/learn/BadgeGrid";
import { getUserBadges, AuthError } from "@/lib/api";
import type { BadgeInfo } from "@/types/database";

const CATEGORIES = ["streak", "mastery", "assessment", "behavior", "rare"];

export default function BadgesPage() {
  const router = useRouter();
  const [earned, setEarned] = useState<BadgeInfo[]>([]);
  const [available, setAvailable] = useState<BadgeInfo[]>([]);
  const [loading, setLoading] = useState(true);
  const [categoryFilter, setCategoryFilter] = useState<string | null>(null);
  const [selectedBadge, setSelectedBadge] = useState<BadgeInfo | null>(null);

  const load = useCallback(async () => {
    try {
      const data = await getUserBadges();
      setEarned(data.earned);
      setAvailable(data.available);
    } catch (err) {
      if (err instanceof AuthError) {
        router.push("/login");
        return;
      }
      toast.error("Failed to load badges");
    } finally {
      setLoading(false);
    }
  }, [router]);

  useEffect(() => {
    load();
  }, [load]);

  const isEarned = selectedBadge
    ? earned.some((b) => b.badge_id === selectedBadge.badge_id)
    : false;

  return (
    <div className="space-y-5">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Badges</h1>
        <p className="text-muted-foreground text-sm">
          {earned.length} earned · {available.length} available
        </p>
      </div>

      {/* Category filters */}
      <div className="flex flex-wrap gap-2">
        <Badge
          variant={categoryFilter === null ? "default" : "outline"}
          className="cursor-pointer"
          onClick={() => setCategoryFilter(null)}
        >
          All
        </Badge>
        {CATEGORIES.map((cat) => (
          <Badge
            key={cat}
            variant={categoryFilter === cat ? "default" : "outline"}
            className="cursor-pointer capitalize"
            onClick={() => setCategoryFilter(categoryFilter === cat ? null : cat)}
          >
            {cat}
          </Badge>
        ))}
      </div>

      {loading ? (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {[1, 2, 3, 4, 5, 6].map((i) => (
            <Skeleton key={i} className="h-32 rounded-xl" />
          ))}
        </div>
      ) : (
        <BadgeGrid
          earned={earned}
          available={available}
          categoryFilter={categoryFilter}
          onBadgeClick={setSelectedBadge}
        />
      )}

      {/* Badge detail dialog */}
      <Dialog open={selectedBadge !== null} onOpenChange={() => setSelectedBadge(null)}>
        <DialogContent>
          {selectedBadge && (
            <>
              <DialogHeader>
                <div className="flex items-center gap-3">
                  <span className="text-3xl">{selectedBadge.icon || "🏆"}</span>
                  <div>
                    <DialogTitle>{selectedBadge.name}</DialogTitle>
                    <DialogDescription>{selectedBadge.description}</DialogDescription>
                  </div>
                </div>
              </DialogHeader>
              <div className="space-y-3">
                <Badge variant="outline" className="capitalize">{selectedBadge.category}</Badge>
                {isEarned && selectedBadge.earned_at ? (
                  <p className="text-sm text-muted-foreground flex items-center gap-1.5">
                    <Award className="h-4 w-4 text-amber-500" />
                    Earned on{" "}
                    {new Date(selectedBadge.earned_at).toLocaleDateString("en", {
                      month: "long",
                      day: "numeric",
                      year: "numeric",
                    })}
                  </p>
                ) : (
                  selectedBadge.progress != null && (
                    <div className="space-y-1.5">
                      <p className="text-sm text-muted-foreground">Progress</p>
                      <Progress value={selectedBadge.progress} className="h-2" />
                      <p className="text-xs text-muted-foreground text-right">
                        {Math.round(selectedBadge.progress)}%
                        {selectedBadge.target != null && ` of ${selectedBadge.target}`}
                      </p>
                    </div>
                  )
                )}
              </div>
            </>
          )}
        </DialogContent>
      </Dialog>
    </div>
  );
}
