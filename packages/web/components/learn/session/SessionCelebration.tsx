"use client";

import { useEffect, useMemo, useState } from "react";
import { useRouter, useParams } from "next/navigation";
import { Flame, Award, ArrowUp, TrendingUp, Sparkles } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { cn } from "@/lib/utils";
import type { LearnSessionComplete } from "@/types/database";

interface SessionCelebrationProps {
  data: LearnSessionComplete;
}

export function SessionCelebration({ data }: SessionCelebrationProps) {
  const router = useRouter();
  const params = useParams<{ courseId: string }>();
  const [showConfetti, setShowConfetti] = useState(true);

  const confettiPieces = useMemo(() => {
    const COLORS = ["#ef4444", "#f59e0b", "#10b981", "#3b82f6", "#8b5cf6", "#ec4899", "#06b6d4"];
    return Array.from({ length: 30 }, (_, i) => ({
      left: `${(i * 37 + 13) % 100}%`,
      delay: `${(i * 0.07) % 2}s`,
      duration: `${2 + (i * 0.13) % 2}s`,
      color: COLORS[i % 7],
      width: `${6 + (i * 0.4) % 6}px`,
      height: `${6 + (i * 0.3) % 6}px`,
      radius: i % 2 === 0 ? "50%" : "2px",
    }));
  }, []);

  useEffect(() => {
    const timer = setTimeout(() => setShowConfetti(false), 4000);
    return () => clearTimeout(timer);
  }, []);

  const { session_summary, xp_summary, streak, badges_earned, tomorrow_preview } = data;

  return (
    <div className="max-w-lg mx-auto space-y-5 relative">
      {/* Confetti */}
      {showConfetti && (
        <div className="fixed inset-0 pointer-events-none overflow-hidden z-50">
          {confettiPieces.map((piece, i) => (
            <div
              key={i}
              className="absolute animate-confetti"
              style={{
                left: piece.left,
                animationDelay: piece.delay,
                animationDuration: piece.duration,
                backgroundColor: piece.color,
                width: piece.width,
                height: piece.height,
                borderRadius: piece.radius,
              }}
            />
          ))}
          <style jsx>{`
            @keyframes confettiFall {
              0% { transform: translateY(-10vh) rotate(0deg); opacity: 1; }
              100% { transform: translateY(110vh) rotate(720deg); opacity: 0; }
            }
            .animate-confetti {
              animation: confettiFall linear forwards;
            }
          `}</style>
        </div>
      )}

      {/* Header */}
      <div className="text-center space-y-1">
        <Sparkles className="h-8 w-8 text-amber-500 mx-auto" />
        <h1 className="text-2xl font-bold">Session Complete!</h1>
        <p className="text-muted-foreground text-sm">
          {session_summary.duration_minutes} min · {session_summary.quiz_score.correct}/{session_summary.quiz_score.total} quiz accuracy
        </p>
      </div>

      {/* Stats grid */}
      <div className="grid grid-cols-3 gap-3 text-center">
        <div className="rounded-lg bg-muted/50 p-3">
          <p className="text-2xl font-bold">{session_summary.concepts_covered.length}</p>
          <p className="text-xs text-muted-foreground">Concepts</p>
        </div>
        <div className="rounded-lg bg-muted/50 p-3">
          <p className="text-2xl font-bold">
            {session_summary.quiz_score.correct}/{session_summary.quiz_score.total}
          </p>
          <p className="text-xs text-muted-foreground">Quiz Score</p>
        </div>
        <div className="rounded-lg bg-muted/50 p-3">
          <p className="text-2xl font-bold text-primary">+{xp_summary.total_earned}</p>
          <p className="text-xs text-muted-foreground">XP Earned</p>
        </div>
      </div>

      {/* Level-up banner */}
      {xp_summary.leveled_up && (
        <div className="rounded-lg border border-primary/50 bg-primary/5 p-4 text-center animate-in zoom-in-95 fade-in duration-500">
          <p className="text-lg font-bold text-primary">🎉 Level Up!</p>
          <p className="text-sm text-muted-foreground">
            You reached Level {xp_summary.level_after}
          </p>
        </div>
      )}

      {/* Streak display */}
      {streak.current_streak > 0 && (
        <div className="flex items-center justify-center gap-2 text-sm">
          <span className="animate-bounce">🔥</span>
          <span className="font-medium">{streak.current_streak}-day streak!</span>
        </div>
      )}

      {/* XP Summary */}
      <Card>
        <CardContent className="p-4 space-y-3">
          <div className="flex items-center justify-between">
            <span className="text-sm font-medium">XP Breakdown</span>
            <span className="text-xl font-bold text-emerald-600">+{xp_summary.total_earned}</span>
          </div>
          <div className="space-y-1">
            {xp_summary.breakdown.map((item, i) => (
              <div key={i} className="flex justify-between text-xs text-muted-foreground">
                <span>{item.source}</span>
                <span>+{item.amount}</span>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>

      {/* Mastery deltas */}
      {session_summary.concepts_covered.length > 0 && (
        <Card>
          <CardContent className="p-4 space-y-2">
            <p className="text-sm font-medium flex items-center gap-1.5">
              <TrendingUp className="h-4 w-4 text-blue-500" />
              Mastery Progress
            </p>
            {session_summary.concepts_covered.map((c, i) => (
              <div key={i} className="flex items-center gap-2 text-sm">
                <span className="flex-1 truncate">{c.title}</span>
                <span className="text-muted-foreground tabular-nums">
                  {Math.round(c.mastery_before * 100)}%
                </span>
                <ArrowUp className="h-3 w-3 text-emerald-500" />
                <span className="font-medium tabular-nums">
                  {Math.round(c.mastery_after * 100)}%
                </span>
                <span className={cn(
                  "text-xs tabular-nums",
                  c.delta > 0 ? "text-emerald-600" : "text-muted-foreground",
                )}>
                  +{Math.round(c.delta * 100)}%
                </span>
              </div>
            ))}
          </CardContent>
        </Card>
      )}

      {/* Streak + Combo */}
      <div className="flex gap-3">
        <Card className="flex-1">
          <CardContent className="p-3 flex items-center gap-2">
            <Flame className={cn(
              "h-5 w-5",
              streak.studied_today ? "text-orange-500" : "text-gray-400",
            )} />
            <div>
              <p className="text-lg font-bold">{streak.current_streak}</p>
              <p className="text-[10px] text-muted-foreground">day streak</p>
            </div>
          </CardContent>
        </Card>
        <Card className="flex-1">
          <CardContent className="p-3 flex items-center gap-2">
            <span className="text-lg">🔥</span>
            <div>
              <p className="text-lg font-bold">x{session_summary.combo_max}</p>
              <p className="text-[10px] text-muted-foreground">max combo</p>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Badges earned */}
      {badges_earned.length > 0 && (
        <Card>
          <CardContent className="p-4 space-y-2">
            <p className="text-sm font-medium flex items-center gap-1.5">
              <Award className="h-4 w-4 text-amber-500" />
              New Badges!
            </p>
            {badges_earned.map((badge) => (
              <div key={badge.badge_id} className="flex items-center gap-2 text-sm rounded-lg bg-amber-50 border border-amber-200 p-2">
                <span className="text-lg">{badge.icon}</span>
                <div>
                  <p className="font-medium">{badge.name}</p>
                  <p className="text-xs text-muted-foreground">{badge.description}</p>
                </div>
              </div>
            ))}
          </CardContent>
        </Card>
      )}

      {/* Tomorrow preview */}
      {tomorrow_preview && (
        <p className="text-sm text-center text-muted-foreground">
          Tomorrow: {tomorrow_preview}
        </p>
      )}

      {/* Actions */}
      <div className="flex gap-3">
        <Button
          className="flex-1"
          onClick={() => router.push(`/dashboard/courses/${params.courseId}/learn`)}
        >
          Study Again
        </Button>
        <Button
          variant="outline"
          className="flex-1"
          onClick={() => router.push("/dashboard")}
        >
          Done for Today
        </Button>
      </div>
    </div>
  );
}
