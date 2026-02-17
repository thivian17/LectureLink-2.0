"use client";

import { BarChart3, Brain, Target, TrendingUp } from "lucide-react";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import type { PerformanceData, ConceptMastery } from "@/types/database";

interface PerformanceDashboardProps {
  performance: PerformanceData;
}

export function PerformanceDashboard({ performance }: PerformanceDashboardProps) {
  const { overall, concepts } = performance;

  return (
    <div className="space-y-4">
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <MetricCard
          icon={<Target className="h-4 w-4" />}
          label="Overall Accuracy"
          value={`${Math.round(overall.overall_accuracy * 100)}%`}
        />
        <MetricCard
          icon={<BarChart3 className="h-4 w-4" />}
          label="Avg Quiz Score"
          value={
            overall.average_quiz_score != null
              ? `${Math.round(overall.average_quiz_score)}%`
              : "N/A"
          }
        />
        <MetricCard
          icon={<Brain className="h-4 w-4" />}
          label="Concepts Mastered"
          value={`${performance.strong_concepts.length}/${concepts.length}`}
        />
        <MetricCard
          icon={<TrendingUp className="h-4 w-4" />}
          label="Quizzes Taken"
          value={`${overall.quizzes_taken}`}
        />
      </div>

      {concepts.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Concept Mastery</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-2">
              {concepts.slice(0, 15).map((c) => (
                <ConceptMasteryBar key={c.concept_id} concept={c} />
              ))}
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}

function MetricCard({
  icon,
  label,
  value,
}: {
  icon: React.ReactNode;
  label: string;
  value: string;
}) {
  return (
    <Card>
      <CardContent className="pt-6">
        <div className="flex items-center gap-2 text-sm text-muted-foreground mb-1">
          {icon}
          {label}
        </div>
        <p className="text-2xl font-bold">{value}</p>
      </CardContent>
    </Card>
  );
}

function ConceptMasteryBar({ concept }: { concept: ConceptMastery }) {
  const pct = Math.round(concept.mastery * 100);
  const trendConfig: Record<string, { label: string; cls: string }> = {
    improving: { label: "Improving", cls: "text-green-600 border-green-300" },
    declining: { label: "Declining", cls: "text-red-600 border-red-300" },
    stable: { label: "Stable", cls: "text-blue-600 border-blue-300" },
    new: { label: "New", cls: "text-gray-600 border-gray-300" },
  };
  const trend = trendConfig[concept.trend] ?? trendConfig.new;

  return (
    <div className="flex items-center gap-3">
      <div className="flex-1 min-w-0">
        <div className="flex items-center justify-between mb-1">
          <span className="text-sm truncate">{concept.title}</span>
          <div className="flex items-center gap-2 shrink-0 ml-2">
            <Badge variant="outline" className={cn("text-xs", trend.cls)}>
              {trend.label}
            </Badge>
            <span className="text-xs text-muted-foreground">{pct}%</span>
          </div>
        </div>
        <div className="h-2 w-full overflow-hidden rounded-full bg-muted">
          <div
            className={cn(
              "h-full rounded-full transition-all",
              pct >= 80 ? "bg-green-500" :
              pct >= 50 ? "bg-yellow-500" :
              pct > 0 ? "bg-orange-500" :
              "bg-red-500",
            )}
            style={{ width: `${pct}%` }}
          />
        </div>
      </div>
    </div>
  );
}
