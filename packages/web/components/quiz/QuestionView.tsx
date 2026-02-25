"use client";

import dynamic from "next/dynamic";
import { MCQOptions } from "@/components/quiz/MCQOptions";
import { TrueFalseOptions } from "@/components/quiz/TrueFalseOptions";
import { ShortAnswerInput } from "@/components/quiz/ShortAnswerInput";
import { QuestionFeedback } from "@/components/quiz/QuestionFeedback";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import type { QuizQuestion, CodeGradingResult } from "@/types/database";

const CodeQuestion = dynamic(
  () => import("@/components/quiz/CodeQuestion").then((m) => m.CodeQuestion),
  {
    ssr: false,
    loading: () => (
      <div className="space-y-4">
        <Skeleton className="h-8 w-48" />
        <Skeleton className="h-64 w-full rounded-md" />
        <Skeleton className="h-9 w-32" />
      </div>
    ),
  },
);

function checkAnswerCorrectness(
  question: QuizQuestion,
  selectedAnswer: string | null,
): boolean {
  if (selectedAnswer == null || selectedAnswer === "") return false;

  // MCQ: compare selected text against the option at correct_option_index
  if (question.question_type === "mcq") {
    if (question.correct_option_index != null && question.options) {
      return question.options[question.correct_option_index] === selectedAnswer;
    }
    // Fallback: case-insensitive text comparison
    return selectedAnswer.trim().toLowerCase() === (question.correct_answer ?? "").trim().toLowerCase();
  }

  // True/False: use hardcoded ["True", "False"] to match TrueFalseOptions component
  if (question.question_type === "true_false") {
    if (question.correct_option_index != null) {
      const tfOptions = ["True", "False"];
      return tfOptions[question.correct_option_index] === selectedAnswer;
    }
    return selectedAnswer.trim().toLowerCase() === (question.correct_answer ?? "").trim().toLowerCase();
  }

  // Short answer: case-insensitive trimmed comparison
  if (question.question_type === "short_answer") {
    return selectedAnswer.trim().toLowerCase() === (question.correct_answer ?? "").trim().toLowerCase();
  }

  return false;
}

interface QuestionViewProps {
  question: QuizQuestion;
  selectedAnswer: string | null;
  onAnswer: (answer: string) => void;
  showFeedback: boolean;
  courseId: string;
  quizId?: string;
  gradingResult?: CodeGradingResult;
  isSubmitting?: boolean;
  timeElapsed?: number;
}

export function QuestionView({
  question,
  selectedAnswer,
  onAnswer,
  showFeedback,
  courseId,
  quizId,
  gradingResult,
  isSubmitting,
  timeElapsed,
}: QuestionViewProps) {
  const isCorrect = checkAnswerCorrectness(question, selectedAnswer);
  const feedbackDisabled = showFeedback;

  const isCodeQuestion =
    question.question_type === "code_writing" ||
    question.question_type === "code_fix" ||
    question.question_type === "code_explain";

  return (
    <div className="space-y-6">
      {/* Header for non-code questions (CodeQuestion renders its own) */}
      {!isCodeQuestion && (
        <div className="space-y-3">
          <p className="text-lg font-medium leading-relaxed">
            {question.question_text}
          </p>
          {question.concept && (
            <Badge variant="secondary" className="text-xs">
              {question.concept}
            </Badge>
          )}
        </div>
      )}

      {question.question_type === "mcq" && question.options && (
        <MCQOptions
          options={question.options}
          selectedAnswer={selectedAnswer}
          onSelect={onAnswer}
          disabled={feedbackDisabled}
          correctAnswer={question.correct_answer}
          correctOptionIndex={question.correct_option_index}
          showFeedback={showFeedback}
        />
      )}

      {question.question_type === "true_false" && (
        <TrueFalseOptions
          selectedAnswer={selectedAnswer}
          onSelect={onAnswer}
          disabled={feedbackDisabled}
          correctAnswer={question.correct_answer}
          correctOptionIndex={question.correct_option_index}
          showFeedback={showFeedback}
        />
      )}

      {question.question_type === "short_answer" && (
        <ShortAnswerInput
          value={selectedAnswer ?? ""}
          onChange={onAnswer}
          disabled={feedbackDisabled}
          correctAnswer={question.correct_answer}
          showFeedback={showFeedback}
          isCorrect={isCorrect}
        />
      )}

      {(question.question_type === "code_writing" ||
        question.question_type === "code_fix" ||
        question.question_type === "code_explain") &&
        quizId && (
          <CodeQuestion
            question={question}
            quizId={quizId}
            selectedAnswer={selectedAnswer}
            onAnswer={onAnswer}
            showFeedback={showFeedback}
            gradingResult={gradingResult}
            isSubmitting={isSubmitting}
            timeElapsed={timeElapsed}
          />
        )}

      {showFeedback && selectedAnswer != null && question.explanation && (
        <QuestionFeedback
          isCorrect={isCorrect}
          explanation={question.explanation}
          sourceLectureId={question.source_lecture_id ?? null}
          sourceLectureTitle={question.source_lecture_title ?? null}
          sourceTimestampSeconds={question.source_timestamp_seconds ?? null}
          courseId={courseId}
        />
      )}
    </div>
  );
}
