"use client";

import { useState } from "react";
import { Loader2 } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
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
import type { Assessment, Lecture, QuizDifficulty } from "@/types/database";
import {
  QuizModeSelector,
  type QuizModeConfig,
} from "@/components/quiz/QuizModeSelector";

interface GenerateQuizDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  assessments: Assessment[];
  lectures: Lecture[];
  onGenerate: (options: {
    target_assessment_id: string | null;
    lecture_ids: string[] | null;
    question_count: number;
    difficulty: QuizDifficulty;
    include_coding?: boolean;
    coding_ratio?: number;
    coding_language?: string;
    coding_only?: boolean;
  }) => Promise<void>;
}

const QUESTION_COUNTS = [5, 10, 15, 20];
const DIFFICULTIES: { value: QuizDifficulty; label: string }[] = [
  { value: "easy", label: "Easy" },
  { value: "medium", label: "Medium" },
  { value: "hard", label: "Hard" },
  { value: "adaptive", label: "Adaptive" },
];

export function GenerateQuizDialog({
  open,
  onOpenChange,
  assessments,
  lectures,
  onGenerate,
}: GenerateQuizDialogProps) {
  const [target, setTarget] = useState<"full" | "assessment" | "lectures">(
    "full",
  );
  const [assessmentId, setAssessmentId] = useState<string | null>(null);
  const [selectedLectureIds, setSelectedLectureIds] = useState<string[]>([]);
  const [questionCount, setQuestionCount] = useState(10);
  const [difficulty, setDifficulty] = useState<QuizDifficulty>("medium");
  const [quizMode, setQuizMode] = useState<QuizModeConfig>({
    include_coding: false,
    coding_only: false,
    coding_ratio: 0,
    coding_language: "python",
    suggested_num_questions: 10,
  });
  const [generating, setGenerating] = useState(false);

  function handleModeChange(config: QuizModeConfig) {
    setQuizMode(config);
    setQuestionCount(config.suggested_num_questions);
  }

  async function handleGenerate() {
    setGenerating(true);
    try {
      await onGenerate({
        target_assessment_id: target === "assessment" ? assessmentId : null,
        lecture_ids: target === "lectures" ? selectedLectureIds : null,
        question_count: questionCount,
        difficulty,
        include_coding: quizMode.include_coding,
        coding_only: quizMode.coding_only,
        coding_ratio: quizMode.coding_ratio,
        coding_language: quizMode.coding_language,
      });
    } finally {
      setGenerating(false);
    }
  }

  function toggleLecture(lectureId: string) {
    setSelectedLectureIds((prev) =>
      prev.includes(lectureId)
        ? prev.filter((id) => id !== lectureId)
        : [...prev, lectureId],
    );
  }

  const upcomingAssessments = assessments.filter((a) => {
    if (!a.due_date) return false;
    return new Date(a.due_date) > new Date();
  });

  const completedLectures = lectures
    .filter((l) => l.processing_status === "completed")
    .sort((a, b) => (a.lecture_number ?? 999) - (b.lecture_number ?? 999));

  const canGenerate =
    !generating &&
    !(target === "assessment" && !assessmentId) &&
    !(target === "lectures" && selectedLectureIds.length === 0);

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
            <div className="flex flex-wrap gap-2">
              <Button
                type="button"
                variant={target === "full" ? "default" : "outline"}
                size="sm"
                onClick={() => setTarget("full")}
              >
                Full course
              </Button>
              <Button
                type="button"
                variant={target === "lectures" ? "default" : "outline"}
                size="sm"
                onClick={() => setTarget("lectures")}
              >
                Specific lectures
              </Button>
              <Button
                type="button"
                variant={target === "assessment" ? "default" : "outline"}
                size="sm"
                onClick={() => setTarget("assessment")}
              >
                Target assessment
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

            {target === "lectures" && (
              <div className="mt-2 max-h-48 overflow-auto rounded-md border p-2 space-y-1">
                {completedLectures.length === 0 ? (
                  <p className="text-sm text-muted-foreground py-2 text-center">
                    No processed lectures available
                  </p>
                ) : (
                  completedLectures.map((lecture) => (
                    <label
                      key={lecture.id}
                      className="flex items-center gap-2 rounded-md px-2 py-1.5 hover:bg-accent/50 cursor-pointer"
                    >
                      <Checkbox
                        checked={selectedLectureIds.includes(lecture.id)}
                        onCheckedChange={() => toggleLecture(lecture.id)}
                      />
                      <span className="text-sm truncate">
                        {lecture.lecture_number != null && (
                          <span className="text-muted-foreground mr-1">
                            #{lecture.lecture_number}
                          </span>
                        )}
                        {lecture.title}
                      </span>
                    </label>
                  ))
                )}
              </div>
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

          {/* Quiz mode */}
          <QuizModeSelector onChange={handleModeChange} />

          {/* Generate */}
          <div className="flex justify-end pt-2">
            <Button onClick={handleGenerate} disabled={!canGenerate}>
              {generating && (
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              )}
              Generate
            </Button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}
