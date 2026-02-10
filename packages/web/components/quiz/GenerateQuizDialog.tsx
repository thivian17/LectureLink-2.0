"use client";

import { useState } from "react";
import { Loader2 } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { cn } from "@/lib/utils";
import type { Assessment, QuizDifficulty } from "@/types/database";

interface GenerateQuizDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  assessments: Assessment[];
  onGenerate: (options: {
    target_assessment_id: string | null;
    question_count: number;
    difficulty: QuizDifficulty;
  }) => Promise<void>;
}

const QUESTION_COUNTS = [5, 10, 15, 20];
const DIFFICULTIES: { value: QuizDifficulty; label: string }[] = [
  { value: "easy", label: "Easy" },
  { value: "medium", label: "Medium" },
  { value: "hard", label: "Hard" },
];

export function GenerateQuizDialog({
  open,
  onOpenChange,
  assessments,
  onGenerate,
}: GenerateQuizDialogProps) {
  const [target, setTarget] = useState<"full" | "assessment">("full");
  const [assessmentId, setAssessmentId] = useState<string | null>(null);
  const [questionCount, setQuestionCount] = useState(10);
  const [difficulty, setDifficulty] = useState<QuizDifficulty>("medium");
  const [generating, setGenerating] = useState(false);

  async function handleGenerate() {
    setGenerating(true);
    try {
      await onGenerate({
        target_assessment_id: target === "assessment" ? assessmentId : null,
        question_count: questionCount,
        difficulty,
      });
    } finally {
      setGenerating(false);
    }
  }

  const upcomingAssessments = assessments.filter((a) => {
    if (!a.due_date) return false;
    return new Date(a.due_date) > new Date();
  });

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Generate Quiz</DialogTitle>
          <DialogDescription>
            Create an AI-generated quiz to test your knowledge.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-5 pt-2">
          {/* Target */}
          <div className="space-y-2">
            <Label>Target</Label>
            <div className="flex gap-2">
              <Button
                type="button"
                variant={target === "full" ? "default" : "outline"}
                size="sm"
                onClick={() => setTarget("full")}
              >
                Full course review
              </Button>
              <Button
                type="button"
                variant={target === "assessment" ? "default" : "outline"}
                size="sm"
                onClick={() => setTarget("assessment")}
              >
                Target an assessment
              </Button>
            </div>
            {target === "assessment" && (
              <Select
                value={assessmentId ?? ""}
                onValueChange={(v) => setAssessmentId(v || null)}
              >
                <SelectTrigger className="mt-2">
                  <SelectValue placeholder="Select an assessment" />
                </SelectTrigger>
                <SelectContent>
                  {upcomingAssessments.map((a) => (
                    <SelectItem key={a.id} value={a.id}>
                      {a.title}
                      {a.due_date && (
                        <span className="ml-2 text-muted-foreground">
                          (due{" "}
                          {new Date(a.due_date).toLocaleDateString("en-US", {
                            month: "short",
                            day: "numeric",
                          })}
                          )
                        </span>
                      )}
                    </SelectItem>
                  ))}
                  {upcomingAssessments.length === 0 && (
                    <SelectItem value="none" disabled>
                      No upcoming assessments
                    </SelectItem>
                  )}
                </SelectContent>
              </Select>
            )}
          </div>

          {/* Number of questions */}
          <div className="space-y-2">
            <Label>Number of questions</Label>
            <div className="flex gap-2">
              {QUESTION_COUNTS.map((count) => (
                <Button
                  key={count}
                  type="button"
                  variant={questionCount === count ? "default" : "outline"}
                  size="sm"
                  className="min-w-[3rem]"
                  onClick={() => setQuestionCount(count)}
                >
                  {count}
                </Button>
              ))}
            </div>
          </div>

          {/* Difficulty */}
          <div className="space-y-2">
            <Label>Difficulty</Label>
            <div className="flex gap-2">
              {DIFFICULTIES.map((d) => (
                <Button
                  key={d.value}
                  type="button"
                  variant={difficulty === d.value ? "default" : "outline"}
                  size="sm"
                  onClick={() => setDifficulty(d.value)}
                >
                  {d.label}
                </Button>
              ))}
            </div>
          </div>

          {/* Generate */}
          <div className="flex justify-end pt-2">
            <Button
              onClick={handleGenerate}
              disabled={
                generating ||
                (target === "assessment" && !assessmentId)
              }
            >
              {generating && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              Generate
            </Button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}
