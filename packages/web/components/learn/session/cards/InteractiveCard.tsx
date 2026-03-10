"use client";

import { useState } from "react";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import type { StudyCard } from "@/types/database";

interface InteractiveCardProps {
  card: StudyCard;
  onInteraction: (xp?: number) => void;
}

export function InteractiveCard({ card, onInteraction }: InteractiveCardProps) {
  const [userInput, setUserInput] = useState("");
  const [showHint, setShowHint] = useState(false);
  const [submitted, setSubmitted] = useState(false);
  const [isCorrect, setIsCorrect] = useState(false);

  function handleSubmit() {
    if (!userInput.trim()) return;
    const normalizedInput = userInput.replace(/\s/g, "").toLowerCase();
    const normalizedAnswer = (card.answer ?? "").replace(/\s/g, "").toLowerCase();
    const correct = normalizedInput === normalizedAnswer;
    setIsCorrect(correct);
    setSubmitted(true);
    onInteraction(correct ? 15 : 5);
  }

  return (
    <Card>
      <CardContent className="p-5 space-y-4">
        <div className="flex items-center gap-2">
          <h3 className="text-sm font-semibold">Challenge</h3>
          {card.challenge_type && (
            <Badge variant="secondary" className="text-[10px]">
              {card.challenge_type}
            </Badge>
          )}
        </div>

        {card.prompt && (
          <p className="text-sm">{card.prompt}</p>
        )}

        {!submitted && (
          <>
            <Input
              value={userInput}
              onChange={(e) => setUserInput(e.target.value)}
              placeholder="Your answer..."
              onKeyDown={(e) => e.key === "Enter" && handleSubmit()}
            />
            <div className="flex gap-2">
              {card.hint && (
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => setShowHint(!showHint)}
                >
                  {showHint ? "Hide hint" : "Hint"}
                </Button>
              )}
              <Button
                size="sm"
                className="ml-auto"
                onClick={handleSubmit}
                disabled={!userInput.trim()}
              >
                Check
              </Button>
            </div>
            {showHint && card.hint && (
              <p className="text-xs text-muted-foreground bg-muted/50 rounded-md p-2">
                {card.hint}
              </p>
            )}
          </>
        )}

        {submitted && (
          <div className="space-y-3 animate-in fade-in duration-200">
            <div className={cn(
              "rounded-lg border p-3",
              isCorrect
                ? "border-green-200 bg-green-50"
                : "border-red-200 bg-red-50",
            )}>
              <p className={cn(
                "text-sm font-medium",
                isCorrect ? "text-green-800" : "text-red-800",
              )}>
                {isCorrect ? "Correct!" : "Not quite"}
              </p>
              {!isCorrect && (
                <p className="text-sm text-muted-foreground mt-1">
                  Answer: {card.answer}
                </p>
              )}
            </div>

            {card.solution_steps && (
              <div className="space-y-1.5">
                <p className="text-xs font-medium text-muted-foreground">Solution:</p>
                {card.solution_steps.map((step, i) => (
                  <p key={i} className="text-xs text-muted-foreground">{step}</p>
                ))}
              </div>
            )}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
