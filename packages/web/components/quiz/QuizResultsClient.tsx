"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { Loader2 } from "lucide-react";

import { Button } from "@/components/ui/button";
import { QuizResults } from "@/components/quiz/QuizResults";
import type { QuizSubmissionResult } from "@/types/database";

interface QuizResultsClientProps {
  courseId: string;
  quizId: string;
}

export function QuizResultsClient({
  courseId,
  quizId,
}: QuizResultsClientProps) {
  const router = useRouter();
  const [result, setResult] = useState<QuizSubmissionResult | null>(null);

  useEffect(() => {
    const stored = sessionStorage.getItem(`quiz-result-${quizId}`);
    if (stored) {
      setResult(JSON.parse(stored));
    }
  }, [quizId]);

  if (!result) {
    return (
      <div className="flex flex-col items-center justify-center py-16 space-y-4">
        <p className="text-sm text-muted-foreground">
          No quiz results found. Try taking the quiz first.
        </p>
        <Button
          variant="outline"
          onClick={() =>
            router.push(`/dashboard/courses/${courseId}/quiz/${quizId}`)
          }
        >
          Take Quiz
        </Button>
      </div>
    );
  }

  return <QuizResults result={result} courseId={courseId} quizId={quizId} />;
}
