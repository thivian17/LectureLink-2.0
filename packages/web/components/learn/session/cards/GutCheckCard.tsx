"use client";

import { useState } from "react";
import { CheckCircle2, XCircle } from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";
import { cn } from "@/lib/utils";
import { submitGutCheck } from "@/lib/api";
import type { StudyCard } from "@/types/database";

interface GutCheckCardProps {
  card: StudyCard;
  sessionId: string;
  conceptId: string;
  onInteraction: (xp?: number) => void;
}

export function GutCheckCard({ card, sessionId, conceptId, onInteraction }: GutCheckCardProps) {
  const [selectedIndex, setSelectedIndex] = useState<number | null>(null);
  const [result, setResult] = useState<{ correct: boolean; explanation: string } | null>(null);

  async function handleSelect(index: number) {
    if (selectedIndex !== null) return;
    setSelectedIndex(index);

    try {
      const apiResult = await submitGutCheck(sessionId, conceptId, index);
      setResult({
        correct: apiResult.correct,
        explanation: card.explanation ?? "",
      });
      onInteraction(apiResult.xp_earned);
    } catch {
      const isCorrect = index === card.correct_index;
      setResult({
        correct: isCorrect,
        explanation: card.explanation ?? "",
      });
      onInteraction(isCorrect ? 10 : 0);
    }
  }

  return (
    <Card>
      <CardContent className="p-5 space-y-3">
        <p className="text-sm font-medium">Gut check</p>
        {card.question_text && (
          <p className="text-sm">{card.question_text}</p>
        )}

        <div className="space-y-2">
          {card.options?.map((option, i) => {
            const isSelected = selectedIndex === i;
            const showResult = result !== null;
            const isCorrectOption = card.correct_index === i;

            return (
              <button
                key={i}
                onClick={() => handleSelect(i)}
                disabled={selectedIndex !== null}
                className={cn(
                  "w-full text-left rounded-lg border p-3 text-sm transition-all duration-200",
                  selectedIndex === null &&
                    "hover:border-primary/50 hover:bg-muted/50 cursor-pointer",
                  showResult && isCorrectOption &&
                    "border-green-500 bg-green-50 text-green-800",
                  showResult && isSelected && !isCorrectOption &&
                    "border-red-500 bg-red-50 text-red-800",
                  showResult && !isSelected && !isCorrectOption &&
                    "opacity-50",
                )}
              >
                {option}
              </button>
            );
          })}
        </div>

        {result && (
          <div className={cn(
            "rounded-lg p-3 text-sm animate-in fade-in duration-300",
            result.correct
              ? "bg-green-50 border border-green-200"
              : "bg-red-50 border border-red-200",
          )}>
            <div className="flex items-center gap-1.5 mb-1 font-medium">
              {result.correct ? (
                <><CheckCircle2 className="h-4 w-4 text-green-600" /> Correct!</>
              ) : (
                <><XCircle className="h-4 w-4 text-red-600" /> Not quite</>
              )}
            </div>
            <p className="text-muted-foreground">{result.explanation}</p>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
