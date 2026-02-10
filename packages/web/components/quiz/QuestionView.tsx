"use client";

import { MCQOptions } from "@/components/quiz/MCQOptions";
import { TrueFalseOptions } from "@/components/quiz/TrueFalseOptions";
import { ShortAnswerInput } from "@/components/quiz/ShortAnswerInput";
import { QuestionFeedback } from "@/components/quiz/QuestionFeedback";
import { Badge } from "@/components/ui/badge";
import type { QuizQuestion } from "@/types/database";

interface QuestionViewProps {
  question: QuizQuestion;
  selectedAnswer: string | null;
  onAnswer: (answer: string) => void;
  showFeedback: boolean;
  courseId: string;
}

export function QuestionView({
  question,
  selectedAnswer,
  onAnswer,
  showFeedback,
  courseId,
}: QuestionViewProps) {
  const isCorrect = selectedAnswer === question.correct_answer;
  const feedbackDisabled = showFeedback;

  return (
    <div className="space-y-6">
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

      {question.question_type === "mcq" && question.options && (
        <MCQOptions
          options={question.options}
          selectedAnswer={selectedAnswer}
          onSelect={onAnswer}
          disabled={feedbackDisabled}
          correctAnswer={question.correct_answer}
          showFeedback={showFeedback}
        />
      )}

      {question.question_type === "true_false" && (
        <TrueFalseOptions
          selectedAnswer={selectedAnswer}
          onSelect={onAnswer}
          disabled={feedbackDisabled}
          correctAnswer={question.correct_answer}
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

      {showFeedback && selectedAnswer != null && (
        <QuestionFeedback
          isCorrect={isCorrect}
          explanation={question.explanation}
          sourceLectureId={question.source_lecture_id}
          sourceLectureTitle={question.source_lecture_title}
          sourceTimestampSeconds={question.source_timestamp_seconds}
          courseId={courseId}
        />
      )}
    </div>
  );
}
