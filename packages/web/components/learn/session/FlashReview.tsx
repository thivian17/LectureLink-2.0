"use client";

import { useState, useRef, useEffect } from "react";
import { Card, CardContent } from "@/components/ui/card";
import { cn } from "@/lib/utils";
import { XPPopup } from "./XPPopup";
import { submitFlashReview } from "@/lib/api";
import type { FlashReviewCard } from "@/types/database";

interface FlashReviewProps {
  cards: FlashReviewCard[];
  sessionId: string;
  onComplete: () => void;
}

export function FlashReview({ cards, sessionId, onComplete }: FlashReviewProps) {
  const [currentIndex, setCurrentIndex] = useState(0);
  const [selectedAnswer, setSelectedAnswer] = useState<number | null>(null);
  const [isCorrect, setIsCorrect] = useState<boolean | null>(null);
  const [xpAmount, setXpAmount] = useState(0);
  const [xpTrigger, setXpTrigger] = useState(0);
  const startTime = useRef(0);

  const card = cards[currentIndex];

  useEffect(() => {
    startTime.current = Date.now();
    setSelectedAnswer(null);
    setIsCorrect(null);
  }, [currentIndex]);

  if (!card) {
    onComplete();
    return null;
  }

  async function handleSelect(index: number) {
    if (selectedAnswer !== null) return;
    setSelectedAnswer(index);
    // eslint-disable-next-line react-hooks/purity
    const elapsed = Math.round(Date.now() - startTime.current); // event handler, not render

    try {
      const result = await submitFlashReview(sessionId, card.card_id, index, elapsed);
      setIsCorrect(result.correct);
      setXpAmount(result.xp_earned);
      setXpTrigger((t) => t + 1);
    } catch {
      setIsCorrect(index === card.correct_index);
    }

    setTimeout(() => {
      if (currentIndex < cards.length - 1) {
        setCurrentIndex((i) => i + 1);
      } else {
        onComplete();
      }
    }, 1500);
  }

  return (
    <div className="max-w-lg mx-auto space-y-4">
      {/* Progress dots */}
      <div className="flex items-center justify-center gap-1.5">
        {cards.map((_, i) => (
          <div
            key={i}
            className={cn(
              "h-2 w-2 rounded-full transition-colors",
              i < currentIndex && "bg-primary",
              i === currentIndex && "bg-primary/60 ring-2 ring-primary/30",
              i > currentIndex && "bg-muted",
            )}
          />
        ))}
      </div>

      <Card className="relative overflow-hidden">
        <XPPopup xp={xpAmount} trigger={xpTrigger} />
        <CardContent className="p-5 space-y-4">
          <p className="text-xs text-muted-foreground">{card.concept_title}</p>
          <p className="text-base font-medium">{card.question_text}</p>
          <div className="space-y-2">
            {card.options.map((option, i) => {
              const isSelected = selectedAnswer === i;
              const showCorrect = selectedAnswer !== null && isCorrect !== null;
              const isCorrectOption = card.correct_index === i;

              return (
                <button
                  key={i}
                  onClick={() => handleSelect(i)}
                  disabled={selectedAnswer !== null}
                  className={cn(
                    "w-full text-left rounded-lg border p-3 text-sm transition-all duration-200",
                    selectedAnswer === null &&
                      "hover:border-primary/50 hover:bg-muted/50 cursor-pointer",
                    showCorrect && isCorrectOption &&
                      "border-green-500 bg-green-50 text-green-800",
                    showCorrect && isSelected && !isCorrectOption &&
                      "border-red-500 bg-red-50 text-red-800",
                    showCorrect && !isSelected && !isCorrectOption &&
                      "opacity-50",
                  )}
                >
                  {option}
                </button>
              );
            })}
          </div>
          <p className="text-[10px] text-muted-foreground text-right">
            Source: {card.source_lecture_title}
          </p>
        </CardContent>
      </Card>
    </div>
  );
}
