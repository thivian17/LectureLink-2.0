"use client";

import { CheckCircle2 } from "lucide-react";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { MarkdownContent } from "./MarkdownContent";

interface SummaryBlockProps {
  content: string;
  questionsAsked: number;
  questionsCorrect: number;
  mastery?: number;
}

export function SummaryBlock({
  content,
  questionsAsked,
  questionsCorrect,
  mastery,
}: SummaryBlockProps) {
  const accuracy =
    questionsAsked > 0
      ? Math.round((questionsCorrect / questionsAsked) * 100)
      : 0;

  return (
    <Card className="border-green-200 dark:border-green-800">
      <CardHeader className="pb-3">
        <CardTitle className="flex items-center gap-2 text-base">
          <CheckCircle2 className="h-4 w-4 text-green-600" />
          Concept Complete
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        <MarkdownContent
          content={content}
          className="prose prose-sm max-w-none dark:prose-invert leading-relaxed text-muted-foreground"
        />
        <div className="flex items-center gap-4 text-sm">
          <span className="text-muted-foreground">
            {questionsCorrect} of {questionsAsked} correct ({accuracy}%)
          </span>
          {mastery != null && (
            <div className="flex items-center gap-2 flex-1 max-w-[200px]">
              <Progress value={mastery * 100} className="h-1.5" />
              <span className="text-xs text-muted-foreground">
                {Math.round(mastery * 100)}%
              </span>
            </div>
          )}
        </div>
      </CardContent>
    </Card>
  );
}
