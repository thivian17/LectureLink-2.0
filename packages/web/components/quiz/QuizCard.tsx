"use client";

import React from "react";
import Link from "next/link";
import { format } from "date-fns";
import { Clock, Check, Loader2, XCircle, Trophy } from "lucide-react";

import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import type { Quiz, QuizStatus } from "@/types/database";

const STATUS_CONFIG: Record<
  QuizStatus,
  { label: string; className: string; icon: React.ElementType }
> = {
  pending: {
    label: "Pending",
    className: "bg-gray-100 text-gray-700 border-gray-200",
    icon: Clock,
  },
  generating: {
    label: "Generating...",
    className: "bg-blue-100 text-blue-700 border-blue-200",
    icon: Loader2,
  },
  ready: {
    label: "Ready",
    className: "bg-green-100 text-green-700 border-green-200",
    icon: Check,
  },
  failed: {
    label: "Failed",
    className: "bg-red-100 text-red-700 border-red-200",
    icon: XCircle,
  },
};

interface QuizCardProps {
  quiz: Quiz;
  courseId: string;
}

export const QuizCard = React.memo(function QuizCard({ quiz, courseId }: QuizCardProps) {
  const config = STATUS_CONFIG[quiz.status];
  const Icon = config.icon;
  const href =
    quiz.status === "ready"
      ? `/dashboard/courses/${courseId}/quiz/${quiz.id}`
      : `/dashboard/courses/${courseId}/quizzes`;

  return (
    <Link href={href}>
      <Card className="h-full transition-colors hover:bg-accent/50">
        <CardHeader className="pb-3">
          <div className="flex items-start justify-between gap-2">
            <CardTitle className="text-base leading-tight truncate">
              {quiz.title}
            </CardTitle>
            <Badge
              variant="outline"
              className={cn("gap-1 shrink-0 font-medium", config.className)}
            >
              <Icon
                className={cn(
                  "h-3 w-3",
                  quiz.status === "generating" && "animate-spin",
                )}
              />
              {config.label}
            </Badge>
          </div>
          <CardDescription>
            {format(new Date(quiz.created_at), "MMM d, yyyy")}
            {" · "}
            {quiz.question_count} questions
            {" · "}
            {quiz.difficulty.charAt(0).toUpperCase() + quiz.difficulty.slice(1)}
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="flex items-center gap-4">
            {quiz.best_score != null ? (
              <div className="flex items-center gap-2">
                <Trophy className="h-4 w-4 text-yellow-500" />
                <span className="text-2xl font-bold">{quiz.best_score}%</span>
              </div>
            ) : (
              <span className="text-sm text-muted-foreground">
                Not attempted
              </span>
            )}
            {quiz.attempt_count > 0 && (
              <span className="text-xs text-muted-foreground">
                Attempted {quiz.attempt_count} time
                {quiz.attempt_count !== 1 ? "s" : ""}
              </span>
            )}
          </div>
        </CardContent>
      </Card>
    </Link>
  );
});
